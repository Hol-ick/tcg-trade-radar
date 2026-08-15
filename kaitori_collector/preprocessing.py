"""Conservative quality classification for noisy public trade posts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import AnalysisStatus, CardMatchStatus, PostStatus, PriceOrigin, PriceScope, PriceStatus


COMPLETED_SIGNALS = (
    "거래완료", "판매완료", "구매완료", "거래 완료", "판매 완료", "구매 완료",
    "판매완", "판완", "완판", "팔렸", "팔림", "끝났", "마감", "거래 끝",
)
RESERVED_SIGNALS = ("예약중", "예약 중", "예약", "찜", "홀딩")
PRICE_REMOVED_SIGNALS = (
    "가격삭제", "가격 삭제", "가격지움", "가격 지움", "가격 내림",
    "가격은 삭제", "거래완료라 가격",
)
BUNDLE_SIGNALS = ("일괄", "세트", "전부", "구성", "소스", "덱")
ARTIFACT_CARD_RE = re.compile(
    r"(?:https?://|javascript\s*:|<\/?script\b|loadscript\b|adsbygoogle|googlesyndication|"
    r"(?:window|document)\s*[.[]|queryselector\s*\(|appendchild\s*\(|\b(?:var|const|let)\s+\w+\s*=|"
    r"function\s*\(|DOM\s*삽입|스크립트|광고\s*삽입)",
    re.IGNORECASE,
)
NON_CARD_LABEL_RE = re.compile(r"^(?:(?:\d+\s*)?(?:장|매|개|통)(?:분)?|한\s*장|(?:장|매|개|통)\s*당|준등포|준등기|등포|등기|택포|반택포|편택포|배송|배송비|가격|합계|총액|일괄\s*(?:시|판매|구매)?|구매|판매|교환|\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?)+|(?:준등포|준등기|등포|등기|택포|배송|배송비|가격|합계|총액|일괄)\s*\d+(?:[.,]\d+)?\s*(?:원|만원|만|천)?)$", re.IGNORECASE)


@dataclass(frozen=True)
class PostQuality:
    status: PostStatus
    image_count: int
    body_characters: int
    reason: str


def classify_post(title: str, body: str, *, image_count: int = 0, row_count: int = 0) -> PostQuality:
    """Classify a post without guessing that an ambiguous post is active."""
    text = f"{title} {body}".casefold()
    if any(signal.casefold() in text for signal in PRICE_REMOVED_SIGNALS):
        return PostQuality("price_removed", image_count, len(body.strip()), "가격 삭제 표현 감지")
    if any(signal.casefold() in text for signal in COMPLETED_SIGNALS):
        return PostQuality("completed", image_count, len(body.strip()), "거래 완료 표현 감지")
    if any(signal.casefold() in text for signal in RESERVED_SIGNALS):
        return PostQuality("reserved", image_count, len(body.strip()), "예약·홀딩 표현 감지")
    if image_count > 0 and len(body.strip()) < 80 and row_count == 0:
        return PostQuality("image_only", image_count, len(body.strip()), "본문보다 이미지에 거래 정보가 있을 가능성")
    return PostQuality("active", image_count, len(body.strip()), "활성 거래글로 판정")


def classify_price(*, raw_price: str, price_unit: str, quantity: int, raw_line: str, post_status: PostStatus) -> tuple[PriceStatus, PriceScope, PriceOrigin]:
    """Return explicit price quality without converting a missing value to zero."""
    if not raw_price.strip():
        return ("removed" if post_status in {"completed", "price_removed"} else "missing", "unknown", "unknown")
    status: PriceStatus = "exact" if price_unit == "원 명시" else "estimated" if price_unit else "unknown"
    line = raw_line.casefold()
    if any(signal.casefold() in line for signal in BUNDLE_SIGNALS) or re.search(r"(?<!\d),(?!\d)|[+/&]|\s(?:및|외)\s", raw_line):
        scope: PriceScope = "bundle"
    elif quantity > 1 and "장당" not in line:
        scope = "per_quantity"
    else:
        scope = "per_card"
    return status, scope, "text"


def analysis_status(*, post_status: PostStatus, listing_type: str, card_name: str, price_status: PriceStatus, price_scope: PriceScope) -> AnalysisStatus:
    if post_status in {"completed", "reserved", "price_removed", "image_only"}:
        return "context_only"
    if is_likely_artifact(card_name):
        return "excluded"
    if listing_type not in {"sell", "buy", "trade"} or len(card_name.strip()) < 2:
        return "needs_review"
    if price_scope != "per_card" or price_status != "exact":
        return "needs_review"
    return "usable"


def append_quality_reason(reason: str, *, post_status: PostStatus, price_status: PriceStatus, price_scope: PriceScope, analysis: AnalysisStatus) -> str:
    reasons = [part.strip() for part in reason.split(",") if part.strip()]
    additions = {
        "completed": "거래 완료 글 · 현재 매물 제외",
        "reserved": "예약·홀딩 글 · 현재 매물 제외",
        "price_removed": "가격 삭제 또는 거래 완료 후 가격 없음",
        "image_only": "이미지 전용 글 · 이미지 확인 필요",
    }
    if post_status in additions:
        reasons.append(additions[post_status])
    if price_status == "missing" and not any("미기재" in reason for reason in reasons):
        reasons.append("가격 미기재")
    elif price_status == "removed":
        reasons.append("가격 삭제 추정")
    if price_scope == "per_quantity":
        reasons.append("복수 수량 총액 · 카드 1장 가격 아님")
    elif price_scope == "bundle":
        reasons.append("묶음·세트 총액 · 개별 카드 가격 아님")
    if analysis == "excluded":
        reasons.append("스크립트·광고 문구로 추정되는 오염 행")
    if analysis == "context_only" and post_status == "active":
        reasons.append("시장 통계 참고용")
    return ", ".join(dict.fromkeys(reasons))


def fallback_card_match(card_name: str, *, image_only: bool = False) -> CardMatchStatus:
    if image_only:
        return "image_review"
    return "candidate" if len(card_name.strip()) >= 2 else "unmatched"


def is_likely_artifact(value: str) -> bool:
    """Detect HTML/advertising fragments that were parsed as a card label."""
    candidate = (value or "").strip()
    return bool(ARTIFACT_CARD_RE.search(candidate) or NON_CARD_LABEL_RE.fullmatch(candidate))
