"""Classify public trade posts without auto-confirming ambiguous intent."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


ListingType = Literal["sell", "buy", "trade", "unknown"]

SELL_SIGNALS = ("팝니다", "판매", "처분", "일괄", "택포")
BUY_SIGNALS = ("구합니다", "구해요", "삽니다", "구매", "찾습니다", "구함")
TRADE_SIGNALS = ("교환", "트레이드", "원합니다")


@dataclass(frozen=True)
class IntentResult:
    listing_type: ListingType
    confidence: float
    reason: str
    price_type: Literal["asking", "wanted", "unknown"]


def classify_listing(post_title: str, body: str, subject: str = "") -> IntentResult:
    """Classify a listing using title/body signals and a conservative subject fallback."""
    text = f"{post_title} {body}".casefold()
    matched = {
        "sell": _has_any(text, SELL_SIGNALS),
        "buy": _has_any(text, BUY_SIGNALS),
        "trade": _has_any(text, TRADE_SIGNALS),
    }
    signals = [kind for kind, present in matched.items() if present]
    if len(signals) == 1:
        kind = signals[0]
        subject_hint = _subject_hint(subject)
        confidence = 0.92 if subject_hint == kind else 0.84
        return IntentResult(kind, confidence, f"{kind} 신호: {', '.join(_signal_names(text, kind))}", "wanted" if kind == "buy" else "asking" if kind == "sell" else "unknown")
    if len(signals) > 1:
        return IntentResult("unknown", 0.25, f"거래 의도 신호 충돌: {', '.join(signals)}", "unknown")

    subject_hint = _subject_hint(subject)
    if subject_hint == "sell":
        return IntentResult("sell", 0.68, "판매 말머리만 확인됨", "asking")
    return IntentResult("unknown", 0.0, "거래 의도 신호 없음", "unknown")


def _subject_hint(subject: str) -> ListingType | None:
    value = (subject or "").casefold()
    if "판매" in value:
        return "sell"
    if "구매" in value or "구함" in value:
        return "buy"
    if "거래" in value or "교환" in value:
        return "trade"
    return None


def _has_any(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal.casefold() in text for signal in signals)


def _signal_names(text: str, kind: str) -> list[str]:
    groups = {"sell": SELL_SIGNALS, "buy": BUY_SIGNALS, "trade": TRADE_SIGNALS}
    return [signal for signal in groups[kind] if signal.casefold() in text]
