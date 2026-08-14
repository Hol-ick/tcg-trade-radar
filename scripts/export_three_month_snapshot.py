"""Export a compact, public collection snapshot from the collector database.

The live SQLite database keeps raw HTML for auditability. This exporter
publishes the structured post, listing, comment, and job-log data without the
large raw HTML column, so a snapshot can be tracked in a normal Git repository.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAMES = ("tcggame", "onepiececardgame", "pokemoncardgame", "digimontcg", "vg")
WATERMARK_PATH = ROOT / "config" / "collection_watermark.json"

POST_FIELDS = (
    "job_id",
    "gallery_id",
    "source_id",
    "post_id",
    "post_url",
    "title",
    "posted_at",
    "author_name",
    "author_type",
    "post_status",
    "source_status",
    "image_count",
    "body_characters",
    "fetched_at",
    "content_hash",
    "seller_id",
    "identity_scope",
    "post_family_id",
    "listing_fingerprint",
    "repost_of_source_id",
    "is_repost",
)

LISTING_FIELDS = (
    "job_id",
    "gallery_id",
    "source_id",
    "row_id",
    "post_url",
    "post_title",
    "posted_at",
    "author_name",
    "author_type",
    "card_name_raw",
    "card_code",
    "rarity",
    "raw_price",
    "price_krw",
    "price_unit",
    "quantity",
    "shipping_included",
    "shipping_price_krw",
    "status",
    "review_reason",
    "raw_line",
    "listing_type",
    "intent_confidence",
    "price_type",
    "set_name",
    "condition_raw",
    "price_krw_observed",
    "post_status",
    "price_status",
    "price_scope",
    "price_origin",
    "analysis_status",
    "card_match_status",
    "created_at",
    "updated_at",
)

COMMENT_FIELDS = (
    "job_id",
    "gallery_id",
    "source_id",
    "post_url",
    "comment_id",
    "parent_id",
    "author_name",
    "author_type",
    "body",
    "posted_at",
    "created_at",
)

LOG_FIELDS = ("job_id", "created_at", "level", "step", "message", "details")


def _rows(connection: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(query, tuple(params))]


def _selected_jobs(connection: sqlite3.Connection, since: str, until: str, job_ids: list[str]) -> list[dict[str, Any]]:
    if job_ids:
        marks = ",".join("?" for _ in job_ids)
        query = f"SELECT * FROM kaitori_jobs WHERE id IN ({marks}) ORDER BY created_at, id"
        return _rows(connection, query, job_ids)
    return _rows(
        connection,
        """
        SELECT * FROM kaitori_jobs
        WHERE since = ? AND until = ? AND gallery_id IN (?, ?, ?, ?, ?)
        ORDER BY created_at, id
        """,
        (since, until, *DEFAULT_GAMES),
    )


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _write_jsonl(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps({field: row.get(field) for field in fields}, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def export_snapshot(db_path: Path, output_root: Path, since: str, until: str, cutoff_at: str, job_ids: list[str]) -> dict[str, Any]:
    output = output_root / f"{since}_{until}"
    output.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        jobs = _selected_jobs(connection, since, until, job_ids)
        selected_ids = [job["id"] for job in jobs]
        if not selected_ids:
            raise ValueError("no matching collection jobs were found")
        marks = ",".join("?" for _ in selected_ids)

        posts = _rows(
            connection,
            f"""
            SELECT js.job_id, s.gallery_id, s.id AS source_id, s.post_id, s.post_url,
                   s.title, s.posted_at, s.author_name, s.author_type, s.post_status,
                   s.source_status, s.image_count, s.body_characters, s.fetched_at,
                   s.content_hash, s.seller_id, s.identity_scope, s.post_family_id,
                   s.listing_fingerprint, s.repost_of_source_id, s.is_repost
            FROM kaitori_job_sources js
            JOIN kaitori_sources s ON s.id = js.source_id
            WHERE js.job_id IN ({marks}) AND s.posted_at <> '' AND s.posted_at <= ?
            ORDER BY s.gallery_id, s.posted_at, s.post_id
            """,
            (*selected_ids, cutoff_at),
        )
        listings = _rows(
            connection,
            f"""
            SELECT jr.job_id, s.gallery_id, r.source_id, r.id AS row_id,
                   s.post_url, s.title AS post_title, s.posted_at,
                   s.author_name, s.author_type, r.card_name_raw, r.card_code,
                   r.rarity, r.raw_price, r.price_krw, r.price_unit, r.quantity,
                   r.shipping_included, r.shipping_price_krw, r.status,
                   r.review_reason, r.raw_line, r.listing_type, r.intent_confidence,
                   r.price_type, r.set_name, r.condition_raw, r.price_krw_observed,
                   r.post_status, r.price_status, r.price_scope, r.price_origin,
                   r.analysis_status, r.card_match_status, r.created_at, r.updated_at
            FROM kaitori_job_rows jr
            JOIN kaitori_rows r ON r.id = jr.row_id
            JOIN kaitori_sources s ON s.id = r.source_id
            WHERE jr.job_id IN ({marks}) AND s.posted_at <> '' AND s.posted_at <= ?
            ORDER BY s.gallery_id, s.posted_at, r.id
            """,
            (*selected_ids, cutoff_at),
        )
        comments = _rows(
            connection,
            f"""
            SELECT js.job_id, c.gallery_id, c.source_id, c.post_url, c.comment_id,
                   c.parent_id, c.author_name, c.author_type, c.body,
                   c.posted_at, c.created_at
            FROM kaitori_comments c
            JOIN kaitori_job_sources js ON js.source_id = c.source_id
            JOIN kaitori_sources s ON s.id = c.source_id
            WHERE js.job_id IN ({marks}) AND s.posted_at <> '' AND s.posted_at <= ?
            ORDER BY c.gallery_id, c.posted_at, c.comment_id
            """,
            (*selected_ids, cutoff_at),
        )
        logs = _rows(
            connection,
            f"SELECT job_id, created_at, level, step, message, details FROM kaitori_job_logs WHERE job_id IN ({marks}) ORDER BY id",
            selected_ids,
        )
        job_summaries: list[dict[str, Any]] = []
        for job in jobs:
            job_id = job["id"]
            job_posts = [row for row in posts if row["job_id"] == job_id and row.get("posted_at")]
            job_summaries.append(
                {
                    "id": job_id,
                    "gallery_id": job["gallery_id"],
                    "subject": job["subject"],
                    "since": job["since"],
                    "until": job["until"],
                    "state": job["state"],
                    "created_at": job["created_at"],
                    "finished_at": job["finished_at"],
                    "error_message": job["error_message"],
                    "source_count": len(job_posts),
                    "listing_count": sum(row["job_id"] == job_id for row in listings),
                    "comment_count": sum(row["job_id"] == job_id for row in comments),
                    "log_count": sum(row["job_id"] == job_id for row in logs),
                    "min_posted_at": min((row["posted_at"] for row in job_posts), default=None),
                    "max_posted_at": max((row["posted_at"] for row in job_posts), default=None),
                }
            )
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        posted_values = [row["posted_at"] for row in posts if row.get("posted_at")]
        files = {
            "posts": "posts.csv",
            "listings": "listings.csv",
            "comments": "comments.csv",
            "logs": "logs.jsonl",
            "manifest": "manifest.json",
        }
        _write_csv(output / files["posts"], POST_FIELDS, posts)
        _write_csv(output / files["listings"], LISTING_FIELDS, listings)
        _write_csv(output / files["comments"], COMMENT_FIELDS, comments)
        _write_jsonl(output / files["logs"], LOG_FIELDS, logs)
        manifest = {
            "schema_version": 1,
            "generated_at": generated_at,
            "since": since,
            "until": until,
            "cutoff_at": cutoff_at,
            "data_min_posted_at": min(posted_values, default=None),
            "data_max_posted_at": max(posted_values, default=None),
            "collection_state": "complete" if all(job["state"] == "completed" for job in jobs) else "in_progress_or_partial",
            "raw_html_included": False,
            "raw_html_note": "원문 HTML은 로컬 감사용 SQLite에 보존하며, 공개 데이터셋에는 구조화된 필드만 포함합니다.",
            "jobs": job_summaries,
            "counts": {"posts": len(posts), "listings": len(listings), "comments": len(comments), "logs": len(logs)},
            "files": files,
        }
        (output / files["manifest"]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    watermark = json.loads(WATERMARK_PATH.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description="Export a compact three-month collection snapshot")
    parser.add_argument("--db", type=Path, default=ROOT / ".audit" / "kaitori.sqlite3")
    parser.add_argument("--output-root", type=Path, default=ROOT / "web" / "public" / "data" / "collections")
    parser.add_argument("--since", default=watermark["since"])
    parser.add_argument("--until", default=watermark["until"])
    parser.add_argument("--cutoff-at", default=watermark["cutoff_at"])
    parser.add_argument("--job-id", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    manifest = export_snapshot(args.db, args.output_root, args.since, args.until, args.cutoff_at, args.job_id)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
