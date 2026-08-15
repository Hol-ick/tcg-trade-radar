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
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .browser_transport import BrowserTransportError, get_default_transport
from .contracts import ExtractedRow, to_public_row
from .html import DCInsideHTMLParser, normalize_space, parse_html
from .intent import classify_listing
from .preprocessing import analysis_status, append_quality_reason, classify_post, classify_price, fallback_card_match


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


DEFAULT_SHIPPING_PRICE_KRW = 2_000
PRICE_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>만원|만|원)?"
    r"(?:\s*[\(\[]?\s*(?:택포|택배비\s*(?:포함|별도)?|배송비\s*(?:포함|별도)?|포함|별도)\s*[\)\]]?)?"
    r"(?=\s*(?:$|(?:\.(?!\d)|,(?!\d)|[!?)]|에|으로|부터|쯤|정도|판매|팝니다|구매|구합니다|구해|찾|양도|거래|입니다|이에요|예요)))"
)
LEADING_PRICE_RE = re.compile(
    r"^(?:반택포|편택포|택포)\s*(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>만원|만|원)?(?P<label>.*)$"
)
LEADING_PRICE_SUFFIX_RE = re.compile(r"^(?:에|으로|부터|쯤|정도|판매|팝니다|구매|구합니다|구해|찾|양도|거래|입니다|이에요|예요)")
RARITY_ALIASES = {
    "오버프싴": "오버프싴",
    "오버프시크": "오버프싴",
    "오버울레": "오버울레",
    "오버울": "오버울",
    "프리시크": "프싴",
    "프시크": "프싴",
    "프싴": "프싴",
    "영싴": "영싴",
    "영시크": "영싴",
    "쿼싴": "쿼싴",
    "쿼시크": "쿼싴",
    "퍼홀": "퍼홀",
    "홀로": "홀로",
    "시크페레": "시크페레",
    "시크페러렐": "시크페레",
    "시크릿": "시크",
    "시크": "시크",
    "싴": "시크",
    "얼티미트": "얼티",
    "얼티": "얼티",
    "얼": "얼티",
    "울트라": "울레",
    "울레": "울레",
    "울": "울레",
    "슈퍼": "슈레",
    "슈레": "슈레",
    "슈": "슈레",
    "컬레": "컬레",
    "컬": "컬레",
    "레어": "레어",
    "구일": "구일",
}
RARITY_TERMS = tuple(sorted(RARITY_ALIASES, key=len, reverse=True))
RARITY_PATTERN = "|".join(re.escape(term) for term in RARITY_TERMS)
RARITY_RE = re.compile(rf"(?P<rarity>{RARITY_PATTERN})$", re.IGNORECASE)
RARITY_PRICE_RE = re.compile(
    rf"(?P<rarity>{RARITY_PATTERN})"
    r"(?:\s*(?P<quantity>[1-9]\d?)\s*장)?"
    r"(?:\s*장당)?\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)(?P<unit>만원|만|원)?",
    re.IGNORECASE,
)
QUANTITY_RE = re.compile(r"(?P<quantity>\d+)\s*장")
QUANTITY_MARKER_RE = re.compile(r"(?<![\d.])(?P<quantity>\d+)\s*(?:장|매|개)")
ATTACHED_QUANTITY_RE = re.compile(r"^(?P<label>[^\d\s]+?)(?P<quantity>[1-9]\d?)$")
STANDALONE_QUANTITY_RE = re.compile(r"^(?P<label>.+?)\s+(?P<quantity>[1-9]\d?)$")
CARD_CODE_TOKEN_RE = re.compile(r"^[A-Z]{1,6}[-_]?\d{1,4}(?:[-_]?[A-Z0-9]+)?$", re.IGNORECASE)
MULTI_CARD_RE = re.compile(r"[,/+]|&|\s(?:및|외)\s")
AMBIGUOUS_QUANTITY_RE = re.compile(r"여러\s*장|다수|수량\s*(?:불명|미상)|전부")
CSV_FIELDS = [
    "gallery_id", "post_title", "post_url", "posted_at", "card_name", "rarity",
    "raw_price", "price_krw", "price_unit", "quantity", "shipping_included", "author_name", "author_type",
    "shipping_price_krw", "review_status", "review_reason", "raw_line", "post_status",
    "price_status", "price_scope", "price_origin", "analysis_status", "card_match_status",
    "seller_id", "seller_name", "seller_risk_score", "seller_risk_level", "seller_review_status", "is_repost",
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


def is_dcinside_public_url(url: str) -> bool:
    """Return whether a URL belongs to DCInside's public web delivery paths."""
    hostname = (urlparse(url).hostname or "").lower()
    return hostname == "dcinside.com" or hostname.endswith(".dcinside.com")


def fetch_text_auto(url: str, timeout: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    """Fetch a public page with a source-aware, bounded fallback order.

    DCInside currently serves empty desktop responses in some environments while
    its mobile public route remains parseable. Try that route first to avoid
    spending another request on a known-empty desktop response. No login,
    identity rotation, or challenge bypass is involved.
    """
    desktop_error: SourceResponseError | HTTPError | OSError | None = None
    mobile_error: SourceResponseError | HTTPError | OSError | None = None

    def try_mobile() -> str | None:
        nonlocal mobile_error
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
        return None

    def try_desktop() -> str | None:
        nonlocal desktop_error
        try:
            desktop_body = fetch_text(url, timeout, user_agent)
            if _has_expected_source_markup(url, desktop_body):
                return desktop_body
            desktop_error = SourceResponseError(
                url,
                status=200,
                content_length=str(len(desktop_body)),
                server="unknown",
                transport="http",
                fallback_error="response-shape-unrecognized",
            )
        except (SourceResponseError, HTTPError, OSError) as error:
            desktop_error = error
        return None

    # The mobile route is the currently working public delivery path for
    # DCInside. Other sources keep the historical HTTP-first behavior.
    candidate = try_mobile() if is_dcinside_public_url(url) else try_desktop()
    if candidate is not None:
        return candidate
    candidate = try_desktop() if is_dcinside_public_url(url) else try_mobile()
    if candidate is not None:
        return candidate

    source_error = desktop_error or mobile_error
    try:
        browser_body = fetch_text_browser(url, max(timeout, 30.0), user_agent)
        if _has_expected_source_markup(url, browser_body):
            return browser_body
        fallback = "response-shape-unrecognized"
        if mobile_error is not None:
            fallback = f"mobile={mobile_error}; {fallback}"
        raise SourceResponseError(
            url,
            status=200,
            content_length=str(len(browser_body)),
            server="browser",
            transport="http+mobile+browser",
            fallback_error=fallback,
        )
    except BrowserTransportError as browser_error:
        fallback = str(browser_error)
        if mobile_error is not None:
            fallback = f"mobile={mobile_error}; browser={fallback}"
        if isinstance(source_error, SourceResponseError):
            raise SourceResponseError(
                url,
                status=source_error.status,
                content_length=source_error.content_length,
                server=source_error.server,
                transport="http+playwright",
                fallback_error=fallback,
            ) from browser_error
        raise SourceResponseError(
            url,
            status=getattr(source_error, "code", None),
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
    if not is_post:
        parser = DCInsideHTMLParser()
        parser.feed(body)
        return bool(parser.list_rows)
    markers = ("title_subject", "write_div", "articleBody", "thum-txtin")
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


def resolve_shipping_price(included: bool | None, shipping_price: int | None) -> int | None:
    """Return an explicit fee or the normal 2,000 KRW parcel default."""
    if included is None:
        return shipping_price
    return shipping_price if shipping_price is not None else DEFAULT_SHIPPING_PRICE_KRW


def _is_plausible_price_match(line: str, match: re.Match[str]) -> bool:
    """Reject card codes and attached copy counts before accepting a number as a price."""
    if match.group("unit"):
        return True
    value = match.group("value")
    if "." in value or "," in value:
        return True
    start, end = match.span("value")
    previous = line[start - 1] if start else ""
    following = line[end] if end < len(line) else ""
    if previous.casefold() in {"x", "×"} or line[:start].rstrip().casefold().endswith((" x", " ×")):
        return False
    if previous and (previous.isalnum() or "가" <= previous <= "힣" or previous in ".-_"):
        return False
    if following and (following.isalnum() or "가" <= following <= "힣" or following in ".-_"):
        suffix = line[end:].lstrip()
        if not suffix.startswith(("에", "으로", "부터", "쯤", "정도", "판매", "팝니다", "구매", "구합니다", "구해", "찾", "양도", "거래", "입니다", "이에요", "예요")):
            return False
    return True


def _price_matches(line: str) -> list[re.Match[str]]:
    return [match for match in PRICE_RE.finditer(line) if _is_plausible_price_match(line, match)]


def _strip_quantity_markers(label: str) -> tuple[str, int, bool]:
    """Separate explicit quantity markers and compact suffix counts from a label."""
    working = normalize_space(label).strip()
    quantity = 0
    detected = False

    x_match = re.search(r"(?P<name>.*?)\s*[x×]\s*(?P<quantity>[1-9]\d?)\s*$", working, re.IGNORECASE)
    if x_match:
        quantity += int(x_match.group("quantity"))
        working = x_match.group("name").strip()
        detected = True

    marker_matches = list(QUANTITY_MARKER_RE.finditer(working))
    for marker in reversed(marker_matches):
        previous = working[marker.start() - 1] if marker.start() else ""
        if re.search(r"\s", working[marker.start():marker.end()]) and previous and (previous.isalnum() or "가" <= previous <= "힣"):
            continue
        quantity += int(marker.group("quantity"))
        working = f"{working[:marker.start()]} {working[marker.end():]}"
        detected = True

    tokens = working.split()
    for index, token in enumerate(tokens):
        attached = ATTACHED_QUANTITY_RE.fullmatch(token)
        if not attached or CARD_CODE_TOKEN_RE.fullmatch(token) or any(mark in token for mark in "()[]{}"):
            continue
        tokens[index] = attached.group("label")
        quantity += int(attached.group("quantity"))
        detected = True

    return normalize_space(" ".join(tokens)).strip("-·:"), max(1, quantity), detected


def _strip_trailing_quantity(label: str) -> tuple[str, int, bool]:
    match = STANDALONE_QUANTITY_RE.fullmatch(normalize_space(label).strip())
    if not match:
        return label, 1, False
    if match.group("label").rstrip().endswith((".", "-", "_")):
        return label, 1, False
    return match.group("label").strip(), int(match.group("quantity")), True


def _card_fields(item_label: str) -> tuple[str, str]:
    rarity_match = RARITY_RE.search(item_label)
    rarity = normalize_rarity(rarity_match.group("rarity")) if rarity_match else ""
    card_name = item_label[: rarity_match.start()].strip(" -·") if rarity_match else item_label
    return card_name or item_label, rarity


def normalize_rarity(value: str) -> str:
    """Collapse spelling/count variants into one filterable rarity label."""
    compact = re.sub(r"\s+", "", normalize_space(value)).strip("-·:[]()")
    compact = re.sub(r"^\d+(?:[.,]\d+)?", "", compact)
    return RARITY_ALIASES.get(compact.casefold(), compact)


def _rarity_header(line: str) -> str:
    """Return a section rarity such as `오버프싴` when a line is only a heading."""
    value = normalize_space(line).strip("-·:[]()")
    value = re.sub(r"^(?:그\s*외|기타|나머지)\s+", "", value)
    return normalize_rarity(value) if normalize_rarity(value) in RARITY_ALIASES.values() else ""


def _is_rarity_price_match(line: str, match: re.Match[str]) -> bool:
    """Reject attached counts such as `2프싴` when they are not prices."""
    start = match.start("rarity")
    previous = line[start - 1] if start else ""
    if previous and (previous.isalnum() or "가" <= previous <= "힣"):
        return False
    end = match.end()
    following = line[end:]
    if following and not following[0].isspace() and following[0] not in ".,!?)]":
        return False
    return True


def _price_value(raw_value: str, unit: str) -> tuple[int, str, str]:
    """Convert a text amount using the project's existing Korean price convention."""
    if unit == "원":
        return round(float(raw_value.replace(",", ""))), "원 명시", raw_value
    normalized = raw_value.replace(",", ".")
    if "." in raw_value or ("," in raw_value and len(raw_value.rsplit(",", 1)[-1]) <= 2):
        return round(float(normalized) * 10_000), "만원 단위 추정", normalized
    numeric_price = int(raw_value.replace(",", ""))
    if numeric_price >= 1_000:
        return numeric_price, "원 단위 추정", raw_value
    return numeric_price * 10_000, "만원 단위 추정", raw_value


def _parse_rarity_price_variants(
    line: str,
    default_shipping: bool | None,
    shipping_price: int | None,
) -> list[dict[str, Any]]:
    """Split `카드 슈레 0.3 컬레 0.5` into one observation per rarity price."""
    matches = [match for match in RARITY_PRICE_RE.finditer(line) if _is_rarity_price_match(line, match)]
    if len(matches) < 2:
        return []
    base_label = normalize_space(line[: matches[0].start()].strip("-·:"))
    if not base_label:
        return []
    base_label, base_quantity, _ = _strip_quantity_markers(base_label)
    base_label = re.sub(r"\b(?:일괄|세트|묶음|전체)\b", "", base_label)
    base_label = normalize_space(base_label).strip("-·:")
    card_name, _ = _card_fields(base_label)
    if not card_name or len(card_name) < 2:
        return []
    included = parse_shipping(line, default_shipping)
    variants: list[dict[str, Any]] = []
    for match in matches:
        raw_value = match.group("value")
        unit = match.group("unit") or ""
        price_krw, price_unit, raw_price = _price_value(raw_value, unit)
        quantity = int(match.group("quantity") or base_quantity or 1)
        price_scope = "per_card" if match.group("quantity") or "장당" in match.group(0) else "per_quantity" if quantity > 1 else "per_card"
        reasons = ["레어도별 가격 분리"]
        if match.group("quantity"):
            reasons.append("수량 표기 감지")
        if not unit:
            reasons.append("가격 단위 추정")
        if included is None:
            reasons.append("배송비 포함 여부 미확정")
        variants.append({
            "card_name": card_name,
            "rarity": normalize_rarity(match.group("rarity")),
            "raw_price": raw_price,
            "price_krw": price_krw,
            "price_unit": price_unit,
            "quantity": quantity,
            "shipping_included": included,
            "shipping_price_krw": resolve_shipping_price(included, shipping_price),
            "review_status": "needs_review",
            "review_reason": ", ".join(reasons),
            "raw_line": line,
            "price_status": "exact" if unit == "원" else "estimated",
            "price_scope": price_scope,
            "price_origin": "text",
        })
    return variants


def _missing_price_row(
    *,
    parse_line: str,
    raw_line: str,
    label: str,
    default_shipping: bool | None,
    shipping_price: int | None,
    allow_standalone_quantity: bool = False,
) -> dict[str, Any] | None:
    item_label, quantity, detected = _strip_quantity_markers(label)
    if allow_standalone_quantity and not detected:
        item_label, standalone_quantity, detected = _strip_trailing_quantity(item_label)
        if detected:
            quantity = standalone_quantity
    if not detected:
        return None
    if not item_label or re.search(r"^(?:택포|반택포|편택포|배송|택배|반택|편택|가격|합계|총액)\b", item_label):
        return None
    item_label = re.sub(r"\b(?:일괄|세트|묶음|전체)\b", "", item_label)
    item_label = re.sub(r"\b(?:택포|배송비\s*포함|택배비\s*포함)\b", "", item_label)
    item_label = normalize_space(item_label).strip("-·:")
    if not item_label:
        return None
    card_name, rarity = _card_fields(item_label)
    included = parse_shipping(parse_line, default_shipping)
    return {
        "card_name": card_name,
        "rarity": rarity,
        "raw_price": "",
        "price_krw": 0,
        "price_unit": "미기재",
        "quantity": quantity,
        "shipping_included": included,
        "shipping_price_krw": resolve_shipping_price(included, shipping_price),
        "review_status": "needs_review",
        "review_reason": "수량 표기 감지 · 가격 미기재",
        "raw_line": raw_line,
        "price_status": "missing",
        "price_scope": "unknown",
        "price_origin": "unknown",
    }


def _looks_like_inventory_body(title: str, body: str) -> bool:
    """Enable conservative spaced-count handling for deck-list style posts."""
    if "일괄" in title:
        return True
    quantity_lines = 0
    for line in body.splitlines():
        if re.search(r"[x×]\s*[1-9]\d?\s*$", line, re.IGNORECASE) or re.search(r"[^\d\s][1-9]\d?\s*$", line):
            quantity_lines += 1
    return quantity_lines >= 2


def parse_sale_line_variants(
    line: str,
    default_shipping: bool | None,
    shipping_price: int | None,
    *,
    quantity_context: bool = False,
) -> list[dict[str, Any]]:
    variants = _parse_rarity_price_variants(line, default_shipping, shipping_price)
    if variants:
        return variants
    parsed = _parse_sale_line_single(line, default_shipping, shipping_price, quantity_context=quantity_context)
    return [parsed] if parsed is not None else []


def parse_sale_line(
    line: str,
    default_shipping: bool | None,
    shipping_price: int | None,
    *,
    quantity_context: bool = False,
) -> dict[str, Any] | None:
    """Keep the legacy single-row interface for callers outside post extraction."""
    variants = parse_sale_line_variants(line, default_shipping, shipping_price, quantity_context=quantity_context)
    return variants[-1] if variants else None


def _parse_sale_line_single(
    line: str,
    default_shipping: bool | None,
    shipping_price: int | None,
    *,
    quantity_context: bool = False,
) -> dict[str, Any] | None:
    line = normalize_space(line).strip("-·:")
    raw_line = line
    parse_line = re.sub(r"\s*(?:거래완료|판매완료|구매완료|판매완|판완|완판|거래\s*완료|판매\s*완료|구매\s*완료|예약중|예약\s*중)\s*$", "", line).strip()
    if not parse_line or parse_line.lower().startswith(("http", "- dc", "sadao")):
        return None
    leading_match = LEADING_PRICE_RE.match(parse_line)
    if leading_match and LEADING_PRICE_SUFFIX_RE.match(leading_match.group("label").lstrip()):
        leading_match = None
    matches = [] if leading_match else _price_matches(parse_line)
    match = None if leading_match else matches[-1] if matches else None
    if not leading_match and match and quantity_context and not match.group("unit") and "." not in match.group("value") and "," not in match.group("value"):
        if int(match.group("value")) <= 20 and len(matches) == 1:
            match = None
    if not leading_match and not match:
        return _missing_price_row(
            parse_line=parse_line,
            raw_line=raw_line,
            label=parse_line,
            default_shipping=default_shipping,
            shipping_price=shipping_price,
            allow_standalone_quantity=quantity_context,
        )

    if leading_match:
        label = normalize_space(leading_match.group("label").strip("-·:"))
        raw_value_text = leading_match.group("value")
        unit = leading_match.group("unit") or ""
    else:
        assert match is not None
        label = normalize_space(parse_line[: match.start()].strip("-·:"))
        raw_value_text = match.group("value")
        unit = match.group("unit") or ""
    if not label or re.search(r"^(?:택포|반택포|편택포|배송|택배|반택|편택|가격|합계|총액)\b", label):
        return None
    label, standalone_quantity, standalone_detected = _strip_trailing_quantity(label)
    item_label, quantity, marker_detected = _strip_quantity_markers(label)
    if standalone_detected:
        quantity = standalone_quantity + (quantity if marker_detected else 0)
        marker_detected = True
    is_bundle = bool(re.search(r"일괄|세트|묶음|전체", label))
    item_label = re.sub(r"\b(?:일괄|세트|묶음|전체)\b", "", item_label)
    item_label = re.sub(r"\b(?:택포|배송비\s*포함|택배비\s*포함)\b", "", item_label)
    item_label = normalize_space(item_label).strip("-·:")
    card_name, rarity = _card_fields(item_label)

    raw_price = raw_value_text.replace(",", ".")
    if unit == "원":
        price_krw = round(float(raw_value_text.replace(",", "")))
        price_unit = "원 명시"
    elif "." in raw_value_text or ("," in raw_value_text and len(raw_value_text.rsplit(",", 1)[-1]) <= 2):
        price_krw = round(float(raw_price) * 10_000)
        price_unit = "만원 단위 추정"
    else:
        numeric_price = int(raw_value_text.replace(",", ""))
        if numeric_price >= 1_000:
            price_krw = numeric_price
            price_unit = "원 단위 추정"
        else:
            price_krw = numeric_price * 10_000
            price_unit = "만원 단위 추정"

    reasons: list[str] = []
    if not unit:
        reasons.append("가격 단위 추정")
    if marker_detected:
        reasons.append("수량 표기 감지")
    if is_bundle:
        reasons.append("일괄·세트 가격")
    if MULTI_CARD_RE.search(item_label):
        reasons.append("복수 카드 가격")
    if AMBIGUOUS_QUANTITY_RE.search(label):
        reasons.append("수량 확인 필요")
    if "이미지" in item_label and not card_name:
        reasons.append("이미지 전용 카드명")
    included = parse_shipping(parse_line, default_shipping)
    if included is None:
        reasons.append("배송비 포함 여부 미확정")
    if not card_name or len(card_name) < 2:
        reasons.append("카드명 확인 필요")
    price_status = "exact" if unit == "원" else "estimated"
    price_scope = "bundle" if is_bundle or MULTI_CARD_RE.search(item_label) else "per_quantity" if quantity > 1 and "장당" not in line else "per_card"
    return {
        "card_name": card_name,
        "rarity": rarity,
        "raw_price": raw_price,
        "price_krw": price_krw,
        "price_unit": price_unit,
        "quantity": quantity,
        "shipping_included": included,
        "shipping_price_krw": resolve_shipping_price(included, shipping_price),
        "review_status": "needs_review" if reasons else "parsed",
        "review_reason": ", ".join(dict.fromkeys(reasons)),
        "raw_line": raw_line,
        "price_status": price_status,
        "price_scope": price_scope,
        "price_origin": "text",
    }


def extract_post(html: str, url: str, gallery_id: str, subject: str = "") -> list[ExtractedRow]:
    document, _ = parse_html(html, url)
    body = document["body"]
    default_shipping = infer_default_shipping(body)
    shipping_price = parse_shipping_price(body)
    intent = classify_listing(document["title"], body, subject)
    quantity_context = _looks_like_inventory_body(document["title"], body)
    rows: list[ExtractedRow] = []
    section_rarity = ""
    for line in body.splitlines():
        header_rarity = _rarity_header(line)
        if header_rarity:
            section_rarity = header_rarity
            continue
        parsed_variants = parse_sale_line_variants(line, default_shipping, shipping_price, quantity_context=quantity_context)
        for parsed in parsed_variants:
            if section_rarity and not parsed["rarity"]:
                parsed["rarity"] = section_rarity
                parsed["review_reason"] = ", ".join(filter(None, [parsed["review_reason"], "레어도 구간 상속"]))
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
                price_status="missing",
                price_scope="unknown",
                price_origin="unknown",
                analysis_status="needs_review",
                card_match_status=fallback_card_match(card_name),
            ))
    post_quality = classify_post(
        document.get("title", ""),
        body,
        image_count=int(document.get("image_count") or 0),
        row_count=len(rows),
    )
    normalized_rows: list[ExtractedRow] = []
    for row in rows:
        price_status, price_scope, price_origin = classify_price(
            raw_price=row.raw_price,
            price_unit=row.price_unit,
            quantity=row.quantity,
            raw_line=row.raw_line,
            post_status=post_quality.status,
        )
        quality = analysis_status(
            post_status=post_quality.status,
            listing_type=row.listing_type,
            card_name=row.card_name,
            price_status=price_status,
            price_scope=price_scope,
        )
        normalized_rows.append(replace(
            row,
            post_status=post_quality.status,
            price_status=price_status,
            price_scope=price_scope,
            price_origin=price_origin,
            analysis_status=quality,
            card_match_status=fallback_card_match(row.card_name),
            review_status="needs_review" if quality != "usable" or row.review_status == "needs_review" else row.review_status,
            review_reason=append_quality_reason(
                row.review_reason,
                post_status=post_quality.status,
                price_status=price_status,
                price_scope=price_scope,
                analysis=quality,
            ),
        ))
    rows = normalized_rows
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
