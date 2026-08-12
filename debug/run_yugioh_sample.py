"""Run a bounded, read-only Yu-Gi-Oh gallery collection sample."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Yu-Gi-Oh public gallery sample collection")
    parser.add_argument("--max-posts", type=int, default=10)
    parser.add_argument("--transport", choices=("auto", "http", "browser"), default="auto")
    args = parser.parse_args()
    max_posts = max(1, min(args.max_posts, 10))
    until = date.today()
    since = until - timedelta(days=6)
    repo = Repository(PROJECT_ROOT / ".audit" / "yugioh-sample.sqlite3")
    if args.transport == "http":
        from kaitori_collector.parser import fetch_text
        service = JobService(repo, fetcher=fetch_text)
    elif args.transport == "browser":
        from kaitori_collector.parser import fetch_text_browser
        service = JobService(repo, fetcher=fetch_text_browser)
    else:
        service = JobService(repo)
    request = JobRequest(
        gallery_id="tcggame",
        gallery_url="https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
        subject="판매",
        subjects=("판매", "구매", "거래", "🔁거래"),
        since=since.isoformat(),
        until=until.isoformat(),
        max_posts=max_posts,
        max_pages=1,
        delay=1.0,
        max_retries=2,
        keep_raw=True,
    )
    job_id = service.create_job(request, start=False)
    status = service.run_job(job_id)
    payload = {
        "gallery": "유희왕 / tcggame",
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "job_id": job_id,
        "status": status,
        "rows": service.get_results(job_id),
        "comments": service.get_comments(job_id),
        "logs": service.get_logs(job_id, limit=2000),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    repo.close()
    return 0 if status["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
