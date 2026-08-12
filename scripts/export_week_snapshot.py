"""Run one bounded weekly crawl and publish a static JSON/CSV snapshot.

This script intentionally runs the collector in-process. It does not start the
HTTP worker API and is suitable for a scheduled or manually dispatched action.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaitori_collector.contracts import JobRequest
from kaitori_collector.parser import CSV_FIELDS
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository

GALLERIES: dict[str, dict[str, str]] = {
    "tcggame": {"name": "TCG 게임", "subject": "판매", "url": "https://gall.dcinside.com/mgallery/board/lists?id=tcggame"},
    "onepiececardgame": {"name": "원피스 카드게임", "subject": "판매", "url": "https://gall.dcinside.com/mgallery/board/lists?id=onepiececardgame"},
    "pokemoncardgame": {"name": "포켓몬 카드", "subject": "판매", "url": "https://gall.dcinside.com/mgallery/board/lists?id=pokemoncardgame"},
    "digimontcg": {"name": "디지몬 카드", "subject": "거래", "url": "https://gall.dcinside.com/mgallery/board/lists?id=digimontcg"},
    "vg": {"name": "뱅가드", "subject": "거래", "url": "https://gall.dcinside.com/mgallery/board/lists?id=vg"},
}
SUBJECTS = ("판매", "구매", "거래", "🔁거래")


def validate_period(since_text: str, until_text: str) -> tuple[date, date]:
    try:
        since = date.fromisoformat(since_text)
        until = date.fromisoformat(until_text)
    except ValueError as exc:
        raise ValueError("since/until must use YYYY-MM-DD") from exc
    if until - since != timedelta(days=6):
        raise ValueError("the collection period must contain exactly seven calendar days")
    return since, until


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in CSV_FIELDS} | {
        "id": row.get("id"),
        "listing_type": row.get("listing_type") or "unknown",
        "source_url": row.get("source_url") or row.get("post_url"),
        "buy_price_krw": row.get("buy_price_krw"),
    }


def write_snapshot(output_root: Path, gallery_id: str, since: date, until: date, rows: list[dict[str, Any]], generated_at: str) -> tuple[Path, Path]:
    target = output_root / gallery_id
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{since.isoformat()}.json"
    csv_path = target / f"{since.isoformat()}.csv"
    public_rows = [public_row(row) for row in rows]
    payload = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "generated_at": generated_at,
        "gallery_id": gallery_id,
        "row_count": len(public_rows),
        "review_count": sum(row.get("review_status") == "needs_review" for row in public_rows),
        "rows": public_rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(public_rows)
    return json_path, csv_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish one seven-day TCG collection snapshot")
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--gallery-id", choices=sorted(GALLERIES), default="tcggame")
    parser.add_argument("--db", type=Path, default=ROOT / ".audit" / "kaitori-week.sqlite3")
    parser.add_argument("--output-root", type=Path, default=ROOT / "web" / "public" / "data" / "weeks")
    parser.add_argument("--max-posts", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    since, until = validate_period(args.since, args.until)
    gallery = GALLERIES[args.gallery_id]
    repository = Repository(args.db)
    service = JobService(repository)
    request = JobRequest(
        gallery_id=args.gallery_id,
        gallery_url=gallery["url"],
        subject=gallery["subject"],
        subjects=SUBJECTS,
        since=since.isoformat(),
        until=until.isoformat(),
        max_posts=args.max_posts,
        max_pages=args.max_pages,
        delay=args.delay,
        max_retries=2,
        buy_rate=60,
        keep_raw=True,
        review_unmatched=True,
    )
    print(json.dumps({"event": "collection_start", "gallery_id": args.gallery_id, "since": args.since, "until": args.until}, ensure_ascii=False), flush=True)
    try:
        job_id = service.create_job(request, start=False)
        status = service.run_job(job_id)
        rows = service.get_results(job_id)
        if status["state"] != "completed":
            raise RuntimeError(status.get("error_message") or "collection failed")
        generated_at = status.get("finished_at") or date.today().isoformat()
        json_path, csv_path = write_snapshot(args.output_root, args.gallery_id, since, until, rows, generated_at)
        print(json.dumps({"event": "collection_done", "state": status["state"], "counts": status["counts"], "json": str(json_path), "csv": str(csv_path)}, ensure_ascii=False), flush=True)
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
