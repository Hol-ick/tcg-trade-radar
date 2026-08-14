"""SQLite persistence for raw sources, extracted rows, jobs and reviews."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .contracts import CommentRecord, ExtractedRow, JobRequest, ReviewAction, SellerReviewAction, to_public_row, utc_now
from .normalization import normalize_listing_card_label
from .seller_risk import build_listing_fingerprint, build_post_family_id, build_seller_identity, detect_text_signals, risk_level


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
  post_status TEXT NOT NULL DEFAULT 'active',
  image_count INTEGER NOT NULL DEFAULT 0,
  body_characters INTEGER NOT NULL DEFAULT 0,
  raw_html TEXT,
  fetched_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  source_status TEXT NOT NULL DEFAULT 'active',
  seller_id TEXT,
  identity_scope TEXT NOT NULL DEFAULT 'post',
  post_family_id TEXT,
  listing_fingerprint TEXT,
  repost_of_source_id TEXT,
  is_repost INTEGER NOT NULL DEFAULT 0,
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
  price_krw_observed INTEGER,
  post_status TEXT NOT NULL DEFAULT 'active',
  price_status TEXT NOT NULL DEFAULT 'unknown',
  price_scope TEXT NOT NULL DEFAULT 'unknown',
  price_origin TEXT NOT NULL DEFAULT 'unknown',
  analysis_status TEXT NOT NULL DEFAULT 'needs_review',
  card_match_status TEXT NOT NULL DEFAULT 'unmatched',
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

CREATE TABLE IF NOT EXISTS kaitori_sellers (
  seller_id TEXT PRIMARY KEY,
  gallery_id TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  author_type TEXT NOT NULL DEFAULT 'unknown',
  identity_scope TEXT NOT NULL DEFAULT 'post',
  first_seen_at TEXT NOT NULL DEFAULT '',
  last_seen_at TEXT NOT NULL DEFAULT '',
  observed_post_count INTEGER NOT NULL DEFAULT 0,
  sell_post_count INTEGER NOT NULL DEFAULT 0,
  buy_post_count INTEGER NOT NULL DEFAULT 0,
  completed_post_count INTEGER NOT NULL DEFAULT 0,
  repost_count INTEGER NOT NULL DEFAULT 0,
  risk_score INTEGER NOT NULL DEFAULT 0,
  risk_level TEXT NOT NULL DEFAULT 'low',
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kaitori_risk_signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id TEXT NOT NULL REFERENCES kaitori_sellers(seller_id),
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  code TEXT NOT NULL,
  severity TEXT NOT NULL,
  score_delta INTEGER NOT NULL DEFAULT 0,
  message TEXT NOT NULL,
  evidence_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (seller_id, source_id, code)
);

CREATE TABLE IF NOT EXISTS kaitori_seller_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id TEXT NOT NULL REFERENCES kaitori_sellers(seller_id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  evidence_url TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

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
  demand_ratio REAL NOT NULL DEFAULT 0,
  sell_post_count INTEGER NOT NULL DEFAULT 0,
  buy_post_count INTEGER NOT NULL DEFAULT 0,
  sell_quantity INTEGER NOT NULL DEFAULT 0,
  buy_quantity INTEGER NOT NULL DEFAULT 0,
  recent_sell_count INTEGER NOT NULL DEFAULT 0,
  recent_buy_count INTEGER NOT NULL DEFAULT 0,
  quality_status TEXT NOT NULL DEFAULT 'needs_review',
  created_at TEXT NOT NULL,
  UNIQUE(snapshot_date, game_id, card_key)
);

CREATE INDEX IF NOT EXISTS kaitori_snapshot_game_date_idx ON kaitori_demand_snapshots(game_id, snapshot_date);
"""


class Repository:
    def __init__(self, path: Path | str) -> None:
        self._thread_lock = threading.RLock()
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

    def __getattribute__(self, name: str):
        """Serialize public repository calls sharing the server's SQLite connection."""
        attribute = object.__getattribute__(self, name)
        if name.startswith("_") or name in {"connection", "path"} or not callable(attribute):
            return attribute
        lock = object.__getattribute__(self, "_thread_lock")

        def synchronized(*args: Any, **kwargs: Any):
            with lock:
                return attribute(*args, **kwargs)

        return synchronized

    def _ensure_market_columns(self) -> None:
        existing = {row[1] for row in self.connection.execute("PRAGMA table_info(kaitori_rows)").fetchall()}
        additions = {
            "listing_type": "TEXT NOT NULL DEFAULT 'unknown'",
            "intent_confidence": "REAL NOT NULL DEFAULT 0",
            "price_type": "TEXT NOT NULL DEFAULT 'unknown'",
            "set_name": "TEXT NOT NULL DEFAULT ''",
            "condition_raw": "TEXT NOT NULL DEFAULT ''",
            "price_krw_observed": "INTEGER",
            "post_status": "TEXT NOT NULL DEFAULT 'active'",
            "price_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "price_scope": "TEXT NOT NULL DEFAULT 'unknown'",
            "price_origin": "TEXT NOT NULL DEFAULT 'unknown'",
            "analysis_status": "TEXT NOT NULL DEFAULT 'needs_review'",
            "card_match_status": "TEXT NOT NULL DEFAULT 'unmatched'",
        }
        for column, definition in additions.items():
            if column not in existing:
                self.connection.execute(f"ALTER TABLE kaitori_rows ADD COLUMN {column} {definition}")
        snapshot_existing = {row[1] for row in self.connection.execute("PRAGMA table_info(kaitori_demand_snapshots)").fetchall()}
        snapshot_additions = {
            "demand_ratio": "REAL NOT NULL DEFAULT 0",
            "sell_post_count": "INTEGER NOT NULL DEFAULT 0",
            "buy_post_count": "INTEGER NOT NULL DEFAULT 0",
            "sell_quantity": "INTEGER NOT NULL DEFAULT 0",
            "buy_quantity": "INTEGER NOT NULL DEFAULT 0",
            "recent_sell_count": "INTEGER NOT NULL DEFAULT 0",
            "recent_buy_count": "INTEGER NOT NULL DEFAULT 0",
            "quality_status": "TEXT NOT NULL DEFAULT 'needs_review'",
        }
        for column, definition in snapshot_additions.items():
            if column not in snapshot_existing:
                self.connection.execute(f"ALTER TABLE kaitori_demand_snapshots ADD COLUMN {column} {definition}")
        source_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(kaitori_sources)").fetchall()}
        if "source_status" not in source_columns:
            self.connection.execute("ALTER TABLE kaitori_sources ADD COLUMN source_status TEXT NOT NULL DEFAULT 'active'")
        if "author_name" not in source_columns:
            self.connection.execute("ALTER TABLE kaitori_sources ADD COLUMN author_name TEXT NOT NULL DEFAULT ''")
        if "author_type" not in source_columns:
            self.connection.execute("ALTER TABLE kaitori_sources ADD COLUMN author_type TEXT NOT NULL DEFAULT 'unknown'")
        source_additions = {
            "post_status": "TEXT NOT NULL DEFAULT 'active'",
            "image_count": "INTEGER NOT NULL DEFAULT 0",
            "body_characters": "INTEGER NOT NULL DEFAULT 0",
            "seller_id": "TEXT",
            "identity_scope": "TEXT NOT NULL DEFAULT 'post'",
            "post_family_id": "TEXT",
            "listing_fingerprint": "TEXT",
            "repost_of_source_id": "TEXT",
            "is_repost": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in source_additions.items():
            if column not in source_columns:
                self.connection.execute(f"ALTER TABLE kaitori_sources ADD COLUMN {column} {definition}")
        self.connection.execute("CREATE INDEX IF NOT EXISTS kaitori_sources_seller_idx ON kaitori_sources(seller_id, posted_at)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS kaitori_risk_seller_idx ON kaitori_risk_signals(seller_id, status, id)")

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
                json.dumps({"gallery_url": request.gallery_url, "max_posts": request.max_posts, "max_pages": request.max_pages, "delay": request.delay, "fetch_concurrency": request.fetch_concurrency, "max_retries": request.max_retries, "keep_raw": request.keep_raw, "review_unmatched": request.review_unmatched, "subjects": list(request.subjects), "cutoff_at": request.cutoff_at}, ensure_ascii=False),
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

    def find_latest_job(self, gallery_id: str, since: str | None, until: str | None, cutoff_at: str | None) -> dict[str, Any] | None:
        """Find the newest backfill job with the same collection boundary."""
        rows = self.connection.execute(
            """
            SELECT * FROM kaitori_jobs
            WHERE gallery_id = ? AND since IS ? AND until IS ?
            ORDER BY created_at DESC, id DESC
            """,
            (gallery_id, since, until),
        ).fetchall()
        for row in rows:
            try:
                config = json.loads(row["config_json"] or "{}")
            except json.JSONDecodeError:
                config = {}
            if config.get("cutoff_at") == cutoff_at:
                return dict(row)
        return None

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
        post_id = str(source.get("post_id") or parse_qs(urlparse(post_url).query).get("no", [""])[0])
        identity = build_seller_identity(
            str(source.get("gallery_id") or ""),
            str(source.get("author_name") or ""),
            str(source.get("author_type") or "unknown"),
            source_id,
        )
        post_family_id = build_post_family_id(str(source.get("gallery_id") or ""), post_url, post_id)
        values = (
            source_id,
            str(source.get("gallery_id") or ""),
            post_id,
            post_url,
            str(source.get("title") or ""),
            str(source.get("posted_at") or ""),
            str(source.get("author_name") or ""),
            str(source.get("author_type") or "unknown"),
            str(source.get("post_status") or "active"),
            max(0, int(source.get("image_count") or 0)),
            max(0, int(source.get("body_characters") or 0)),
            raw_html if source.get("keep_raw", True) else None,
            str(source.get("fetched_at") or utc_now()),
            content_hash,
            str(source.get("source_status") or "active"),
            identity.seller_id,
            identity.identity_scope,
            post_family_id,
        )
        cursor = self.connection.execute(
            """INSERT OR IGNORE INTO kaitori_sources
            (id, gallery_id, post_id, post_url, title, posted_at, author_name, author_type, post_status, image_count, body_characters, raw_html, fetched_at, content_hash, source_status, seller_id, identity_scope, post_family_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
        self.connection.execute(
            """UPDATE kaitori_sources
               SET author_name = CASE WHEN ? <> '' THEN ? ELSE author_name END,
                   author_type = CASE WHEN ? <> 'unknown' THEN ? ELSE author_type END,
                   post_status = ?, image_count = ?, body_characters = ?, seller_id = ?, identity_scope = ?, post_family_id = ?
               WHERE id = ?""",
            (values[6], values[6], values[7], values[7], values[8], values[9], values[10], values[15], values[16], values[17], source_id),
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
        now = utc_now()
        self.connection.execute(
            "INSERT OR IGNORE INTO kaitori_job_sources (job_id, source_id, created_at) VALUES (?, ?, ?)",
            (job_id, source_id, now),
        )
        self.connection.execute(
            """INSERT OR IGNORE INTO kaitori_job_rows (job_id, row_id, created_at)
               SELECT ?, id, ? FROM kaitori_rows WHERE source_id = ?""",
            (job_id, now, source_id),
        )
        self.connection.commit()

    def find_source_for_post(self, gallery_id: str, post_url: str) -> dict[str, Any] | None:
        parsed = urlparse(post_url)
        post_id = parse_qs(parsed.query).get("no", [""])[0]
        if not post_id:
            parts = [part for part in parsed.path.split("/") if part]
            post_id = parts[-1] if parts and parts[-1].isdigit() else ""
        row = self.connection.execute(
            """SELECT * FROM kaitori_sources
               WHERE gallery_id = ? AND (post_url = ? OR (? <> '' AND post_id = ?))
               ORDER BY fetched_at DESC, id DESC
               LIMIT 1""",
            (gallery_id, post_url, post_id, post_id),
        ).fetchone()
        return dict(row) if row else None

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
                 price_krw_observed, post_status, price_status, price_scope, price_origin, analysis_status, card_match_status,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    public["price_krw"] if public.get("price_status") in {"exact", "estimated"} and public.get("price_krw") not in (None, "", 0) else None,
                    public.get("post_status") or "active",
                    public.get("price_status") or "unknown",
                    public.get("price_scope") or "unknown",
                    public.get("price_origin") or "unknown",
                    public.get("analysis_status") or "needs_review",
                    public.get("card_match_status") or "unmatched",
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

    def reprocess_quality(self) -> dict[str, int]:
        """Backfill quality metadata for rows collected before the quality layer existed."""
        from .html import parse_html
        from .preprocessing import analysis_status, append_quality_reason, classify_post, classify_price, fallback_card_match

        sources = self.connection.execute("SELECT * FROM kaitori_sources ORDER BY id").fetchall()
        source_count = 0
        row_count = 0
        for source in sources:
            source_data = dict(source)
            raw_html = source_data.get("raw_html") or ""
            rows = self.connection.execute("SELECT * FROM kaitori_rows WHERE source_id = ?", (source_data["id"],)).fetchall()
            if raw_html:
                document, _ = parse_html(raw_html, source_data["post_url"])
                post_quality = classify_post(
                    document.get("title", source_data.get("title", "")),
                    document.get("body", ""),
                    image_count=int(document.get("image_count") or 0),
                    row_count=len(rows),
                )
                self.connection.execute(
                    """UPDATE kaitori_sources SET post_status = ?, image_count = ?, body_characters = ?,
                       title = CASE WHEN ? <> '' THEN ? ELSE title END,
                       posted_at = CASE WHEN ? <> '' THEN ? ELSE posted_at END
                       WHERE id = ?""",
                    (post_quality.status, post_quality.image_count, post_quality.body_characters,
                     document.get("title", ""), document.get("title", ""), document.get("posted_at", ""), document.get("posted_at", ""), source_data["id"]),
                )
            else:
                post_quality = classify_post(source_data.get("title", ""), "", image_count=int(source_data.get("image_count") or 0), row_count=len(rows))
            for row in rows:
                row_data = dict(row)
                price_status, price_scope, price_origin = classify_price(
                    raw_price=str(row_data.get("raw_price") or ""),
                    price_unit=str(row_data.get("price_unit") or ""),
                    quantity=int(row_data.get("quantity") or 1),
                    raw_line=str(row_data.get("raw_line") or ""),
                    post_status=post_quality.status,
                )
                quality = analysis_status(
                    post_status=post_quality.status,
                    listing_type=str(row_data.get("listing_type") or "unknown"),
                    card_name=str(row_data.get("card_name_raw") or ""),
                    price_status=price_status,
                    price_scope=price_scope,
                )
                observed_price = int(row_data["price_krw"]) if row_data.get("price_krw") not in (None, 0) and price_status in {"exact", "estimated"} else None
                next_status = row_data.get("status") or "needs_review"
                if next_status not in {"approved", "exported"}:
                    next_status = "parsed" if quality == "usable" and not row_data.get("review_reason") else "needs_review"
                reason = append_quality_reason(
                    str(row_data.get("review_reason") or ""),
                    post_status=post_quality.status,
                    price_status=price_status,
                    price_scope=price_scope,
                    analysis=quality,
                )
                self.connection.execute(
                    """UPDATE kaitori_rows SET price_krw_observed = ?, post_status = ?, price_status = ?,
                       price_scope = ?, price_origin = ?, analysis_status = ?, card_match_status = ?,
                       review_reason = ?, status = ?, updated_at = ? WHERE id = ?""",
                    (observed_price, post_quality.status, price_status, price_scope, price_origin, quality,
                     fallback_card_match(str(row_data.get("card_name_raw") or "")), reason, next_status, utc_now(), row_data["id"]),
                )
                row_count += 1
            source_count += 1
        self.connection.commit()
        return {"sources": source_count, "rows": row_count}

    def analyze_source_risk(self, source_id: str) -> dict[str, Any]:
        """Link a source to a seller and rebuild its deterministic review signals."""
        source = self.get_source(source_id)
        if source is None:
            raise KeyError(f"source not found: {source_id}")
        identity = build_seller_identity(source["gallery_id"], source.get("author_name", ""), source.get("author_type", "unknown"), source_id)
        post_family_id = source.get("post_family_id") or build_post_family_id(source["gallery_id"], source["post_url"], source.get("post_id", ""))
        rows = [dict(row) for row in self.connection.execute("SELECT * FROM kaitori_rows WHERE source_id = ?", (source_id,)).fetchall()]
        fingerprint = build_listing_fingerprint(source, rows)
        previous = self.connection.execute(
            """SELECT id, post_status, posted_at FROM kaitori_sources
               WHERE seller_id = ? AND listing_fingerprint = ? AND id <> ?
               ORDER BY posted_at DESC LIMIT 1""",
            (identity.seller_id, fingerprint, source_id),
        ).fetchone()
        completed_revision = self.connection.execute(
            """SELECT id FROM kaitori_sources
               WHERE post_family_id = ? AND id <> ? AND post_status = 'completed'
               LIMIT 1""",
            (post_family_id, source_id),
        ).fetchone()
        is_repost = int(previous is not None or completed_revision is not None)
        repost_of = (previous["id"] if previous else completed_revision["id"] if completed_revision else None)
        now = utc_now()
        self.connection.execute(
            """UPDATE kaitori_sources SET seller_id = ?, identity_scope = ?, post_family_id = ?,
               listing_fingerprint = ?, repost_of_source_id = ?, is_repost = ? WHERE id = ?""",
            (identity.seller_id, identity.identity_scope, post_family_id, fingerprint, repost_of, is_repost, source_id),
        )
        self.connection.execute(
            """INSERT OR IGNORE INTO kaitori_sellers
               (seller_id, gallery_id, display_name, author_type, identity_scope, first_seen_at, last_seen_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (identity.seller_id, source["gallery_id"], identity.display_name, identity.author_type, identity.identity_scope, source.get("posted_at", ""), source.get("posted_at", ""), now, now),
        )
        self.connection.execute(
            """UPDATE kaitori_sellers SET display_name = ?, author_type = ?, identity_scope = ?,
               first_seen_at = CASE WHEN first_seen_at = '' OR first_seen_at > ? THEN ? ELSE first_seen_at END,
               last_seen_at = CASE WHEN last_seen_at < ? THEN ? ELSE last_seen_at END,
               updated_at = ? WHERE seller_id = ?""",
            (identity.display_name, identity.author_type, identity.identity_scope, source.get("posted_at", ""), source.get("posted_at", ""), source.get("posted_at", ""), source.get("posted_at", ""), now, identity.seller_id),
        )
        text = " ".join([str(source.get("title") or ""), str(source.get("raw_html") or "")])
        signals = detect_text_signals(text)
        if is_repost:
            signals.append({"code": "repeated_listing", "severity": "medium", "score_delta": 20, "message": "같은 판매자의 유사 매물이 반복 등록되었습니다."})
        if completed_revision is not None:
            signals.append({"code": "completed_repost", "severity": "medium", "score_delta": 20, "message": "거래완료 게시글과 같은 게시글 계열이 다시 관찰되었습니다."})
        if source.get("post_status") == "image_only" and not rows:
            signals.append({"code": "image_only_listing", "severity": "low", "score_delta": 8, "message": "본문 가격·카드명이 없어 사진 확인이 필요한 매물입니다."})
        recent_posts = self.connection.execute(
            """SELECT COUNT(*) FROM kaitori_sources WHERE seller_id = ?
               AND posted_at >= datetime(?, '-1 day')""",
            (identity.seller_id, source.get("posted_at") or now),
        ).fetchone()[0]
        if int(recent_posts) >= 5:
            signals.append({"code": "high_post_velocity", "severity": "low", "score_delta": 10, "message": "짧은 기간에 여러 게시글이 등록되어 활동량 확인이 필요합니다."})
        for signal in signals:
            self.connection.execute(
                """INSERT INTO kaitori_risk_signals
                   (seller_id, source_id, code, severity, score_delta, message, evidence_text, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                   ON CONFLICT(seller_id, source_id, code) DO UPDATE SET severity = excluded.severity,
                     score_delta = excluded.score_delta, message = excluded.message, evidence_text = excluded.evidence_text,
                     updated_at = excluded.updated_at""",
                (identity.seller_id, source_id, signal["code"], signal["severity"], signal["score_delta"], signal["message"], signal["message"], now, now),
            )
        stats = self.connection.execute(
            """SELECT COUNT(*) AS posts,
               SUM(CASE WHEN post_status = 'completed' THEN 1 ELSE 0 END) AS completed,
               SUM(CASE WHEN is_repost = 1 THEN 1 ELSE 0 END) AS reposts
               FROM kaitori_sources WHERE seller_id = ?""",
            (identity.seller_id,),
        ).fetchone()
        listing_stats = self.connection.execute(
            """SELECT COUNT(DISTINCT CASE WHEN r.listing_type = 'sell' THEN r.source_id END) AS sells,
               COUNT(DISTINCT CASE WHEN r.listing_type = 'buy' THEN r.source_id END) AS buys
               FROM kaitori_rows r JOIN kaitori_sources s ON s.id = r.source_id WHERE s.seller_id = ?""",
            (identity.seller_id,),
        ).fetchone()
        score = self.connection.execute(
            "SELECT COALESCE(SUM(score_delta), 0) FROM kaitori_risk_signals WHERE seller_id = ? AND status = 'open'",
            (identity.seller_id,),
        ).fetchone()[0]
        self.connection.execute(
            """UPDATE kaitori_sellers SET observed_post_count = ?, sell_post_count = ?, buy_post_count = ?,
               completed_post_count = ?, repost_count = ?, risk_score = ?, risk_level = ?, updated_at = ? WHERE seller_id = ?""",
            (int(stats["posts"] or 0), int(listing_stats["sells"] or 0), int(listing_stats["buys"] or 0), int(stats["completed"] or 0), int(stats["reposts"] or 0), min(100, int(score)), risk_level(int(score)), now, identity.seller_id),
        )
        self.connection.commit()
        seller = self.get_seller(identity.seller_id)
        assert seller is not None
        return seller

    def reprocess_seller_risk(self) -> dict[str, int]:
        source_ids = [row[0] for row in self.connection.execute("SELECT id FROM kaitori_sources ORDER BY id").fetchall()]
        for source_id in source_ids:
            self.analyze_source_risk(source_id)
        return {"sources": len(source_ids), "sellers": int(self.connection.execute("SELECT COUNT(*) FROM kaitori_sellers").fetchone()[0])}

    def list_sellers(self, *, game_id: str = "", query_text: str = "", risk_level_filter: str = "", limit: int = 200) -> list[dict[str, Any]]:
        query = """SELECT s.*, COUNT(DISTINCT rs.id) AS open_signal_count
                   FROM kaitori_sellers s LEFT JOIN kaitori_risk_signals rs
                   ON rs.seller_id = s.seller_id AND rs.status = 'open' WHERE 1=1"""
        values: list[Any] = []
        if game_id:
            query += " AND s.gallery_id = ?"
            values.append(game_id)
        if query_text.strip():
            query += " AND s.display_name LIKE ?"
            values.append(f"%{query_text.strip()}%")
        if risk_level_filter in {"low", "medium", "high"}:
            query += " AND s.risk_level = ?"
            values.append(risk_level_filter)
        query += " GROUP BY s.seller_id ORDER BY s.risk_score DESC, s.last_seen_at DESC LIMIT ?"
        values.append(max(1, min(int(limit), 1000)))
        return [dict(row) for row in self.connection.execute(query, values).fetchall()]

    def get_seller(self, seller_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM kaitori_sellers WHERE seller_id = ?", (seller_id,)).fetchone()
        if row is None:
            return None
        seller = dict(row)
        seller["sources"] = [dict(item) for item in self.connection.execute(
            """SELECT id, post_url, title, posted_at, post_status, is_repost, repost_of_source_id
               FROM kaitori_sources WHERE seller_id = ? ORDER BY posted_at DESC, id DESC LIMIT 200""", (seller_id,)
        ).fetchall()]
        seller["signals"] = self.list_risk_signals(seller_id=seller_id, limit=500)
        return seller

    def list_risk_signals(self, *, seller_id: str = "", severity: str = "", status: str = "", limit: int = 200) -> list[dict[str, Any]]:
        query = "SELECT * FROM kaitori_risk_signals WHERE 1=1"
        values: list[Any] = []
        if seller_id:
            query += " AND seller_id = ?"
            values.append(seller_id)
        if severity in {"low", "medium", "high"}:
            query += " AND severity = ?"
            values.append(severity)
        if status in {"open", "dismissed"}:
            query += " AND status = ?"
            values.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        values.append(max(1, min(int(limit), 1000)))
        return [dict(row) for row in self.connection.execute(query, values).fetchall()]

    def review_seller(self, seller_id: str, action: SellerReviewAction) -> dict[str, Any]:
        if self.get_seller(seller_id) is None:
            raise KeyError(f"seller not found: {seller_id}")
        now = utc_now()
        review_status = {"watch": "watching", "clear": "unreviewed", "mark_safe": "safe", "confirm_risk": "confirmed", "note": "noted"}[action.action]
        self.connection.execute(
            "INSERT INTO kaitori_seller_reviews (seller_id, actor, action, note, evidence_url, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (seller_id, action.actor, action.action, action.note, action.evidence_url, now),
        )
        if action.action == "clear":
            self.connection.execute("UPDATE kaitori_risk_signals SET status = 'dismissed', updated_at = ? WHERE seller_id = ?", (now, seller_id))
        self.connection.execute("UPDATE kaitori_sellers SET review_status = ?, updated_at = ? WHERE seller_id = ?", (review_status, now, seller_id))
        if action.action == "clear":
            self.connection.execute("UPDATE kaitori_sellers SET risk_score = 0, risk_level = 'low' WHERE seller_id = ?", (seller_id,))
        self.connection.commit()
        return self.get_seller(seller_id) or {}

    def list_rows(self, *, job_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT r.*, s.gallery_id, s.post_url, s.title AS post_title, s.posted_at, s.raw_html, s.author_name, s.author_type,
                          s.seller_id, s.identity_scope, s.post_family_id, s.is_repost,
                          sl.display_name AS seller_display_name, sl.risk_score AS seller_risk_score,
                          sl.risk_level AS seller_risk_level, sl.review_status AS seller_review_status
                   FROM kaitori_rows r
                   JOIN kaitori_sources s ON s.id = r.source_id
                   LEFT JOIN kaitori_sellers sl ON sl.seller_id = s.seller_id
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
                   s.posted_at, s.source_status, s.author_name, s.author_type, s.seller_id,
                   s.identity_scope, s.post_family_id, s.is_repost,
                   sl.display_name AS seller_display_name, sl.risk_score AS seller_risk_score,
                   sl.risk_level AS seller_risk_level, sl.review_status AS seller_review_status
                   FROM kaitori_rows r
                   JOIN kaitori_sources s ON s.id = r.source_id
                   LEFT JOIN kaitori_sellers sl ON sl.seller_id = s.seller_id
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

    def list_card_listings(
        self,
        card_key: str,
        *,
        game_id: str = "",
        since: str | None = None,
        until: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return raw listings belonging to a normalized card summary key."""
        key = str(card_key or "").strip().casefold()
        rows = self.list_market_listings(game_id=game_id, since=since, until=until, limit=5000)
        return [
            row for row in rows
            if str(row.get("card_code") or "").strip().replace("_", "-").casefold() == key
            or normalize_listing_card_label(str(row.get("card_name_raw") or ""), str(row.get("listing_type") or "")).casefold() == key
        ][: max(1, min(int(limit), 1000))]

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
        rows = self.list_market_listings(query_text="", game_id=game_id, listing_type=listing_type, since=since, until=until, limit=5000)
        if query_text.strip():
            needle = query_text.strip().casefold()
            normalized_needle = normalize_listing_card_label(query_text).casefold()
            rows = [
                row for row in rows
                if needle in str(row.get("card_name_raw") or "").casefold()
                or needle in str(row.get("card_code") or "").casefold()
                or (normalized_needle and normalized_needle in normalize_listing_card_label(str(row.get("card_name_raw") or ""), str(row.get("listing_type") or "")).casefold())
            ]
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            code = str(row.get("card_code") or "").strip().upper().replace("_", "-")
            normalized_name = normalize_listing_card_label(str(row.get("card_name_raw") or ""), str(row.get("listing_type") or ""))
            key = code or normalized_name
            if key:
                groups.setdefault(key, []).append(row)
        result = [_card_summary(key, values, reference_date=until or date.today().isoformat()) for key, values in groups.items()]
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
                active_source_count, demand_score, demand_ratio, sell_post_count, buy_post_count,
                sell_quantity, buy_quantity, recent_sell_count, recent_buy_count, quality_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (snapshot_date, game_id, summary["card_key"], summary["card_name_raw"], summary["sell_count"], summary["buy_count"], summary["trade_count"],
                 summary["sell_price_median"], summary["sell_price_min"], summary["sell_price_max"], summary["wanted_price_median"],
                 summary["active_source_count"], summary["demand_score"], summary["demand_ratio"], summary["sell_post_count"], summary["buy_post_count"],
                 summary["sell_quantity"], summary["buy_quantity"], summary["recent_sell_count"], summary["recent_buy_count"], summary["quality_status"], utc_now()),
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
        next_match_status = "matched" if result.status == "matched" and result.card_code else "candidate" if result.candidates else "unmatched"
        next_analysis_status = current.get("analysis_status", "needs_review")
        if next_match_status == "matched" and next_analysis_status == "needs_review" and current.get("price_scope") == "per_card" and current.get("price_status") in {"exact", "estimated"}:
            next_analysis_status = "usable" if current.get("post_status", "active") == "active" else "context_only"
        self.connection.execute(
            """UPDATE kaitori_rows SET card_code = ?, status = ?, card_match_status = ?, analysis_status = ?,
               review_reason = CASE WHEN ? = 'needs_review' THEN ? ELSE review_reason END, updated_at = ? WHERE id = ?""",
            (result.card_code, next_status, next_match_status, next_analysis_status, result.status, result.reason, now, row_id),
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


def _card_summary(card_key: str, rows: list[dict[str, Any]], *, reference_date: str | None = None) -> dict[str, Any]:
    sells = [row for row in rows if row.get("listing_type") == "sell" and _include_current_listing(row)]
    buys = [row for row in rows if row.get("listing_type") == "buy" and _include_current_listing(row)]
    trades = [row for row in rows if row.get("listing_type") == "trade" and _include_current_listing(row)]
    sell_prices = [_observed_price(row) for row in sells if _usable_price(row)]
    wanted_prices = [_observed_price(row) for row in buys if _usable_price(row)]
    active_sources = {row.get("source_id") for row in [*sells, *buys, *trades] if row.get("source_id")}
    buy_count = len(buys)
    sell_count = len(sells)
    reference_day = _as_date(reference_date) or date.today()
    recent_buys = [row for row in buys if _recentness_weight(row.get("posted_at"), reference_day) >= 1.0]
    recent_sells = [row for row in sells if _recentness_weight(row.get("posted_at"), reference_day) >= 1.0]
    weighted_buy = sum(_recentness_weight(row.get("posted_at"), reference_day) for row in buys)
    weighted_sell = sum(_recentness_weight(row.get("posted_at"), reference_day) for row in sells)
    if buy_count and not recent_buys:
        demand_status = "stale_demand"
    elif buy_count and sell_count == 0:
        demand_status = "hot_demand"
    elif buy_count >= 3 and buy_count > sell_count:
        demand_status = "hot_demand"
    elif buy_count and sell_count:
        demand_status = "balanced"
    elif sell_count:
        demand_status = "supply_heavy"
    else:
        demand_status = "unknown"
    score = round(weighted_buy / max(weighted_sell, 1.0), 2)
    demand_ratio = round(buy_count / max(sell_count, 1), 2)
    sell_posts = {row.get("source_id") or row.get("post_url") for row in sells}
    buy_posts = {row.get("source_id") or row.get("post_url") for row in buys}
    quality_status = "needs_review" if any(row.get("analysis_status") in {"needs_review", "context_only"} or row.get("status") == "needs_review" or row.get("listing_type") == "unknown" for row in rows) else "observed"
    if len(active_sources) < 2 and quality_status == "observed":
        quality_status = "low_sample"
    latest = max((str(row.get("posted_at") or "") for row in rows), default="")
    normalized_name = next((normalize_listing_card_label(str(row.get("card_name_raw") or ""), str(row.get("listing_type") or "")) for row in rows if row.get("card_name_raw")), card_key)
    return {
        "card_key": card_key,
        "card_name_raw": next((str(row.get("card_name_raw") or "") for row in rows if row.get("card_name_raw")), card_key),
        "card_name_normalized": normalized_name,
        "gallery_id": next((row.get("gallery_id") for row in rows if row.get("gallery_id")), ""),
        "sell_count": sell_count,
        "buy_count": buy_count,
        "trade_count": len(trades),
        "sell_post_count": len({value for value in sell_posts if value}),
        "buy_post_count": len({value for value in buy_posts if value}),
        "sell_quantity": sum(max(1, int(row.get("quantity") or 1)) for row in sells),
        "buy_quantity": sum(max(1, int(row.get("quantity") or 1)) for row in buys),
        "recent_sell_count": len(recent_sells),
        "recent_buy_count": len(recent_buys),
        "sell_price_median": _median(sell_prices),
        "sell_price_min": min(sell_prices) if sell_prices else None,
        "sell_price_max": max(sell_prices) if sell_prices else None,
        "wanted_price_median": _median(wanted_prices),
        "active_source_count": len(active_sources),
        "demand_score": score,
        "demand_ratio": demand_ratio,
        "demand_status": demand_status,
        "quality_status": quality_status,
        "latest_posted_at": latest,
        "evidence": f"최근 구매글 {buy_count}건(최근 {len(recent_buys)}건) / 판매 매물 {sell_count}건 / 게시글 {len(active_sources)}개",
        "usable_price_count": len(sell_prices),
        "context_only_count": sum(1 for row in rows if row.get("analysis_status") == "context_only"),
        "review_count": sum(1 for row in rows if row.get("analysis_status") == "needs_review"),
    }


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2)


def _as_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _recentness_weight(value: Any, reference_day: date) -> float:
    posted_day = _as_date(value)
    if posted_day is None:
        return 0.0
    age = max(0, (reference_day - posted_day).days)
    if age <= 7:
        return 1.0
    if age <= 30:
        return 0.5
    return 0.25


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_storage_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_name_raw": row["card_name_raw"],
        "rarity": row["rarity"],
        "raw_price": row["raw_price"],
        "price_krw": _observed_price(row),
        "quantity": row["quantity"],
        "shipping_included": row["shipping_included"],
        "shipping_price_krw": row["shipping_price_krw"],
        "review_reason": row["review_reason"],
        "status": row["status"],
        "post_status": row.get("post_status", "active"),
        "price_status": row.get("price_status", "unknown"),
        "price_scope": row.get("price_scope", "unknown"),
        "price_origin": row.get("price_origin", "unknown"),
        "analysis_status": row.get("analysis_status", "needs_review"),
        "card_match_status": row.get("card_match_status", "unmatched"),
    }


def _allowed_review_fields(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {"card_name_raw", "card_name", "rarity", "raw_price", "price_krw", "quantity", "shipping_included", "shipping_price_krw", "review_reason", "price_status", "price_scope", "analysis_status", "card_match_status"}
    result = {key: value for key, value in data.items() if key in allowed}
    if "card_name" in result and "card_name_raw" not in result:
        result["card_name_raw"] = result.pop("card_name")
    if "shipping_included" in result:
        value = result["shipping_included"]
        if value not in {"included", "separate", "unknown"}:
            raise ValueError("shipping_included must be included, separate, or unknown")
    return result


def _observed_price(row: dict[str, Any]) -> int | None:
    observed = row.get("price_krw_observed")
    if observed not in (None, "", 0):
        return int(observed)
    status = row.get("price_status")
    value = row.get("price_krw")
    if status in {"missing", "removed"} or value in (None, "", 0):
        return None
    return int(value)


def _usable_price(row: dict[str, Any]) -> bool:
    return row.get("analysis_status") == "usable" and row.get("price_scope") == "per_card" and _observed_price(row) is not None


def _include_current_listing(row: dict[str, Any]) -> bool:
    if row.get("post_status", "active") != "active" or row.get("analysis_status", "usable") in {"context_only", "excluded"}:
        return False
    if row.get("listing_type") in {"sell", "trade"} and row.get("price_scope") != "per_card":
        return False
    return True
