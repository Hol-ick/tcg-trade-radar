"""Safe source-response inspection and bounded retry helpers."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html import unescape
from typing import Any

from .html import DCInsideHTMLParser


BLOCK_MARKERS = (
    "자동입력 방지",
    "비정상적인 접근",
    "접근이 제한",
    "captcha",
    "access denied",
    "too many requests",
)


@dataclass(frozen=True)
class SourceResponseProfile:
    state: str
    expected: str
    characters: int
    list_rows: int
    image_count: int
    markers: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_source_response(html: str, url: str, *, expected: str) -> SourceResponseProfile:
    value = html or ""
    visible = re.sub(r"<script\b[^>]*>.*?</script\s*>", " ", value, flags=re.I | re.S)
    visible = re.sub(r"<style\b[^>]*>.*?</style\s*>", " ", visible, flags=re.I | re.S)
    visible = unescape(re.sub(r"<[^>]+>", " ", visible)).casefold()
    lowered = visible
    markers = tuple(marker for marker in BLOCK_MARKERS if marker.casefold() in lowered)
    if not value.strip():
        return SourceResponseProfile("empty", expected, 0, 0, 0, markers, "응답 본문이 비어 있음")
    if markers:
        return SourceResponseProfile("blocked", expected, len(value), 0, value.lower().count("<img"), markers, "차단 응답 문구가 포함됨")
    parser = DCInsideHTMLParser()
    parser.feed(value)
    rows = len(parser.list_rows)
    if expected == "list" and rows == 0:
        return SourceResponseProfile("structure_changed", expected, len(value), 0, value.lower().count("<img"), markers, "목록 행을 찾지 못함")
    if expected == "post" and len(value) < 80:
        return SourceResponseProfile("suspicious", expected, len(value), rows, value.lower().count("<img"), markers, "게시글 응답이 비정상적으로 짧음")
    return SourceResponseProfile("ok", expected, len(value), rows, value.lower().count("<img"), markers, "정상 응답으로 판별")


def is_retryable_error(error: BaseException) -> bool:
    return isinstance(error, (TimeoutError, ConnectionError, OSError))


def retry_delay(attempt: int) -> float:
    return min(8.0, 1.0 * (2 ** max(0, attempt)))
