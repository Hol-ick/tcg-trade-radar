"""Collect all configured card-trade posts in a calendar three-month window."""
from __future__ import annotations

import argparse
import json
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


GAMES: tuple[dict[str, Any], ...] = (
    {"name": "유희왕", "id": "tcggame", "subject": "판매"},
    {"name": "원피스 카드게임", "id": "onepiececardgame", "subject": "판매"},
    {"name": "포켓몬 카드게임", "id": "pokemoncardgame", "subject": "🔁거래"},
    {"name": "디지몬 카드게임", "id": "digimontcg", "subject": "거래"},
    {"name": "뱅가드", "id": "vg", "subject": "거래"},
)
SUBJECTS = ("판매", "구매", "거래", "🔁거래")


def subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def build_parser() -> argparse.ArgumentParser:
    today = date.today()
    parser = argparse.ArgumentParser(description="Run a complete three-month multi-game DCInside backfill")
    parser.add_argument("--since", default=subtract_months(today, 3).isoformat())
    parser.add_argument("--until", default=today.isoformat())
    parser.add_argument("--db", type=Path, default=ROOT / ".audit" / "kaitori.sqlite3")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--max-posts", type=int, default=20_000)
    parser.add_argument("--max-pages", type=int, default=5_000)
    parser.add_argument("--game-id", action="append", choices=[game["id"] for game in GAMES])
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    selected = [game for game in GAMES if not args.game_id or game["id"] in args.game_id]
    repository = Repository(args.db)
    service = JobService(repository)
    summary: list[dict[str, Any]] = []
    try:
        print(json.dumps({"event": "collection_start", "since": args.since, "until": args.until, "games": [game["id"] for game in selected]}, ensure_ascii=False), flush=True)
        for game in selected:
            request = JobRequest(
                gallery_id=game["id"],
                gallery_url=f"https://gall.dcinside.com/mgallery/board/lists?id={game['id']}",
                subject=game["subject"],
                subjects=SUBJECTS,
                since=args.since,
                until=args.until,
                max_posts=args.max_posts,
                max_pages=args.max_pages,
                delay=args.delay,
                max_retries=2,
                buy_rate=60,
                keep_raw=True,
                review_unmatched=True,
            )
            job_id = service.create_job(request, start=False)
            print(json.dumps({"event": "game_start", "game": game["name"], "gallery_id": game["id"], "job_id": job_id}, ensure_ascii=False), flush=True)
            status = service.run_job(job_id)
            logs = repository.list_job_logs(job_id, limit=20_000)
            result = {
                "event": "game_done",
                "game": game["name"],
                "gallery_id": game["id"],
                "job_id": job_id,
                "state": status["state"],
                "counts": status["counts"],
                "warnings": [log["message"] for log in logs if log["level"] == "warning"][-20:],
                "errors": [log["message"] for log in logs if log["level"] == "error"][-20:],
            }
            summary.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        repository.close()

    manifest = {
        "since": args.since,
        "until": args.until,
        "games": summary,
    }
    manifest_path = args.manifest or ROOT / ".audit" / f"three-month-collection-{args.since}-{args.until}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "collection_done", "manifest": str(manifest_path), "failed_games": [item["gallery_id"] for item in summary if item["state"] != "completed"]}, ensure_ascii=False), flush=True)
    return 0 if all(item["state"] == "completed" for item in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
