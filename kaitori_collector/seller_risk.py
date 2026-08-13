"""Seller identity, repost fingerprints and review-oriented risk signals.

The collector must not turn a nickname or a guest marker into a scam verdict.
Registered identities are grouped only inside a gallery. Guest identities are
post-scoped because common guest labels and partial IP displays are not stable
identifiers.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class SellerIdentity:
    seller_id: str
    display_name: str
    author_type: str
    identity_scope: str


def normalize_identity_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", value).strip().casefold()


def build_seller_identity(gallery_id: str, author_name: str, author_type: str, source_id: str) -> SellerIdentity:
    gallery = normalize_identity_name(gallery_id) or "unknown-gallery"
    author_kind = str(author_type or "unknown").strip().casefold()
    display_name = str(author_name or "미상").strip() or "미상"
    if author_kind == "registered" and normalize_identity_name(author_name):
        scope = "gallery"
        key = f"{gallery}|registered|{normalize_identity_name(author_name)}"
    else:
        # Guest names such as ㅇㅇ are not stable. Keep each post separate.
        scope = "post"
        key = f"{gallery}|guest|{source_id}"
        author_kind = "guest" if author_kind in {"", "unknown"} else author_kind
    seller_id = "seller-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return SellerIdentity(seller_id, display_name, author_kind, scope)


def build_post_family_id(gallery_id: str, post_url: str, post_id: str = "") -> str:
    parsed = urlparse(post_url)
    number = str(post_id or parse_qs(parsed.query).get("no", [""])[0]).strip()
    key = f"{normalize_identity_name(gallery_id)}|post|{number}" if number else f"{normalize_identity_name(gallery_id)}|url|{post_url.rstrip('/')}"
    return "post-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def build_listing_fingerprint(source: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    parts = [normalize_text(str(source.get("title") or ""))]
    for row in sorted(rows, key=lambda item: (str(item.get("card_name_raw") or ""), str(item.get("raw_line") or ""))):
        parts.append("|".join([
            normalize_text(str(row.get("card_name_raw") or "")),
            normalize_text(str(row.get("rarity") or "")),
            str(row.get("listing_type") or "unknown"),
            str(row.get("price_status") or "unknown"),
            str(row.get("price_scope") or "unknown"),
        ]))
    return "listing-" + hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def risk_level(score: int) -> str:
    if score >= 50:
        return "high"
    if score >= 20:
        return "medium"
    return "low"


def detect_text_signals(text: str) -> list[dict[str, Any]]:
    value = normalize_text(text)
    signals: list[dict[str, Any]] = []
    if re.search(r"오픈\s*카톡|오픈채팅|카카오톡|텔레그램|telegram|open\.kakao", value):
        signals.append({"code": "external_messenger", "severity": "medium", "score_delta": 15, "message": "외부 메신저 유도 표현이 있어 거래 방식 확인이 필요합니다."})
    if re.search(r"사기|먹튀|잠수|연락\s*두절|미배송|환불\s*분쟁|입금하고", value):
        signals.append({"code": "dispute_keyword", "severity": "high", "score_delta": 30, "message": "본문 또는 댓글에 거래 분쟁 관련 표현이 있어 확인이 필요합니다."})
    return signals
