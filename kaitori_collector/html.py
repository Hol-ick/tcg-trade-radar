"""Small, dependency-free HTML adapter for stable DCInside page classes."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class DCInsideHTMLParser(HTMLParser):
    """Collect title, body, JSON-LD and list rows without executing page code."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.write_parts: list[str] = []
        self.title_head_parts: list[str] = []
        self.title_subject_parts: list[str] = []
        self.json_ld_parts: list[str] = []
        self.json_ld_scripts: list[str] = []
        self.json_ld_active = False
        self.current_row: dict[str, str] | None = None
        self.current_row_subject: list[str] = []
        self.subject_depth: int | None = None
        self._list_rows: list[dict[str, str]] = []
        self.author_name = ""
        self.author_type = "unknown"
        self._author_active = False
        self._author_parts: list[str] = []
        self._author_attrs: dict[str, str] = {}

    def _has_class(self, name: str) -> bool:
        return any(name in classes for _, classes in self.stack)

    def _append(self, parts: list[str], value: str) -> None:
        if value:
            parts.append(value.replace("\xa0", " "))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag not in VOID_TAGS:
            self.stack.append((tag, classes))

        if tag == "script" and (attributes.get("type") or "").lower() == "application/ld+json":
            self.json_ld_active = True
            self.json_ld_parts = []

        if tag == "tr":
            self.current_row = {"subject": "", "href": ""}
            self.current_row_subject = []
            self.subject_depth = None
        elif tag == "td" and "gall_subject" in classes and self.current_row is not None:
            self.subject_depth = len(self.stack)

        if self._has_class("write_div"):
            self._append(self.write_parts, "\n" if tag in {"br", "p", "div", "li"} else "")
        if self._has_class("title_headtext"):
            self._append(self.title_head_parts, "\n" if tag == "br" else "")
        if self._has_class("title_subject"):
            self._append(self.title_subject_parts, "\n" if tag == "br" else "")

        if not self.author_name and self._has_class("w_top_left") and (
            "nickname" in classes or attributes.get("user_name") or attributes.get("user_id")
        ):
            self._author_active = True
            self._author_parts = []
            self._author_attrs = {key: value or "" for key, value in attributes.items()}

        if self.current_row is not None and tag == "a" and ("gall_tit" in classes or self._has_class("gall_tit")):
            self.current_row["href"] = attributes.get("href") or ""

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.json_ld_active:
            self.json_ld_scripts.append("".join(self.json_ld_parts))
            self.json_ld_parts = []
            self.json_ld_active = False

        if self._author_active and tag in {"span", "a"}:
            self.author_name = normalize_space("".join(self._author_parts))
            self.author_type = infer_author_type(self.author_name, self._author_attrs)
            self._author_active = False

        if tag == "td" and self.subject_depth == len(self.stack) and self.current_row is not None:
            self.current_row["subject"] = "".join(self.current_row_subject)
            self.subject_depth = None

        if tag == "tr" and self.current_row is not None:
            if self.current_row.get("subject") or self.current_row.get("href"):
                self.current_row["subject"] = normalize_space(self.current_row["subject"])
                self.current_row["href"] = self.current_row["href"].strip()
                self._list_rows.append(self.current_row)
            self.current_row = None
            self.current_row_subject = []
            self.subject_depth = None

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self.json_ld_active:
            self.json_ld_parts.append(data)
        if self._has_class("write_div"):
            self._append(self.write_parts, data)
        if self._has_class("title_headtext"):
            self._append(self.title_head_parts, data)
        if self._has_class("title_subject"):
            self._append(self.title_subject_parts, data)
        if self._author_active:
            self._author_parts.append(data)
        if self.subject_depth is not None and self.current_row is not None:
            self.current_row_subject.append(data)

    @property
    def list_rows(self) -> list[dict[str, str]]:
        return self._list_rows


def normalize_space(value: str) -> str:
    import re

    return re.sub(r"[ \t\r\f\v]+", " ", value.replace("\xa0", " ")).strip()


def normalize_body(value: str) -> str:
    lines = [normalize_space(line) for line in value.replace("\r", "").split("\n")]
    return "\n".join(line for line in lines if line)


def parse_json_ld(scripts: list[str]) -> dict[str, Any]:
    for script in scripts:
        try:
            value = json.loads(script.strip())
        except json.JSONDecodeError:
            continue
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("articleBody"):
                return candidate
    return {}


def parse_html(html: str, url: str) -> tuple[dict[str, Any], DCInsideHTMLParser]:
    parser = DCInsideHTMLParser()
    parser.feed(html)
    metadata = parse_json_ld(parser.json_ld_scripts)
    title = normalize_space(" ".join(parser.title_subject_parts)) or normalize_space(str(metadata.get("headline", "")))
    subject = normalize_space(" ".join(parser.title_head_parts))
    body = normalize_body("".join(parser.write_parts))
    if not body:
        body = normalize_body(str(metadata.get("articleBody", "")))
    return {
        "title": title,
        "subject": subject,
        "body": body,
        "url": str(metadata.get("url") or url),
        "posted_at": str(metadata.get("datePublished") or ""),
        "author_name": parser.author_name,
        "author_type": parser.author_type,
    }, parser


def infer_author_type(name: str, attrs: dict[str, str] | None = None) -> str:
    """Classify the public author marker without storing network identifiers."""
    attrs = attrs or {}
    public_id = attrs.get("user_id") or attrs.get("data-uid") or attrs.get("data-user-id")
    if public_id and not re.fullmatch(r"(?:\d{1,3}\.){1,3}\d{1,3}", public_id):
        return "registered"
    if re.search(r"\b(?:ㅇㅇ|유동)\b", name) or re.search(r"\([^)]*\d+\.[^)]*\)", name):
        return "guest"
    if name:
        return "registered"
    return "unknown"
