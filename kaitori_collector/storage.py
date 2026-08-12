"""SQLite persistence for raw sources, extracted rows, jobs and reviews."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .contracts import CommentRecord, ExtractedRow, JobRequest, ReviewAction, to_public_row, utc_now


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kaitori_sources (
  id TEXT PRIMARY KEY,
  gallery_id TEXT NOT NULL,
  post_id TEXT,
  post_url TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  posted_at TEXT NOT NULL DEFAULT '',
  author_name TEXT NOT NULL DEFAULT '',
  author_type TEXT NOT NULL DEFAULT 'unknown',
  raw_html TEXT,
  fetched_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  source_status TEXT NOT NULL DEFAULT 'active',
  UNIQUE (post_url, content_hash)
);

CREATE TABLE IF NOT EXISTS kaitori_jobs (
  id TEXT PRIMARY KEY,
  gallery_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  since TEXT,
  until TEXT,
  buy_rate INTEGER NOT NULL,
  state TEXT NOT NULL,
  counts TEXT NOT NULL DEFAULT '{}',
  error_message TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT,
  worker_version TEXT NOT NULL,
  last_success_at TEXT,
  config_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS kaitori_rows (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  row_fingerprint TEXT NOT NULL,
  card_name_raw TEXT NOT NULL DEFAULT '',
  card_code TEXT NOT NULL DEFAULT '',
  rarity TEXT NOT NULL DEFAULT '',
  raw_price TEXT NOT NULL DEFAULT '',
  price_krw INTEGER NOT NULL DEFAULT 0,
  price_unit TEXT NOT NULL DEFAULT '',
  quantity INTEGER NOT NULL DEFAULT 1,
  shipping_included TEXT NOT NULL CHECK (shipping_included IN ('included', 'separate', 'unknown')),
  shipping_price_krw INTEGER,
  status TEXT NOT NULL CHECK (status IN ('raw', 'parsed', 'needs_review', 'approved', 'rejected', 'exported')),
  review_reason TEXT NOT NULL DEFAULT '',
  raw_line TEXT NOT NULL DEFAULT '',
  listing_type TEXT NOT NULL DEFAULT 'unknown',
  intent_confidence REAL NOT NULL DEFAULT 0,
  price_type TEXT NOT NULL DEFAULT 'unknown',
  set_name TEXT NOT NULL DEFAULT '',
  condition_raw TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, row_fingerprint)
);

CREATE TABLE IF NOT EXISTS kaitori_job_sources (
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (job_id, source_id)
);

CREATE TABLE IF NOT EXISTS kaitori_job_rows (
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (job_id, row_id)
);

CREATE TABLE IF NOT EXISTS kaitori_matches (
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  catalog_card_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  matched_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (row_id, catalog_card_id)
);

CREATE TABLE IF NOT EXISTS kaitori_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  before_data TEXT NOT NULL,
  after_data TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kaitori_job_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  created_at TEXT NOT NULL,
  level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error')),
  step TEXT NOT NULL,
  message TEXT NOT NULL,
  details TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS kaitori_comments (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  gallery_id TEXT NOT NULL,
  post_url TEXT NOT NULL,
  comment_id TEXT NOT NULL DEFAULT '',
  parent_id TEXT NOT NULL DEFAULT '',
  author_name TEXT NOT NULL DEFAULT '',
  author_type TEXT NOT NULL DEFAULT 'unknown',
  body TEXT NOT NULL DEFAULT '',
  posted_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE (source_id, comment_id, body)
);

CREATE INDEX IF NOT EXISTS kaitori_rows_job_status_idx ON kaitori_rows(job_id, status);
CREATE INDEX IF NOT EXISTS kaitori_reviews_row_idx ON kaitori_reviews(row_id, id);
CREATE INDEX IF NOT EXISTS kaitori_job_rows_status_idx ON kaitori_job_rows(job_id, row_id);
CREATE INDEX IF NOT EXISTS kaitori_job_logs_job_idx ON kaitori_job_logs(job_id, id);
CREATE INDEX IF NOT EXISTS kaitori_comments_source_idx ON kaitori_comments(source_id, id);

CREATE TABLE IF NOT EXISTS kaitori_demand_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_date TEXT NOT NULL,
  game_id TEXT NOT NULL,
  card_key TEXT NOT NULL,
  card_name_raw TEXT NOT NULL DEFAULT '',
  sell_count INTEGER NOT NULL DEFAULT 0,
  buy_count INTEGER NOT NULL DEFAULT 0,
  trade_count INTEGER NOT NULL DEFAULT 0,
  sell_price_median INTEGER,
  sell_price_min INTEGER,
  sell_price_max INTEGER,
  wanted_price_median INTEGER,
  active_source_count INTEGER NOT NULL DEFAULT 0,
  demand_score REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(snapshot_date, game_id, card_key)
);

CREATE INDEX IF NOT EXISTS kaitori_snapshot_game_date_idx ON kaitori_demand_snapshots(game_id, snapshot_date);
"""


class Repository:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(SCHEMA_SQL)
        self._ensure_market_columns()
        self.connection.commit()

    def _ensure_market_columns(self) -> None:
        existing = {row[1] for row in self.connection.execute("PRAGMA table_info(kaitori_rows)").fetchall()}
        additions = {
            "listing_type": "TEXT NOT NULL DEFAULT 'unknown'",
            "intent_confidence": "REAL NOT NULL DEFAULT 0",
            "price_type": "TEXT NOT NULL DEFAULT 'unknown'",
            "set_name": "TEXT NOT NULL DEFAULT ''",
            "condition_raw": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in additions.items():
            if column not in existing:
                self.connection.execute(f"ALTER TABLE kaitori_rows ADD COLUMN {column} {definition}")
        source_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(kaitori_sources)").fetchall()}
        if "source_status" not in source_columns:
            self.connection.execute("ALTER TABLE kaitori_sources ADD COLUMN source_status TEXT NOT NULL DEFAULT 'active'")
        if "author_name" not in source_columns:
            self.connection.execute("ALTER TABLE kaitori_sources ADD COLUMN author_name TEXT NOT NULL DEFAULT ''")
        if "author_type" not in source_columns:
            self.connection.execute("ALTER TABLE kaitori_sources ADD COLUMN author_type TEXT NOT NULL DEFAULT 'unknown'")

    def close(self) -> None:
        self.connection.close()

    def create_job(self, request: JobRequest, job_id: str | None = None) -> str:
        request.validate()
        job_id = job_id or f"job-{uuid.uuid4().hex[:12]}"
        now = utc_now()
        self.connection.execute(
            """INSERT INTO kaitori_jobs
            (id, gallery_id, subject, since, until, buy_rate, state, counts,
             created_at, worker_version, config_json)
            VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)""",
            (
                job_id,
                request.gallery_id,
                request.subject,
                request.since,
                request.until,
                request.buy_rate,
                json.dumps(_empty_counts()),
                now,
                __version__,
                json.dumps({"gallery_url": request.gallery_url, "max_posts": request.max_posts, "max_pages": request.max_pages, "delay": request.delay, "max_retries": request.max_retries, "keep_raw": request.keep_raw, "review_unmatched": request.review_unmatched, "subjects": list(request.subjects)}, ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM kaitori_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["counts"] = self._counts_for_job(job_id)
        return result

    def update_job(self, job_id: str, *, state: str | None = None, error_message: str | None = None, finished_at: str | None = None, last_success_at: str | None = None) -> None:
        updates: list[str] = []
        values: list[Any] = []
        if state is not None:
            updates.append("state = ?")
            values.append(state)
        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)
        if finished_at is not None:
            updates.append("finished_at = ?")
            values.append(finished_at)
        if last_success_at is not None:
            updates.append("last_success_at = ?")
            values.append(last_success_at)
        counts = self._counts_for_job(job_id)
        updates.append("counts = ?")
        values.append(json.dumps(counts, ensure_ascii=False))
        if not updates:
            return
        values.append(job_id)
        self.connection.execute(f"UPDATE kaitori_jobs SET {', '.join(updates)} WHERE id = ?", values)
        self.connection.commit()

    def reset_job(self, job_id: str) -> None:
        self.connection.execute(
            "UPDATE kaitori_jobs SET state = 'queued', error_message = NULL, finished_at = NULL WHERE id = ?",
            (job_id,),
        )
        self.connection.commit()

    def add_job_log(
        self,
        job_id: str,
        *,
        level: str = "info",
        step: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> int:
        if level not in {"info", "warning", "error"}:
            raise ValueError("log level must be info, warning, or error")
        cursor = self.connection.execute(
            """INSERT INTO kaitori_job_logs (job_id, created_at, level, step, message, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, utc_now(), level, step, message, json.dumps(details or {}, ensure_ascii=False)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def list_job_logs(self, job_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, job_id, created_at, level, step, message, details FROM kaitori_job_logs WHERE job_id = ? ORDER BY id LIMIT ?",
            (job_id, max(1, min(limit, 2000))),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item["details"] or "{}")
            except json.JSONDecodeError:
                item["details"] = {}
            result.append(item)
        return result

    def upsert_source(self, source: dict[str, Any]) -> tuple[str, bool]:
        post_url = str(source.get("post_url") or "").strip()
        if not post_url:
            raise ValueError("source post_url is required")
        raw_html = str(source.get("raw_html") or "")
        content_hash = str(source.get("content_hash") or _hash_text(raw_html)).strip()
        source_id = _hash_text(f"{post_url}\n{content_hash}")[:24]
        values = (
            source_id,
            str(source.get("gallery_id") or ""),
            str(source.get("post_id") or parse_qs(urlparse(post_url).query).get("no", [""])[0]),
            post_url,
            str(source.get("title") or ""),
            str(source.get("posted_at") or ""),
            str(source.get("author_name") or ""),
            str(source.get("author_type") or "unknown"),
            raw_html if source.get("keep_raw", True) else None,
            str(source.get("fetched_at") or utc_now()),
            content_hash,
            str(source.get("source_status") or "active"),
        )
        cursor = self.connection.execute(
            """INSERT OR IGNORE INTO kaitori_sources
            (id, gallery_id, post_id, post_url, title, posted_at, author_name, author_type, raw_html, fetched_at, content_hash, source_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
        self.connection.execute(
            """UPDATE kaitori_sources
               SET author_name = CASE WHEN ? <> '' THEN ? ELSE author_name END,
                   author_type = CASE WHEN ? <> 'unknown' THEN ? ELSE author_type END
               WHERE id = ?""",
            (values[6], values[6], values[7], values[7], source_id),
        )
        self.connection.commit()
        return source_id, cursor.rowcount == 1

    def insert_comments(self, source_id: str, comments: list[CommentRecord]) -> int:
        inserted = 0
        now = utc_now()
        for comment in comments:
            fingerprint = _hash_text(json.dumps({
                "source_id": source_id,
                "comment_id": comment.comment_id,
                "parent_id": comment.parent_id,
                "body": comment.body,
                "posted_at": comment.posted_at,
            }, ensure_ascii=False, sort_keys=True))[:24]
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO kaitori_comments
                (id, source_id, gallery_id, post_url, comment_id, parent_id, author_name, author_type, body, posted_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fingerprint, source_id, comment.gallery_id, comment.post_url, comment.comment_id, comment.parent_id, comment.author_name, comment.author_type, comment.body, comment.posted_at, now),
            )
            inserted += int(cursor.rowcount == 1)
        self.connection.commit()
        return inserted

    def list_comments(self, *, job_id: str | None = None, source_id: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT c.* FROM kaitori_comments c
                   JOIN kaitori_sources s ON s.id = c.source_id
                   LEFT JOIN kaitori_job_sources js ON js.source_id = c.source_id
                   WHERE 1=1"""
        values: list[Any] = []
        if job_id:
            query += " AND js.job_id = ?"
            values.append(job_id)
        if source_id:
            query += " AND c.source_id = ?"
            values.append(source_id)
        query += " GROUP BY c.id ORDER BY c.posted_at, c.id"
        return [dict(row) for row in self.connection.execute(query, values).fetchall()]

    def attach_source_to_job(self, job_id: str, source_id: str) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO kaitori_job_sources (job_id, source_id, created_at) VALUES (?, ?, ?)",
            (job_id, source_id, utc_now()),
        )
        self.connection.commit()

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM kaitori_sources WHERE id = ?", (source_id,)).fetchone()
        return dict(row) if row else None

    def insert_rows(self, job_id: str, source_id: str, rows: list[ExtractedRow]) -> int:
        inserted = 0
        now = utc_now()
        for row in rows:
            public = to_public_row(row)
            fingerprint = _hash_text(json.dumps({
                "source_id": source_id,
                "card_name": public["card_name"],
                "rarity": public["rarity"],
                "raw_price": public["raw_price"],
                "quantity": public["quantity"],
                "shipping_included": public["shipping_included"],
                "listing_type": public["listing_type"],
                "price_type": public["price_type"],
                "raw_line": public["raw_line"],
            }, ensure_ascii=False, sort_keys=True))
            row_id = _hash_text(f"{source_id}:{fingerprint}")[:24]
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO kaitori_rows
                (id, job_id, source_id, row_fingerprint, card_name_raw, rarity, raw_price,
                 price_krw, price_unit, quantity, shipping_included, shipping_price_krw,
                 status, review_reason, raw_line, listing_type, intent_confidence, price_type,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    job_id,
                    source_id,
                    fingerprint,
                    public["card_name"],
                    public["rarity"],
                    public["raw_price"],
                    public["price_krw"],
                    public["price_unit"],
                    max(1, int(public["quantity"] or 1)),
                    public["shipping_included"],
                    public["shipping_price_krw"],
                    public["review_status"] if public["review_status"] in {"parsed", "needs_review"} else "needs_review",
                    public["review_reason"],
                    public["raw_line"],
                    public["listing_type"],
                    float(public["intent_confidence"] or 0),
                    public["price_type"],
                    now,
                    now,
                ),
            )
            row_exists = cursor.rowcount == 1
            if not row_exists:
                row_exists = self.connection.execute("SELECT 1 FROM kaitori_rows WHERE id = ?", (row_id,)).fetchone() is not None
            if row_exists:
                association = self.connection.execute(
                    "INSERT OR IGNORE INTO kaitori_job_rows (job_id, row_id, created_at) VALUES (?, ?, ?)",
                    (job_id, row_id, now),
                )
                inserted += int(association.rowcount == 1)
        self.connection.commit()
        return inserted

    def list_rows(self, *, job_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT r.*, s.gallery_id, s.post_url, s.title AS post_title, s.posted_at, s.raw_html, s.author_name, s.author_type
                   FROM kaitori_rows r
                   JOIN kaitori_sources s ON s.id = r.source_id
                   LEFT JOIN kaitori_job_rows jr ON jr.row_id = r.id
                   WHERE 1=1"""
        values: list[Any] = []
        if job_id:
            query += " AND jr.job_id = ?"
            values.append(job_id)
        if status:
            query += " AND r.status = ?"
            values.append(status)
        query += " GROUP BY r.id ORDER BY r.created_at, r.id"
        return [dict(row) for row in self.connection.execute(query, values).fetchall()]

    def list_market_listings(
        self,
        *,
        query_text: str = "",
        game_id: str = "",
        listing_type: str = "",
        since: str | None = None,
        until: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        status: str = "",
        sort: str = "recent",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = """SELECT DISTINCT r.*, s.gallery_id, s.post_url, s.title AS post_title,
                   s.posted_at, s.source_status, s.author_name, s.author_type
                   FROM kaitori_rows r
                   JOIN kaitori_sources s ON s.id = r.source_id
                   WHERE 1=1"""
        values: list[Any] = []
        if game_id:
            query += " AND s.gallery_id = ?"
            values.append(game_id)
        if listing_type in {"sell", "buy", "trade", "unknown"}:
            query += " AND r.listing_type = ?"
            values.append(listing_type)
        if query_text.strip():
            query += " AND (r.card_name_raw LIKE ? OR r.card_code LIKE ? OR s.title LIKE ?)"
            term = f"%{query_text.strip()}%"
            values.extend([term, term, term])
        if since:
            query += " AND substr(s.posted_at, 1, 10) >= ?"
            values.append(since[:10])
        if until:
            query += " AND substr(s.posted_at, 1, 10) <= ?"
            values.append(until[:10])
        if min_price is not None:
            query += " AND r.price_krw >= ?"
            values.append(min_price)
        if max_price is not None:
            query += " AND r.price_krw <= ?"
            values.append(max_price)
        if status:
            query += " AND r.status = ?"
            values.append(status)
        order = {
            "price_asc": "r.price_krw ASC, s.posted_at DESC",
            "price_desc": "r.price_krw DESC, s.posted_at DESC",
            "demand": "r.intent_confidence DESC, s.posted_at DESC",
            "recent": "s.posted_at DESC, r.created_at DESC",
        }.get(sort, "s.posted_at DESC, r.created_at DESC")
        query += f" ORDER BY {order} LIMIT ?"
        values.append(max(1, min(int(limit), 1000)))
        return [dict(row) for row in self.connection.execute(query, values).fetchall()]

    def summarize_cards(
        self,
        *,
        query_text: str = "",
        game_id: str = "",
        listing_type: str = "",
        since: str | None = None,
        until: str | None = None,
        sort: str = "demand",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        rows = self.list_market_listings(query_text=query_text, game_id=game_id, listing_type=listing_type, since=since, until=until, limit=5000)
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = str(row.get("card_code") or row.get("card_name_raw") or "").strip()
            if key:
                groups.setdefault(key, []).append(row)
        result = [_card_summary(key, values) for key, values in groups.items()]
        if sort == "recent":
            result.sort(key=lambda item: item["latest_posted_at"], reverse=True)
        elif sort == "price_asc":
            result.sort(key=lambda item: item["sell_price_median"] if item["sell_price_median"] is not None else 10**12)
        elif sort == "price_desc":
            result.sort(key=lambda item: item["sell_price_median"] if item["sell_price_median"] is not None else -1, reverse=True)
        else:
            result.sort(key=lambda item: (-item["demand_score"], -item["buy_count"], item["card_name_raw"]))
        return result[: max(1, min(int(limit), 500))]

    def refresh_demand_snapshot(self, snapshot_date: str, game_id: str, *, since: str | None = None, until: str | None = None) -> int:
        summaries = self.summarize_cards(game_id=game_id, since=since, until=until, limit=500)
        for summary in summaries:
            self.connection.execute(
                """INSERT OR REPLACE INTO kaitori_demand_snapshots
                (snapshot_date, game_id, card_key, card_name_raw, sell_count, buy_count, trade_count,
                 sell_price_median, sell_price_min, sell_price_max, wanted_price_median,
                 active_source_count, demand_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (snapshot_date, game_id, summary["card_key"], summary["card_name_raw"], summary["sell_count"], summary["buy_count"], summary["trade_count"],
                 summary["sell_price_median"], summary["sell_price_min"], summary["sell_price_max"], summary["wanted_price_median"],
                 summary["active_source_count"], summary["demand_score"], utc_now()),
            )
        self.connection.commit()
        return len(summaries)

    def list_demand_snapshots(self, *, game_id: str = "", card_key: str = "", limit: int = 365) -> list[dict[str, Any]]:
        query = "SELECT * FROM kaitori_demand_snapshots WHERE 1=1"
        values: list[Any] = []
        if game_id:
            query += " AND game_id = ?"
            values.append(game_id)
        if card_key:
            query += " AND card_key = ?"
            values.append(card_key)
        query += " ORDER BY snapshot_date DESC, demand_score DESC LIMIT ?"
        values.append(max(1, min(int(limit), 1000)))
        return [dict(row) for row in self.connection.execute(query, values).fetchall()]

    def get_row(self, row_id: str) -> dict[str, Any] | None:
        rows = self.list_rows()
        return next((row for row in rows if row["id"] == row_id), None)

    def record_review(self, row_id: str, action: ReviewAction) -> dict[str, Any]:
        current = self.get_row(row_id)
        if current is None:
            raise KeyError(f"row not found: {row_id}")
        before = _public_storage_row(current)
        after = dict(before)
        if action.after_data:
            after.update(_allowed_review_fields(action.after_data))
        status = {"approve": "approved", "reject": "rejected", "edit": "needs_review"}[action.action]
        after["status"] = status
        now = utc_now()
        self.connection.execute(
            """INSERT INTO kaitori_reviews (row_id, actor, action, before_data, after_data, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row_id, action.actor, action.action, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False), now),
        )
        updates = {
            "card_name_raw": after.get("card_name_raw", current["card_name_raw"]),
            "rarity": after.get("rarity", current["rarity"]),
            "raw_price": after.get("raw_price", current["raw_price"]),
            "price_krw": after.get("price_krw", current["price_krw"]),
            "quantity": max(1, int(after.get("quantity", current["quantity"]) or 1)),
            "shipping_included": after.get("shipping_included", current["shipping_included"]),
            "shipping_price_krw": after.get("shipping_price_krw", current["shipping_price_krw"]),
            "review_reason": after.get("review_reason", current["review_reason"]),
            "status": status,
            "updated_at": now,
        }
        self.connection.execute(
            """UPDATE kaitori_rows SET card_name_raw = ?, rarity = ?, raw_price = ?, price_krw = ?,
               quantity = ?, shipping_included = ?, shipping_price_krw = ?, review_reason = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (*updates.values(), row_id),
        )
        self.connection.commit()
        updated = self.get_row(row_id)
        assert updated is not None
        return updated

    def list_reviews(self, row_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM kaitori_reviews WHERE row_id = ? ORDER BY id", (row_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["before_data"] = json.loads(item["before_data"])
            item["after_data"] = json.loads(item["after_data"])
            result.append(item)
        return result

    def add_match(self, row_id: str, catalog_card_id: str, confidence: float, matched_by: str) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO kaitori_matches (row_id, catalog_card_id, confidence, matched_by, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (row_id, catalog_card_id, confidence, matched_by, utc_now()),
        )
        self.connection.commit()

    def apply_match(self, row_id: str, result: Any) -> dict[str, Any]:
        current = self.get_row(row_id)
        if current is None:
            raise KeyError(f"row not found: {row_id}")
        now = utc_now()
        for candidate in result.candidates:
            self.add_match(row_id, candidate.card.id, candidate.confidence, candidate.matched_by)
        next_status = current["status"]
        if result.status == "needs_review" and next_status not in {"approved", "exported"}:
            next_status = "needs_review"
        self.connection.execute(
            "UPDATE kaitori_rows SET card_code = ?, status = ?, review_reason = CASE WHEN ? = 'needs_review' THEN ? ELSE review_reason END, updated_at = ? WHERE id = ?",
            (result.card_code, next_status, result.status, result.reason, now, row_id),
        )
        self.connection.commit()
        updated = self.get_row(row_id)
        assert updated is not None
        return updated

    def export_approved_rows(self, job_id: str) -> list[dict[str, Any]]:
        rows = self.list_rows(job_id=job_id, status="approved")
        if not rows:
            return []
        now = utc_now()
        self.connection.executemany("UPDATE kaitori_rows SET status = 'exported', updated_at = ? WHERE id = ?", [(now, row["id"]) for row in rows])
        self.connection.commit()
        return [self.get_row(row["id"]) for row in rows if self.get_row(row["id"]) is not None]

    def _counts_for_job(self, job_id: str) -> dict[str, int]:
        counts = _empty_counts()
        source_count = self.connection.execute("SELECT COUNT(*) FROM kaitori_job_sources WHERE job_id = ?", (job_id,)).fetchone()[0]
        counts["sources"] = int(source_count)
        counts["comments"] = int(self.connection.execute("""SELECT COUNT(*) FROM kaitori_comments c
            JOIN kaitori_job_sources js ON js.source_id = c.source_id WHERE js.job_id = ?""", (job_id,)).fetchone()[0])
        for row in self.connection.execute("""SELECT r.status, COUNT(*) AS count
            FROM kaitori_rows r JOIN kaitori_job_rows jr ON jr.row_id = r.id
            WHERE jr.job_id = ? GROUP BY r.status""", (job_id,)).fetchall():
            counts[row["status"]] = int(row["count"])
        for row in self.connection.execute("""SELECT r.listing_type, COUNT(*) AS count
            FROM kaitori_rows r JOIN kaitori_job_rows jr ON jr.row_id = r.id
            WHERE jr.job_id = ? GROUP BY r.listing_type""", (job_id,)).fetchall():
            if row["listing_type"] in {"sell", "buy", "trade", "unknown"}:
                counts[row["listing_type"]] = int(row["count"])
        counts["rows"] = sum(value for key, value in counts.items() if key in {"parsed", "needs_review", "approved", "rejected", "exported"})
        return counts


def _empty_counts() -> dict[str, int]:
    return {"sources": 0, "comments": 0, "rows": 0, "parsed": 0, "needs_review": 0, "approved": 0, "rejected": 0, "exported": 0, "sell": 0, "buy": 0, "trade": 0, "unknown": 0}


def _card_summary(card_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    sells = [row for row in rows if row.get("listing_type") == "sell"]
    buys = [row for row in rows if row.get("listing_type") == "buy"]
    trades = [row for row in rows if row.get("listing_type") == "trade"]
    sell_prices = [int(row.get("price_krw") or 0) for row in sells if int(row.get("price_krw") or 0) > 0]
    wanted_prices = [int(row.get("price_krw") or 0) for row in buys if int(row.get("price_krw") or 0) > 0]
    active_sources = {row.get("source_id") for row in rows if row.get("source_id")}
    buy_count = len(buys)
    sell_count = len(sells)
    if buy_count and sell_count == 0:
        demand_status = "hot_demand"
    elif buy_count >= 3 and buy_count > sell_count:
        demand_status = "hot_demand"
    elif buy_count and sell_count:
        demand_status = "balanced"
    elif sell_count:
        demand_status = "supply_heavy"
    else:
        demand_status = "unknown"
    score = round((buy_count * 1.0 * _recentness_factor(rows)) / max(sell_count, 1), 2)
    latest = max((str(row.get("posted_at") or "") for row in rows), default="")
    return {
        "card_key": card_key,
        "card_name_raw": next((str(row.get("card_name_raw") or "") for row in rows if row.get("card_name_raw")), card_key),
        "gallery_id": next((row.get("gallery_id") for row in rows if row.get("gallery_id")), ""),
        "sell_count": sell_count,
        "buy_count": buy_count,
        "trade_count": len(trades),
        "sell_price_median": _median(sell_prices),
        "sell_price_min": min(sell_prices) if sell_prices else None,
        "sell_price_max": max(sell_prices) if sell_prices else None,
        "wanted_price_median": _median(wanted_prices),
        "active_source_count": len(active_sources),
        "demand_score": score,
        "demand_status": demand_status,
        "latest_posted_at": latest,
        "evidence": f"최근 데이터 구매글 {buy_count}건 / 판매 매물 {sell_count}건",
    }


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2)


def _recentness_factor(rows: list[dict[str, Any]]) -> float:
    """Keep the first score explainable until a time-series model is introduced."""
    return 1.0 if rows else 0.0


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_storage_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_name_raw": row["card_name_raw"],
        "rarity": row["rarity"],
        "raw_price": row["raw_price"],
        "price_krw": row["price_krw"],
        "quantity": row["quantity"],
        "shipping_included": row["shipping_included"],
        "shipping_price_krw": row["shipping_price_krw"],
        "review_reason": row["review_reason"],
        "status": row["status"],
    }


def _allowed_review_fields(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {"card_name_raw", "card_name", "rarity", "raw_price", "price_krw", "quantity", "shipping_included", "shipping_price_krw", "review_reason"}
    result = {key: value for key, value in data.items() if key in allowed}
    if "card_name" in result and "card_name_raw" not in result:
        result["card_name_raw"] = result.pop("card_name")
    if "shipping_included" in result:
        value = result["shipping_included"]
        if value not in {"included", "separate", "unknown"}:
            raise ValueError("shipping_included must be included, separate, or unknown")
    return result
