"""Deterministic card-catalog matching with an explicit review boundary."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal


@dataclass(frozen=True)
class CatalogCard:
    id: str
    code: str
    name: str
    game: str = ""
    set_name: str = ""
    rarity: str = ""


@dataclass(frozen=True)
class MatchCandidate:
    card: CatalogCard
    confidence: float
    matched_by: str


@dataclass(frozen=True)
class MatchResult:
    status: Literal["matched", "needs_review"]
    card_code: str
    candidates: list[MatchCandidate]
    reason: str


CARD_CODE_RE = re.compile(r"\b[A-Z]{2,8}[-_][A-Z0-9]{2,12}\b", re.IGNORECASE)


def match_card(card_name: str, rarity: str, catalog: Iterable[CatalogCard]) -> MatchResult:
    cards = list(catalog)
    code = extract_card_code(card_name)
    if code:
        code_candidates = [card for card in cards if card.code.casefold() == code.casefold()]
        if rarity:
            rarity_candidates = [card for card in code_candidates if normalize(card.rarity) == normalize(rarity)]
            if rarity_candidates:
                code_candidates = rarity_candidates
        if len(code_candidates) == 1:
            return MatchResult("matched", code, [MatchCandidate(code_candidates[0], 1.0, "card_code")], "카드 코드 일치")
        if len(code_candidates) > 1:
            return MatchResult("needs_review", code, [MatchCandidate(card, 0.98, "card_code") for card in code_candidates], "카드 코드 후보가 복수")

    normalized_name = normalize(CARD_CODE_RE.sub("", card_name))
    candidates = [card for card in cards if normalize(card.name) == normalized_name]
    if rarity:
        rarity_candidates = [card for card in candidates if normalize(card.rarity) == normalize(rarity)]
        if rarity_candidates:
            candidates = rarity_candidates
    if len(candidates) == 1:
        return MatchResult("matched", candidates[0].code, [MatchCandidate(candidates[0], 0.9, "name_rarity" if rarity else "name")], "카드명 후보 하나")
    if len(candidates) > 1:
        return MatchResult("needs_review", code, [MatchCandidate(card, 0.7, "name") for card in candidates], "카드명 후보가 복수")
    return MatchResult("needs_review", code, [], "카탈로그와 일치하는 카드 없음")


def extract_card_code(value: str) -> str:
    match = CARD_CODE_RE.search(value or "")
    return match.group(0).upper().replace("_", "-") if match else ""


def normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (value or "").casefold())
