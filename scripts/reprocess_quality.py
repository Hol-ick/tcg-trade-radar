"""Apply the quality layer to a previously collected SQLite database."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaitori_collector.storage import Repository


def main() -> int:
    parser = argparse.ArgumentParser(description="Reprocess collected trade data quality metadata")
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    repository = Repository(args.db)
    try:
        print(json.dumps({"db": str(args.db), **repository.reprocess_quality()}, ensure_ascii=False))
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
