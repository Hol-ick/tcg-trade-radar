"""Start a local in-process worker and verify the public API contract."""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kaitori_collector.api import WorkerApplication
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repository = Repository(Path(directory) / "kaitori.sqlite3")
        service = JobService(repository, sleep=lambda _: None)
        application = WorkerApplication(service, api_token="smoke", start_jobs=False)
        health = application.request("GET", "/health")
        if health.status != 200 or not health.body.get("version"):
            raise SystemExit("health contract failed")
        unauthorized = application.request("POST", "/jobs", {"gallery_id": "tcggame"})
        if unauthorized.status != 401:
            raise SystemExit("authorization contract failed")
        repository.close()
    print("API smoke passed")


if __name__ == "__main__":
    main()
