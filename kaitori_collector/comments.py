"""Parser for the public DCInside comment fragment."""
from __future__ import annotations

import re
from html.parser import HTMLParser

from .contracts import CommentRecord
from .html import infer_author_type, normalize_space


class CommentHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.current: dict[str, str] | None = None
        self._rows: list[dict[str, str]] = []
        self._reply_parts: list[str] = []
        self._author_parts: list[str] = []
        self._time_parts: list[str] = []
        self._in_reply = False
        self._in_author = False
        self._in_time = False
        self._in_ip = False
        self._reply_attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        classes = set((attributes.get("class") or "").split())
        if tag not in {"br", "img", "input", "meta", "link"}:
            self.stack.append((tag, classes))
        if tag == "tr" and "reply_line" in classes:
            self.current = {"comment_id": "", "parent_id": "", "author_name": "", "author_type": "unknown", "body": "", "posted_at": ""}
            self._reply_attrs = attributes
        elif self.current is not None and tag == "td" and "user" in classes and "user_layer" in classes:
            self._in_author = True
            self._author_parts = []
            self._reply_attrs.update(attributes)
        elif self.current is not None and tag == "td" and "reply" in classes:
            self._in_reply = True
            self._reply_parts = []
        elif self.current is not None and tag == "td" and "retime" in classes:
            self._in_time = True
            self._time_parts = []
        elif self.current is not None and "etc_ip" in classes:
            self._in_ip = True
        if self.current is not None and tag == "a":
            onclick = attributes.get("onclick", "")
            match = re.search(r"\((.*?)\)", onclick)
            if match and not self.current["comment_id"]:
                values = [part.strip(" '\"") for part in match.group(1).split(",")]
                if values:
                    self.current["comment_id"] = values[0]
                if len(values) >= 4:
                    self.current["parent_id"] = values[3]

    def handle_endtag(self, tag: str) -> None:
        if self.current is not None and tag == "td":
            if self._in_author:
                self.current["author_name"] = normalize_space("".join(self._author_parts))
                self.current["author_type"] = infer_author_type(self.current["author_name"], self._reply_attrs)
                self._in_author = False
            if self._in_reply:
                self.current["body"] = normalize_space("".join(self._reply_parts))
                self._in_reply = False
            if self._in_time:
                self.current["posted_at"] = normalize_space("".join(self._time_parts))
                self._in_time = False
            self._in_ip = False
        if tag == "tr" and self.current is not None:
            self._rows.append(dict(self.current))
            self.current = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self.current is None or self._in_ip:
            return
        if self._in_author:
            self._author_parts.append(data)
        if self._in_reply:
            self._reply_parts.append(data)
        if self._in_time:
            self._time_parts.append(data)


def parse_comments(html: str, post_url: str, gallery_id: str) -> list[CommentRecord]:
    parser = CommentHTMLParser()
    parser.feed(html)
    return [
        CommentRecord(
            gallery_id=gallery_id,
            post_url=post_url,
            comment_id=row["comment_id"],
            parent_id=row["parent_id"],
            author_name=row["author_name"],
            author_type=row["author_type"],
            body=row["body"],
            posted_at=row["posted_at"],
        )
        for row in parser._rows
        if row["body"]
    ]
