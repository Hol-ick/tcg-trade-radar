"""Conservative parser and bounded gallery crawler."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
import time
import zlib
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .browser_transport import BrowserTransportError, get_default_transport
from .contracts import ExtractedRow, to_public_row
from .html import DCInsideHTMLParser, normalize_space, parse_html
from .intent import classify_listing


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/131.0 Safari/537.36 Marineford-Kaitori/0.1"
)
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; SM-S918N) "
    "AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"
)


class SourceResponseError(RuntimeError):
    """The public source returned a response that cannot be parsed safely."""

    def __init__(self, url: str, *, status: int | None, content_length: str | None, server: str | None, transport: str = "http", fallback_error: str = "") -> None:
        self.url = url
        self.status = status
        self.content_length = content_length
        self.server = server
        self.transport = transport
        self.fallback_error = fallback_error
        details = [f"url={url}"]
        if status is not None:
            details.append(f"status={status}")
        if content_length:
            details.append(f"content_length={content_length}")
        if server:
            details.append(f"server={server}")
        if fallback_error:
            details.append(f"fallback={fallback_error}")
        super().__init__("원본 서버가 빈 응답을 반환했습니다 (" + ", ".join(details) + ")")

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "url": self.url,
            "status": self.status,
            "content_length": self.content_length,
            "server": self.server,
            "transport": self.transport,
            "fallback_error": self.fallback_error,
            "reason": "empty_response",
        }
PRICE_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>만원|만|원)?"
    r"(?:\s*[\(\[]?\s*(?:택포|택배비\s*(?:포함|별도)?|배송비\s*(?:포함|별도)?|포함|별도)\s*[\)\]]?)?\s*$"
)
RARITY_RE = re.compile(
    r"(?P<rarity>(?:\d+\s*)?(?:프싴|영싴|쿼싴|퍼홀|홀로|시크페레|시크|얼티|울레|레어|슈레|울|슈|컬|싴|얼|구일))$"
)
QUANTITY_RE = re.compile(r"(?P<quantity>\d+)\s*장")
MULTI_CARD_RE = re.compile(r"[,/+]|&|\s(?:및|외)\s")
AMBIGUOUS_QUANTITY_RE = re.compile(r"여러\s*장|다수|수량\s*(?:불명|미상)|전부")
CSV_FIELDS = [
    "gallery_id", "post_title", "post_url", "posted_at", "card_name", "rarity",
    "raw_price", "price_krw", "price_unit", "quantity", "shipping_included", "author_name", "author_type",
    "shipping_price_krw", "review_status", "review_reason", "raw_line",
]


def fetch_text(url: str, timeout: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://gall.dcinside.com/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
        if not payload:
            raise SourceResponseError(
                url,
                status=getattr(response, "status", None),
                content_length=response.headers.get("Content-Length"),
                server=response.headers.get("Server"),
            )
    return _decode_http_payload(payload, response.headers.get("Content-Encoding"), encoding)


def mobile_url_for(url: str) -> str:
    """Map a public desktop gallery URL to DCInside's mobile read-only page."""
    parsed = urlparse(url)
    if parsed.netloc.lower() == "m.dcinside.com" and parsed.path.startswith("/board/"):
        return url
    query = parse_qs(parsed.query, keep_blank_values=True)
    gallery_id = query.get("id", [""])[0].strip()
    if not gallery_id:
        return url
    if "/board/view" in parsed.path:
        post_number = query.get("no", [""])[0].strip()
        if not post_number:
            return url
        path = f"/board/{quote(gallery_id, safe='')}/{quote(post_number, safe='')}"
        query.pop("id", None)
        query.pop("no", None)
    else:
        path = f"/board/{quote(gallery_id, safe='')}"
        query.pop("id", None)
        query.pop("list_num", None)
    return urlunparse(("https", "m.dcinside.com", path, "", urlencode(query, doseq=True), ""))


def fetch_text_mobile(url: str, timeout: float = 20.0) -> str:
    """Fetch the mobile public page, which is a separate DCInside delivery path."""
    mobile_url = mobile_url_for(url)
    request = Request(
        mobile_url,
        headers={
            "User-Agent": MOBILE_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Referer": "https://m.dcinside.com/",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
        if not payload:
            raise SourceResponseError(
                mobile_url,
                status=getattr(response, "status", None),
                content_length=response.headers.get("Content-Length"),
                server=response.headers.get("Server"),
                transport="mobile-http",
            )
    return _decode_http_payload(payload, response.headers.get("Content-Encoding"), encoding)


def _decode_http_payload(payload: bytes, content_encoding: str | None, encoding: str) -> str:
    """Decode the compression explicitly; urllib does not transparently unzip bodies."""
    compression = (content_encoding or "").lower().strip()
    if compression == "gzip":
        payload = gzip.decompress(payload)
    elif compression == "deflate":
        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            payload = zlib.decompress(payload, -zlib.MAX_WBITS)
    return payload.decode(encoding, errors="replace")


def fetch_text_browser(url: str, timeout: float = 30.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    """Fetch one public page through a normal browser page."""
    return get_default_transport(user_agent=user_agent).fetch(url, timeout)


def fetch_text_auto(url: str, timeout: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    """Try desktop HTTP, then mobile HTTP, then the browser transport."""
    try:
        return fetch_text(url, timeout, user_agent)
    except (SourceResponseError, HTTPError) as http_error:
        if isinstance(http_error, SourceResponseError) and http_error.content_length in (None, "", "0"):
            try:
                return fetch_text(url, timeout, user_agent)
            except (SourceResponseError, HTTPError):
                pass
        mobile_error: Exception | None = None
        try:
            mobile_body = fetch_text_mobile(url, max(timeout, 20.0))
            if _has_expected_source_markup(url, mobile_body):
                return mobile_body
            mobile_error = SourceResponseError(
                mobile_url_for(url),
                status=200,
                content_length=str(len(mobile_body)),
                server="unknown",
                transport="mobile-http",
                fallback_error="response-shape-unrecognized",
            )
        except (SourceResponseError, HTTPError, OSError) as error:
            mobile_error = error
        try:
            return fetch_text_browser(url, max(timeout, 30.0), user_agent)
        except BrowserTransportError as browser_error:
            fallback = str(browser_error)
            if mobile_error is not None:
                fallback = f"mobile={mobile_error}; browser={fallback}"
            if isinstance(http_error, SourceResponseError):
                raise SourceResponseError(
                    url,
                    status=http_error.status,
                    content_length=http_error.content_length,
                    server=http_error.server,
                    transport="http+playwright",
                    fallback_error=fallback,
                ) from browser_error
            raise SourceResponseError(
                url,
                status=getattr(http_error, "code", None),
                content_length=None,
                server=None,
                transport="http+playwright",
                fallback_error=fallback,
            ) from browser_error


def _has_expected_source_markup(url: str, body: str) -> bool:
    """Reject non-empty challenge/error documents from a transport fallback."""
    if "dcinside.com" not in urlparse(url).netloc.lower():
        return True
    if not body.lstrip().startswith(("<!DOCTYPE", "<html", "<HTML")):
        return False
    parsed = urlparse(url)
    is_post = "/board/view" in parsed.path or bool(parse_qs(parsed.query).get("no")) or bool(re.search(r"/board/[^/]+/\d+", parsed.path))
    markers = (
        ("title_subject", "write_div", "articleBody", "thum-txtin")
        if is_post
        else ("gall_subject", "gall_tit", "gall-detail-lnktb", "/board/view/")
    )
    return any(marker in body for marker in markers)


def fetch_comment_text_auto(
    post_url: str,
    gallery_id: str,
    post_number: str,
    ci_t: str,
    page: int = 1,
    timeout: float = 15.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    try:
        body = fetch_comment_text(post_url, gallery_id, post_number, ci_t, page, timeout, user_agent)
        if body.strip():
            return body
    except (HTTPError, OSError):
        pass
    return get_default_transport(user_agent=user_agent).fetch_comment(
        post_url,
        gallery_id,
        post_number,
        ci_t,
        page,
        max(timeout, 30.0),
    )


def fetch_comment_text(
    post_url: str,
    gallery_id: str,
    post_number: str,
    ci_t: str,
    page: int = 1,
    timeout: float = 15.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    """Read one public comment page through DCInside's read-only endpoint."""
    payload = urlencode({"ci_t": ci_t, "id": gallery_id, "no": post_number, "comment_page": str(page)}).encode()
    request = Request(
        "https://gall.dcinside.com/comment/view",
        data=payload,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": post_url,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return body.decode(encoding, errors="replace")


def extract_comment_token(html: str) -> str:
    match = re.search(r'<input[^>]+name=["\']ci_t["\'][^>]+value=["\']([^"\']+)', html, re.I)
    return match.group(1) if match else ""


def infer_default_shipping(body: str) -> bool | None:
    if re.search(r"택포\s*표기\s*없으면|배송비\s*(?:미포함|별도)|택배비\s*(?:미포함|별도)", body):
        return False
    if re.search(r"(?:전체|전부|모두).{0,15}(?:택포|배송비\s*포함|택배비\s*포함)", body, re.S):
        return True
    return None


def parse_shipping(line: str, default_shipping: bool | None) -> bool | None:
    if re.search(r"택포|배송비\s*포함|택배비\s*포함", line):
        return True
    if re.search(r"배송비\s*(?:미포함|별도)|택배비\s*(?:미포함|별도)", line):
        return False
    return default_shipping


def parse_shipping_price(body: str) -> int | None:
    matches = re.findall(
        r"(?:반택|편택|택배)(?:비)?[^\n()]*\((\d+(?:[.,]\d+)?)(만원|만|천|원)?\)",
        body,
    )
    if len(matches) != 1:
        return None
    raw_value, unit = matches[0]
    if unit == "원":
        return round(float(raw_value.replace(",", "")))
    if unit in {"만원", "만"}:
        return round(float(raw_value.replace(",", ".")) * 10_000)
    return round(float(raw_value.replace(",", ".")) * (1_000 if unit == "천" else 1_000))


def parse_sale_line(
    line: str,
    default_shipping: bool | None,
    shipping_price: int | None,
) -> dict[str, Any] | None:
    line = normalize_space(line).strip("-·:")
    if not line or line.lower().startswith(("http", "- dc", "sadao")):
        return None
    match = PRICE_RE.search(line)
    if not match:
        return None

    label = normalize_space(line[: match.start()].strip("-·:"))
    if not label or re.search(r"^(?:배송|택배|반택|편택|가격|합계|총액)\b", label):
        return None
    quantity_match = QUANTITY_RE.search(label)
    quantity = int(quantity_match.group("quantity")) if quantity_match else 1
    is_bundle = bool(re.search(r"일괄|세트|묶음|전체", label))
    item_label = QUANTITY_RE.sub("", label)
    item_label = re.sub(r"\b(?:일괄|세트|묶음|전체)\b", "", item_label)
    item_label = re.sub(r"\b(?:택포|배송비\s*포함|택배비\s*포함)\b", "", item_label)
    item_label = normalize_space(item_label).strip("-·:")
    rarity_match = RARITY_RE.search(item_label)
    rarity = normalize_space(rarity_match.group("rarity")) if rarity_match else ""
    card_name = item_label[: rarity_match.start()].strip(" -·") if rarity_match else item_label
    card_name = card_name or item_label

    raw_price = match.group("value").replace(",", ".")
    unit = match.group("unit") or ""
    if unit == "원":
        price_krw = round(float(match.group("value").replace(",", "")))
        price_unit = "원 명시"
    else:
        price_krw = round(float(raw_price) * 10_000)
        price_unit = "만원 단위 추정"

    reasons: list[str] = []
    if not unit:
        reasons.append("가격 단위 추정")
    if is_bundle:
        reasons.append("일괄·세트 가격")
    if MULTI_CARD_RE.search(item_label):
        reasons.append("복수 카드 가격")
    if AMBIGUOUS_QUANTITY_RE.search(label):
        reasons.append("수량 확인 필요")
    if "이미지" in item_label and not card_name:
        reasons.append("이미지 전용 카드명")
    included = parse_shipping(line, default_shipping)
    if included is None:
        reasons.append("배송비 포함 여부 미확정")
    if not card_name or len(card_name) < 2:
        reasons.append("카드명 확인 필요")
    return {
        "card_name": card_name,
        "rarity": rarity,
        "raw_price": raw_price,
        "price_krw": price_krw,
        "price_unit": price_unit,
        "quantity": quantity,
        "shipping_included": included,
        "shipping_price_krw": shipping_price if included is False else None,
        "review_status": "needs_review" if reasons else "parsed",
        "review_reason": ", ".join(dict.fromkeys(reasons)),
        "raw_line": line,
    }


def extract_post(html: str, url: str, gallery_id: str, subject: str = "") -> list[ExtractedRow]:
    document, _ = parse_html(html, url)
    body = document["body"]
    default_shipping = infer_default_shipping(body)
    shipping_price = parse_shipping_price(body)
    intent = classify_listing(document["title"], body, subject)
    rows: list[ExtractedRow] = []
    for line in body.splitlines():
        parsed = parse_sale_line(line, default_shipping, shipping_price)
        if parsed is None:
            continue
        rows.append(ExtractedRow(
            gallery_id=gallery_id,
            post_title=document["title"],
            post_url=document["url"],
            posted_at=document["posted_at"],
            listing_type=intent.listing_type,
            intent_confidence=intent.confidence,
            price_type=intent.price_type,
            author_name=document.get("author_name", ""),
            author_type=document.get("author_type", "unknown"),
            **parsed,
        ))
    if not rows and intent.listing_type == "buy":
        card_name = _buy_card_label(document["title"], body)
        if card_name:
            rows.append(ExtractedRow(
                gallery_id=gallery_id,
                post_title=document["title"],
                post_url=document["url"],
                posted_at=document["posted_at"],
                card_name=card_name,
                rarity="",
                raw_price="",
                price_krw=0,
                price_unit="미기재",
                quantity=_buy_quantity(body),
                shipping_included=None,
                shipping_price_krw=None,
                review_status="needs_review",
                review_reason="희망가 미기재",
                raw_line=normalize_space(document["title"] or body.splitlines()[0] if body.splitlines() else body),
                listing_type="buy",
                intent_confidence=intent.confidence,
                price_type="wanted",
                author_name=document.get("author_name", ""),
                author_type=document.get("author_type", "unknown"),
            ))
    if not rows and body:
        print(f"warning: no price line parsed from {document['url']}; review image-only post", file=sys.stderr)
    return rows


def _buy_card_label(title: str, body: str) -> str:
    value = normalize_space(title or body.splitlines()[0] if body.splitlines() else body)
    value = re.sub(r"(?:구합니다|구해요|삽니다|구매합니다|찾습니다|구함|구매)", "", value)
    value = re.sub(r"^(?:구매|구함|카드)", "", value)
    return normalize_space(value).strip(" -·:[]()")


def _buy_quantity(body: str) -> int:
    match = QUANTITY_RE.search(body)
    return int(match.group("quantity")) if match else 1


def build_list_url(gallery_id: str, page: int, gallery_url: str = "") -> str:
    """Build a paginated list URL while preserving the configured gallery host/path."""
    fallback = "https://gall.dcinside.com/mgallery/board/lists"
    parsed = urlparse(gallery_url.strip()) if gallery_url.strip() else urlparse(fallback)
    if not parsed.scheme or not parsed.netloc:
        parsed = urlparse(fallback)
    path = parsed.path if parsed.path.rstrip("/").endswith("/board/lists") else "/mgallery/board/lists"
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.update({"id": [gallery_id], "page": [str(page)], "list_num": ["50"]})
    return parsed._replace(path=path, query=urlencode(query, doseq=True), fragment="").geturl()


def extract_gallery(
    gallery_id: str,
    subject: str,
    pages: int,
    max_posts: int,
    delay: float,
    timeout: float = 15.0,
    user_agent: str = DEFAULT_USER_AGENT,
    fetcher: Callable[[str], str] | None = None,
    gallery_url: str = "",
) -> list[ExtractedRow]:
    if not 1 <= pages <= 20:
        raise ValueError("pages must be between 1 and 20")
    if not 1 <= max_posts <= 200:
        raise ValueError("max_posts must be between 1 and 200")
    if delay < 0:
        raise ValueError("delay must be zero or greater")
    read = fetcher or (lambda url: fetch_text_auto(url, timeout, user_agent))
    rows: list[ExtractedRow] = []
    seen_urls: set[str] = set()
    fetched_posts = 0
    for page in range(1, pages + 1):
        list_url = build_list_url(gallery_id, page, gallery_url)
        parser = DCInsideHTMLParser()
        parser.feed(read(list_url))
        candidates = [
            urljoin(list_url, item["href"])
            for item in parser.list_rows
            if normalize_space(item.get("subject", "")) == subject and item.get("href")
        ]
        for post_url in candidates:
            if post_url in seen_urls or fetched_posts >= max_posts:
                continue
            seen_urls.add(post_url)
            fetched_posts += 1
            rows.extend(extract_post(read(post_url), post_url, gallery_id, subject))
            if delay > 0:
                time.sleep(delay)
        if fetched_posts >= max_posts:
            break
        if delay > 0:
            time.sleep(delay)
    return rows


def write_output(rows: list[ExtractedRow], output: Path | None, output_format: str) -> None:
    payload = [to_public_row(row) for row in rows]
    if output_format == "csv":
        target = output.open("w", encoding="utf-8-sig", newline="") if output else sys.stdout
        close_target = output is not None
        try:
            writer = csv.DictWriter(target, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(payload)
        finally:
            if close_target:
                target.close()
        return
    text = json.dumps({"rows": payload}, ensure_ascii=False, indent=2)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract bounded DCInside card-sale rows")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--post-url", help="extract one already-known post")
    source.add_argument("--gallery-id", help="crawl sale posts from a minor gallery")
    parser.add_argument("--html-file", type=Path, help="parse a saved HTML file with --post-url")
    parser.add_argument("--subject", default="판매")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--max-posts", type=int, default=20)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    return parser


def run_cli(args: argparse.Namespace) -> int:
    if args.max_posts < 1 or args.max_posts > 200:
        raise ValueError("--max-posts must be between 1 and 200")
    if args.pages < 1 or args.pages > 20:
        raise ValueError("--pages must be between 1 and 20")
    if args.delay < 0:
        raise ValueError("--delay must be zero or greater")
    if args.post_url:
        html = args.html_file.read_text(encoding="utf-8", errors="replace") if args.html_file else fetch_text(args.post_url, args.timeout, args.user_agent)
        gallery_id = parse_qs(urlparse(args.post_url).query).get("id", [""])[0]
        rows = extract_post(html, args.post_url, gallery_id)
    else:
        rows = extract_gallery(args.gallery_id, args.subject, args.pages, args.max_posts, args.delay, args.timeout, args.user_agent)
    write_output(rows, args.output, args.format)
    print(f"extracted {len(rows)} rows", file=sys.stderr)
    return 0
