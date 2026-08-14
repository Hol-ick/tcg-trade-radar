"""Versioned data contracts shared by the CLI, worker and admin API."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any, Literal


ShippingIncluded = Literal["included", "separate", "unknown"]
RowStatus = Literal["raw", "parsed", "needs_review", "approved", "rejected", "exported"]
JobState = Literal["queued", "running", "completed", "failed"]
ListingType = Literal["sell", "buy", "trade", "unknown"]
PriceType = Literal["asking", "wanted", "unknown"]
AuthorType = Literal["guest", "registered", "unknown"]
PostStatus = Literal["active", "completed", "reserved", "price_removed", "image_only", "unknown"]
PriceStatus = Literal["exact", "estimated", "missing", "removed", "unknown"]
PriceScope = Literal["per_card", "per_quantity", "bundle", "unknown"]
PriceOrigin = Literal["text", "ocr", "comment", "inferred", "unknown"]
AnalysisStatus = Literal["usable", "needs_review", "context_only", "excluded"]
CardMatchStatus = Literal["matched", "candidate", "unmatched", "image_review"]


@dataclass(frozen=True)
class ExtractedRow:
    """Backward-compatible internal representation of one extracted sale row."""

    gallery_id: str
    post_title: str
    post_url: str
    posted_at: str
    card_name: str
    rarity: str
    raw_price: str
    price_krw: int
    price_unit: str
    quantity: int
    shipping_included: bool | None
    shipping_price_krw: int | None
    review_status: str
    review_reason: str
    raw_line: str
    listing_type: ListingType = "unknown"
    intent_confidence: float = 0.0
    price_type: PriceType = "unknown"
    author_name: str = ""
    author_type: AuthorType = "unknown"
    post_status: PostStatus = "active"
    price_status: PriceStatus = "exact"
    price_scope: PriceScope = "per_card"
    price_origin: PriceOrigin = "text"
    analysis_status: AnalysisStatus = "usable"
    card_match_status: CardMatchStatus = "unmatched"


@dataclass(frozen=True)
class CommentRecord:
    gallery_id: str
    post_url: str
    comment_id: str
    parent_id: str
    author_name: str
    author_type: AuthorType
    body: str
    posted_at: str


@dataclass(frozen=True)
class JobRequest:
    gallery_id: str
    gallery_url: str = ""
    subject: str = "판매"
    subjects: tuple[str, ...] = ()
    since: str | None = None
    until: str | None = None
    cutoff_at: str | None = None
    max_posts: int = 20
    max_pages: int = 1
    delay: float = 1.0
    max_retries: int = 2
    buy_rate: int = 60
    keep_raw: bool = True
    review_unmatched: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRequest":
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        gallery_id = str(payload.get("gallery_id") or "").strip()
        if not gallery_id:
            raise ValueError("gallery_id is required")
        request = cls(
            gallery_id=gallery_id,
            gallery_url=str(payload.get("gallery_url") or "").strip(),
            subject=str(payload.get("subject") or "판매").strip() or "판매",
            subjects=_as_subjects(payload.get("subjects")),
            since=_optional_text(payload.get("since")),
            until=_optional_text(payload.get("until")),
            cutoff_at=_optional_text(payload.get("cutoff_at")),
            max_posts=_as_int(payload.get("max_posts"), 20),
            max_pages=_as_int(payload.get("max_pages", payload.get("pages")), 1),
            delay=_as_float(payload.get("delay", payload.get("delay_seconds")), 1.0),
            max_retries=_as_int(payload.get("max_retries"), 2),
            buy_rate=_as_int(payload.get("buy_rate"), 60),
            keep_raw=_as_bool(payload.get("keep_raw"), True),
            review_unmatched=_as_bool(payload.get("review_unmatched"), True),
        )
        request.validate()
        return request

    def validate(self) -> None:
        if not self.gallery_id:
            raise ValueError("gallery_id is required")
        if self.cutoff_at:
            try:
                cutoff = datetime.fromisoformat(self.cutoff_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("cutoff_at must be an ISO-8601 timestamp") from exc
            if cutoff.tzinfo is None:
                raise ValueError("cutoff_at must include a timezone offset")
        if any(not subject.strip() for subject in self.subjects):
            raise ValueError("subjects must contain non-empty strings")
        if not 1 <= self.max_posts <= 20_000:
            raise ValueError("max_posts must be between 1 and 20000")
        if not 1 <= self.max_pages <= 5_000:
            raise ValueError("max_pages must be between 1 and 5000")
        if self.delay < 0:
            raise ValueError("delay must be zero or greater")
        if not 0 <= self.max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")
        if not 0 <= self.buy_rate <= 100:
            raise ValueError("buy_rate must be between 0 and 100")


@dataclass(frozen=True)
class JobStatus:
    id: str
    gallery_id: str
    subject: str
    since: str | None
    until: str | None
    buy_rate: int
    state: JobState
    counts: dict[str, int]
    error_message: str | None
    created_at: str
    finished_at: str | None
    worker_version: str
    last_success_at: str | None


@dataclass(frozen=True)
class ReviewAction:
    action: Literal["approve", "reject", "edit"]
    actor: str
    after_data: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewAction":
        action = str(payload.get("action") or "").strip().lower()
        if action not in {"approve", "reject", "edit"}:
            raise ValueError("action must be approve, reject, or edit")
        actor = str(payload.get("actor") or "admin").strip() or "admin"
        after_data = payload.get("after_data")
        if after_data is not None and not isinstance(after_data, dict):
            raise ValueError("after_data must be an object")
        return cls(action=action, actor=actor, after_data=after_data)


@dataclass(frozen=True)
class SellerReviewAction:
    action: Literal["watch", "clear", "mark_safe", "confirm_risk", "note"]
    actor: str = "admin"
    note: str = ""
    evidence_url: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SellerReviewAction":
        action = str(payload.get("action") or "").strip().lower()
        if action not in {"watch", "clear", "mark_safe", "confirm_risk", "note"}:
            raise ValueError("action must be watch, clear, mark_safe, confirm_risk, or note")
        return cls(
            action=action,
            actor=str(payload.get("actor") or "admin").strip() or "admin",
            note=str(payload.get("note") or "").strip(),
            evidence_url=str(payload.get("evidence_url") or "").strip(),
        )


def to_public_row(row: ExtractedRow | dict[str, Any]) -> dict[str, Any]:
    """Return the stable API shape without leaking internal boolean values."""
    values = asdict(row) if isinstance(row, ExtractedRow) else dict(row)
    values["shipping_included"] = _shipping_value(values.get("shipping_included"))
    return {field.name: values.get(field.name) for field in fields(ExtractedRow)}


def utc_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _shipping_value(value: Any) -> ShippingIncluded:
    if value in (True, "true", "included"):
        return "included"
    if value in (False, "false", "separate"):
        return "separate"
    return "unknown"


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected integer, got {value!r}") from exc


def _as_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected number, got {value!r}") from exc


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    raise ValueError(f"expected boolean, got {value!r}")


def _as_subjects(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        raise ValueError("subjects must be a list or string")
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
