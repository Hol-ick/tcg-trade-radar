import csv
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "export_week_snapshot.py"
MODULE_SPEC = importlib.util.spec_from_file_location("export_week_snapshot", MODULE_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
EXPORTER = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(EXPORTER)


def test_validate_period_requires_exactly_seven_days():
    assert EXPORTER.validate_period("2026-08-07", "2026-08-13") == (date(2026, 8, 7), date(2026, 8, 13))
    with pytest.raises(ValueError, match="exactly seven"):
        EXPORTER.validate_period("2026-08-07", "2026-08-14")


def test_write_snapshot_publishes_json_and_csv(tmp_path):
    rows = [{"card_name": "Blue-Eyes", "post_title": "판매", "price_krw": 12000, "review_status": "needs_review", "post_url": "https://example.test/1"}]
    json_path, csv_path = EXPORTER.write_snapshot(tmp_path, "tcggame", date(2026, 8, 7), date(2026, 8, 13), rows, "2026-08-13T12:00:00+09:00")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["row_count"] == 1
    assert payload["review_count"] == 1
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        exported = list(csv.DictReader(handle))
    assert exported[0]["card_name"] == "Blue-Eyes"
