import csv
import json
from pathlib import Path

from scripts.export_partitioned_market import export_partitioned_market


INPUT_FIELDS = (
    "gallery_id", "source_id", "row_id", "post_id", "posted_at", "date_quality", "post_url", "post_title",
    "seller_id", "seller_name", "author_type", "card_key", "card_name_raw", "card_name_normalized", "card_code",
    "rarity", "listing_type", "quantity", "raw_price", "price_krw_observed", "price_status", "price_scope",
    "price_origin", "shipping_included", "shipping_price_krw", "post_status", "analysis_status", "review_status",
    "review_reason", "price_confidence", "price_candidate", "include_in_price_stats", "raw_line",
)


def _write_input(path: Path) -> None:
    rows = [
        {
            "gallery_id": "tcggame", "source_id": "source-1", "row_id": "row-1", "post_id": "post-1",
            "posted_at": "2026-07-04T10:00:00+09:00", "date_quality": "known", "post_url": "https://example/1",
            "post_title": "블루아이즈 판매", "seller_id": "seller-1", "seller_name": "판매자1", "author_type": "registered",
            "card_key": "canonical-blue-eyes", "card_name_raw": "블루아이즈", "card_name_normalized": "블루아이즈", "card_code": "",
            "rarity": "", "listing_type": "sell", "quantity": "2", "raw_price": "10000",
            "price_krw_observed": "10000", "price_status": "exact", "price_scope": "per_card", "price_origin": "text",
            "shipping_included": "unknown", "shipping_price_krw": "", "post_status": "active", "analysis_status": "usable",
            "review_status": "parsed", "review_reason": "", "price_confidence": "exact", "price_candidate": "yes",
            "include_in_price_stats": "yes", "raw_line": "블루아이즈 1장 10000원",
        },
        {
            "gallery_id": "pokemoncardgame", "source_id": "source-2", "row_id": "row-2", "post_id": "post-2",
            "posted_at": "2026-07-14T11:00:00+09:00", "date_quality": "known", "post_url": "https://example/2",
            "post_title": "피카츄 구합니다", "seller_id": "seller-2", "seller_name": "구매자1", "author_type": "guest",
            "card_key": "pikachu", "card_name_raw": "피카츄", "card_name_normalized": "피카츄", "card_code": "",
            "rarity": "", "listing_type": "buy", "quantity": "1", "raw_price": "",
            "price_krw_observed": "", "price_status": "missing", "price_scope": "unknown", "price_origin": "unknown",
            "shipping_included": "unknown", "shipping_price_krw": "", "post_status": "active", "analysis_status": "needs_review",
            "review_status": "needs_review", "review_reason": "희망가 미기재", "price_confidence": "missing", "price_candidate": "no",
            "include_in_price_stats": "no", "raw_line": "피카츄 구합니다",
        },
        {
            "gallery_id": "tcggame", "source_id": "source-3", "row_id": "row-3", "post_id": "post-3",
            "posted_at": "", "date_quality": "unknown", "post_url": "https://example/3",
            "post_title": "카드 교환", "seller_id": "seller-3", "seller_name": "교환자", "author_type": "guest",
            "card_key": "mystery", "card_name_raw": "미상", "card_name_normalized": "미상", "card_code": "",
            "rarity": "", "listing_type": "trade", "quantity": "1", "raw_price": "",
            "price_krw_observed": "", "price_status": "missing", "price_scope": "unknown", "price_origin": "unknown",
            "shipping_included": "unknown", "shipping_price_krw": "", "post_status": "active", "analysis_status": "needs_review",
            "review_status": "needs_review", "review_reason": "", "price_confidence": "missing", "price_candidate": "no",
            "include_in_price_stats": "no", "raw_line": "카드 교환",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_export_creates_one_partition_per_observation(tmp_path: Path):
    source = tmp_path / "observations.csv"
    output = tmp_path / "market"
    _write_input(source)

    manifest = export_partitioned_market(source, output)

    assert manifest["counts"]["input_rows"] == 3
    assert manifest["counts"]["partition_rows"] == 3
    assert manifest["counts"]["partitions"] == 3
    partitions = _read_csv(output / "index" / "partitions.csv")
    assert {row["path"] for row in partitions} == {
        "partitions/tcggame/2026-07/sell.csv",
        "partitions/pokemoncardgame/2026-07/buy.csv",
        "partitions/tcggame/unknown-date/trade.csv",
    }
    assert sum(int(row["rows"]) for row in partitions) == 3
    rows = []
    for partition in partitions:
        rows.extend(_read_csv(output / partition["path"]))
    assert {row["observation_id"] for row in rows} == {"row-1", "row-2", "row-3"}
    assert next(row for row in rows if row["observation_id"] == "row-1")["card_key"] == "canonical-blue-eyes"
    assert {row["year_month"] for row in rows} == {"2026-07", "unknown-date"}


def test_export_writes_dimension_summaries_and_manifest(tmp_path: Path):
    source = tmp_path / "observations.csv"
    output = tmp_path / "market"
    _write_input(source)

    export_partitioned_market(source, output)

    by_game = _read_csv(output / "summary" / "by_game.csv")
    tcggame = next(row for row in by_game if row["game_id"] == "tcggame")
    assert tcggame["observations"] == "2"
    assert tcggame["sell_rows"] == "1"
    assert tcggame["trade_rows"] == "1"
    assert tcggame["quantity_total"] == "3"
    assert tcggame["strict_price_rows"] == "1"

    by_type = _read_csv(output / "summary" / "by_listing_type.csv")
    assert {row["listing_type"] for row in by_type} == {"sell", "buy", "trade"}
    assert next(row for row in by_type if row["listing_type"] == "buy")["missing_price_rows"] == "1"

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["files"]["partition_index"] == "index/partitions.csv"
    assert manifest["dimensions"]["listing_types"] == ["sell", "buy", "trade", "unknown"]
