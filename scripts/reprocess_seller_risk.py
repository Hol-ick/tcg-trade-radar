"""Backfill seller profiles and review signals for an existing SQLite database."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaitori_collector.storage import Repository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/kaitori.sqlite3")
    args = parser.parse_args()
    repository = Repository(Path(args.db))
    try:
        print(json.dumps(repository.reprocess_seller_risk(), ensure_ascii=False))
    finally:
        repository.close()


if __name__ == "__main__":
    main()
