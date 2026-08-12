"""Conservative, analysis-only normalization for user-written card labels."""
from __future__ import annotations

import re


_TRADE_WORDS = re.compile(
    r"(?:\b(?:sell|buy|trade|wanted|selling|buying)\b|판매합니다|판매|팝니다|팜|삽니다|구매합니다|구매|구합니다|구해요|구함|찾습니다|찾아요|찾음|교환합니다|교환|파는\s*사람|사는\s*사람)",
    re.IGNORECASE,
)
_QUANTITY = re.compile(r"(?<![A-Za-z가-힣])\d+\s*(?:장|매|개|통|세트)(?:분)?\b", re.IGNORECASE)
_PRICE = re.compile(r"(?<![A-Za-z가-힣0-9.-])\d[\d,]*(?:\.\d+)?\s*(?:원|만원|만)?(?=$|[^A-Za-z가-힣0-9])", re.IGNORECASE)
_SEPARATORS = re.compile(r"[\[\](){}<>|/,:;]+")
_SPACES = re.compile(r"\s+")


def normalize_listing_card_label(raw_label: str, listing_type: str = "") -> str:
    """Return a conservative key for grouping sell and buy labels."""
    del listing_type  # Reserved for future type-specific rules.
    value = str(raw_label or "").strip()
    if not value:
        return ""
    value = _TRADE_WORDS.sub(" ", value)
    value = _QUANTITY.sub(" ", value)
    value = _PRICE.sub(" ", value)
    value = _SEPARATORS.sub(" ", value)
    value = _SPACES.sub(" ", value).strip(" -._~")
    if not value or _TRADE_WORDS.fullmatch(value):
        return ""
    return value
