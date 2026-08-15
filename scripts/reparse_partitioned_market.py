"""Reparse every partition in a public market dataset and rebuild its indexes."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.export_partitioned_market import export_partitioned_market
    from scripts.reparse_market_csv import reparse_market_csv
except ModuleNotFoundError:
    from export_partitioned_market import export_partitioned_market
    from reparse_market_csv import reparse_market_csv


def _merge_partitions(input_root: Path, merged_csv: Path) -> int:
    files = sorted((input_root / "partitions").glob("**/*.csv"))
    if not files:
        raise FileNotFoundError(f"no partition CSVs found under {input_root / 'partitions'}")
    row_count = 0
    fieldnames: list[str] | None = None
    source_fieldnames: list[str] | None = None
    with merged_csv.open("w", encoding="utf-8-sig", newline="") as output_handle:
        writer: csv.DictWriter[str] | None = None
        for path in files:
            with path.open("r", encoding="utf-8-sig", newline="") as input_handle:
                reader = csv.DictReader(input_handle)
                if not reader.fieldnames:
                    continue
                if fieldnames is None:
                    source_fieldnames = list(reader.fieldnames)
                    fieldnames = list(source_fieldnames)
                    for required in ("gallery_id", "card_name_normalized"):
                        if required not in fieldnames:
                            fieldnames.append(required)
                    writer = csv.DictWriter(output_handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\r\n")
                    writer.writeheader()
                elif list(reader.fieldnames) != source_fieldnames:
                    raise ValueError(f"partition schema mismatch: {path}")
                assert writer is not None
                for row in reader:
                    if not row.get("gallery_id"):
                        row["gallery_id"] = row.get("game_id", "")
                    if not row.get("card_name_normalized"):
                        row["card_name_normalized"] = row.get("card_name", "")
                    writer.writerow({field: row.get(field, "") or "" for field in fieldnames})
                    row_count += 1
    return row_count


def reparse_partitioned_market(input_root: Path, output_root: Path) -> dict[str, Any]:
    input_root = Path(input_root)
    output_root = Path(output_root)
    if input_root.resolve() == output_root.resolve():
        raise ValueError("input and output roots must be different")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kaitori-reparse-") as temporary:
        temporary_root = Path(temporary)
        merged = temporary_root / "observations.csv"
        reparsed = temporary_root / "reparsed-observations.csv"
        source_rows = _merge_partitions(input_root, merged)
        reparse_report = reparse_market_csv(merged, reparsed)
        export_report = export_partitioned_market(reparsed, output_root, replace=True)
    report = {
        "input_root": str(input_root),
        "output_root": str(output_root),
        "source_rows": source_rows,
        "reparse": reparse_report,
        "export": export_report,
    }
    report["export"]["source"]["path"] = str(input_root).replace("\\", "/")
    (output_root / "manifest.json").write_text(json.dumps(export_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["reparse"]["input"] = str(input_root)
    report["reparse"]["output"] = str(output_root / "<temporary-reparsed-observations.csv>")
    (output_root / "reparse-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(reparse_partitioned_market(args.input_root, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
