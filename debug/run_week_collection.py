"""Run the configured five-game, seven-day collection in one Python process."""
from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository

from kaitori_app import COLLECTION_DAYS, MAX_PAGES_PER_GAME, MAX_POSTS_PER_GAME, PRESETS, collection_period


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-index", type=int, default=0)
    args = parser.parse_args()
    since, until = collection_period()
    database = PROJECT_ROOT / ".audit" / "kaitori.sqlite3"
    repository = Repository(database)
    service = JobService(repository)
    print(json.dumps({"event": "collection_start", "since": since, "until": until, "days": COLLECTION_DAYS, "start_index": args.start_index}, ensure_ascii=True), flush=True)
    try:
        for game in PRESETS[args.start_index:]:
            request = JobRequest(
                gallery_id=game["id"],
                gallery_url=game["url"],
                subject=game["subject"],
                subjects=game.get("subjects", ()),
                since=since,
                until=until,
                max_posts=MAX_POSTS_PER_GAME,
                max_pages=MAX_PAGES_PER_GAME,
                delay=1.0,
                buy_rate=60,
                keep_raw=True,
                review_unmatched=True,
            )
            job_id = service.create_job(request, start=False)
            print(json.dumps({"event": "game_start", "game": game["name"], "gallery_id": game["id"], "subject": game["subject"], "job_id": job_id}, ensure_ascii=True), flush=True)
            status = service.run_job(job_id)
            logs = repository.list_job_logs(job_id, limit=2000)
            warnings = [log["message"] for log in logs if log["level"] == "warning"]
            errors = [log["message"] for log in logs if log["level"] == "error"]
            print(json.dumps({
                "event": "game_done",
                "game": game["name"],
                "job_id": job_id,
                "state": status["state"],
                "counts": status["counts"],
                "warnings": warnings[-10:],
                "errors": errors[-10:],
            }, ensure_ascii=True), flush=True)
    finally:
        repository.close()
    print(json.dumps({"event": "collection_done", "since": since, "until": until}, ensure_ascii=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
