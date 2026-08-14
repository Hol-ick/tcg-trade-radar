from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaitori_collector.storage import Repository


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill graph-ready market observations and daily aggregates")
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()

    repository = Repository(args.db)
    try:
        result = repository.refresh_market_history()
        print(json.dumps({"db": str(args.db), **result}, ensure_ascii=False))
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
