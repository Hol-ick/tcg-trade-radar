"""Publish a partitioned, analysis-ready market CSV dataset.

Each observation is written exactly once to a game/month/listing-type
partition. Dimension summaries and a partition index make the dataset usable
without duplicating the full observation table for every dimension.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

GAME_NAMES = {
    "tcggame": "유희왕",
    "onepiececardgame": "원피스 카드게임",
    "pokemoncardgame": "포켓몬 카드게임",
    "digimontcg": "디지몬 카드게임",
    "vg": "뱅가드",
}
LISTING_TYPE_LABELS = {
    "sell": "판매",
    "buy": "구매",
    "trade": "교환",
    "unknown": "미분류",
}
LISTING_TYPES = ("sell", "buy", "trade", "unknown")

OUTPUT_FIELDS = (
    "observation_id", "game_id", "game_name", "year_month", "posted_at", "date_quality", "source_id", "row_id",
    "post_id", "post_url", "post_title", "seller_id", "seller_name", "author_type", "card_key", "card_name",
    "card_name_raw", "card_code", "rarity", "listing_type", "listing_type_label", "quantity", "raw_price",
    "price_krw_observed", "price_status", "price_scope", "price_origin", "shipping_included", "shipping_price_krw",
    "post_status", "analysis_status", "review_status", "review_reason", "price_confidence", "price_candidate",
    "include_in_price_stats", "raw_line",
)
SUMMARY_FIELDS = (
    "game_id", "game_name", "year_month", "listing_type", "listing_type_label", "observations", "sell_rows",
    "buy_rows", "trade_rows", "unknown_rows", "quantity_total", "price_candidate_rows", "strict_price_rows",
    "missing_price_rows", "unique_cards", "unique_sellers", "first_posted_at", "last_posted_at", "median_price_krw",
)
INDEX_FIELDS = (
    "path", "game_id", "game_name", "year_month", "listing_type", "listing_type_label", "rows", "bytes",
    "price_candidate_rows", "strict_price_rows", "min_posted_at", "max_posted_at",
)


def _safe_path_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip(".-") or fallback


def _listing_type(value: str) -> str:
    return value if value in LISTING_TYPES else "unknown"


def _year_month(value: str) -> str:
    value = (value or "").strip()
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])-\d{2}(?:T|$)", value):
        return value[:7]
    return "unknown-date"


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _quantity(value: Any) -> int:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def _new_bucket() -> dict[str, Any]:
    return {
        "observations": 0,
        "sell_rows": 0,
        "buy_rows": 0,
        "trade_rows": 0,
        "unknown_rows": 0,
        "quantity_total": 0,
        "price_candidate_rows": 0,
        "strict_price_rows": 0,
        "missing_price_rows": 0,
        "cards": set(),
        "sellers": set(),
        "dates": [],
        "strict_prices": [],
    }


def _update_bucket(bucket: dict[str, Any], row: dict[str, str], listing_type: str, price: int | None) -> None:
    bucket["observations"] += 1
    bucket[f"{listing_type}_rows"] += 1
    bucket["quantity_total"] += _quantity(row.get("quantity"))
    if price is None:
        bucket["missing_price_rows"] += 1
    if row.get("price_candidate") == "yes":
        bucket["price_candidate_rows"] += 1
    if row.get("include_in_price_stats") == "yes":
        bucket["strict_price_rows"] += 1
        if price is not None:
            bucket["strict_prices"].append(price)
    card_key = (row.get("card_key") or "").strip()
    if card_key:
        bucket["cards"].add(card_key)
    seller_key = (row.get("seller_id") or row.get("seller_name") or "").strip()
    if seller_key:
        bucket["sellers"].add(seller_key)
    posted_at = (row.get("posted_at") or "").strip()
    if posted_at:
        bucket["dates"].append(posted_at)


def _summary_row(key: tuple[str, ...], bucket: dict[str, Any], dimension: str) -> dict[str, Any]:
    game_id = key[0] if dimension in {"game", "game_month", "game_month_type"} else ""
    year_month = key[1] if dimension in {"game_month", "game_month_type"} else key[0] if dimension == "month" else ""
    listing_type = key[0] if dimension == "type" else key[2] if dimension == "game_month_type" else ""
    prices = bucket["strict_prices"]
    return {
        "game_id": game_id,
        "game_name": GAME_NAMES.get(game_id, game_id) if game_id else "",
        "year_month": year_month,
        "listing_type": listing_type,
        "listing_type_label": LISTING_TYPE_LABELS.get(listing_type, "") if listing_type else "",
        "observations": bucket["observations"],
        "sell_rows": bucket["sell_rows"],
        "buy_rows": bucket["buy_rows"],
        "trade_rows": bucket["trade_rows"],
        "unknown_rows": bucket["unknown_rows"],
        "quantity_total": bucket["quantity_total"],
        "price_candidate_rows": bucket["price_candidate_rows"],
        "strict_price_rows": bucket["strict_price_rows"],
        "missing_price_rows": bucket["missing_price_rows"],
        "unique_cards": len(bucket["cards"]),
        "unique_sellers": len(bucket["sellers"]),
        "first_posted_at": min(bucket["dates"]) if bucket["dates"] else "",
        "last_posted_at": max(bucket["dates"]) if bucket["dates"] else "",
        "median_price_krw": int(median(prices)) if prices else "",
    }


def _write_csv(path: Path, fields: Iterable[str], rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fields), extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _clean_csv_value(row.get(field)) for field in writer.fieldnames})
            count += 1
    return count


def _clean_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value.rstrip() if isinstance(value, str) else value


def _read_source_fields(input_csv: Path) -> tuple[str, ...]:
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        fields = tuple(csv.DictReader(handle).fieldnames or ())
    required = {"gallery_id", "row_id", "posted_at", "listing_type"}
    missing = sorted(required.difference(fields))
    if missing:
        raise ValueError(f"input CSV missing required fields: {', '.join(missing)}")
    return fields


def _read_source_date_range(input_csv: Path) -> tuple[str, str]:
    first = ""
    last = ""
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("posted_at") or "").strip()
            if not value:
                continue
            first = value if not first or value < first else first
            last = value if not last or value > last else last
    return first, last


def _write_readme(output_root: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Partitioned market dataset",
        "",
        "전처리 관측행을 게임·월·거래유형별로 중복 없이 나눈 공개 분석 데이터입니다.",
        "",
        f"- source rows: {manifest['counts']['input_rows']:,}",
        f"- partitions: {manifest['counts']['partitions']:,}",
        f"- source date range: {manifest['source']['min_posted_at'] or 'unknown'} ~ {manifest['source']['max_posted_at'] or 'unknown'}",
        "- listing types: `sell` 판매, `buy` 구매, `trade` 교환, `unknown` 미분류",
        "",
        "## 파일 사용 순서",
        "",
        "1. `manifest.json`에서 스키마와 전체 행 수를 확인합니다.",
        "2. `index/partitions.csv`에서 원하는 게임·월·거래유형 파티션을 찾습니다.",
        "3. 전체 추세는 `summary/` 아래 집계 CSV를 사용합니다.",
        "",
        "각 관측행은 `partitions/<game_id>/<year_month>/<listing_type>.csv` 한 파일에만 존재합니다. 따라서 게임별·월별·유형별 분석을 위해 같은 원본행을 여러 번 커밋하지 않습니다.",
        "",
    ]
    (output_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def export_partitioned_market(input_csv: Path, output_root: Path, replace: bool = False) -> dict[str, Any]:
    input_csv = Path(input_csv)
    output_root = Path(output_root)
    if not input_csv.is_file():
        raise FileNotFoundError(input_csv)
    if output_root.exists() and any(output_root.iterdir()):
        if not replace:
            raise FileExistsError(f"output directory is not empty: {output_root}")
        for child in output_root.iterdir():
            if child.is_dir():
                import shutil
                shutil.rmtree(child)
            else:
                child.unlink()
    output_root.mkdir(parents=True, exist_ok=True)
    source_fields = _read_source_fields(input_csv)
    source_min, source_max = _read_source_date_range(input_csv)
    partition_buckets: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(_new_bucket)
    game_buckets: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_new_bucket)
    month_buckets: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_new_bucket)
    type_buckets: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_new_bucket)
    game_month_buckets: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_new_bucket)
    game_month_type_buckets: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_new_bucket)
    partition_rows: dict[tuple[str, str, str], int] = defaultdict(int)
    seen_observation_ids: set[str] = set()
    input_rows = 0
    unknown_date_rows = 0

    with ExitStack() as stack, input_csv.open("r", encoding="utf-8-sig", newline="") as source_handle:
        reader = csv.DictReader(source_handle)
        partition_writers: dict[tuple[str, str, str], csv.DictWriter] = {}
        for row_number, raw in enumerate(reader, start=2):
            input_rows += 1
            row = {field: raw.get(field, "") or "" for field in source_fields}
            observation_id = row.get("row_id") or f"{row.get('source_id', 'source')}:{row_number}"
            if observation_id in seen_observation_ids:
                raise ValueError(f"duplicate observation_id: {observation_id}")
            seen_observation_ids.add(observation_id)
            game_id = (row.get("gallery_id") or "unknown-game").strip() or "unknown-game"
            period = _year_month(row.get("posted_at", ""))
            listing_type = _listing_type(row.get("listing_type", ""))
            if period == "unknown-date":
                unknown_date_rows += 1
            game_name = GAME_NAMES.get(game_id, game_id)
            partition_key = (game_id, period, listing_type)
            partition_path = output_root / "partitions" / _safe_path_part(game_id, "unknown-game") / _safe_path_part(period, "unknown-date") / f"{listing_type}.csv"
            if partition_key not in partition_writers:
                partition_path.parent.mkdir(parents=True, exist_ok=True)
                handle = stack.enter_context(partition_path.open("w", encoding="utf-8-sig", newline=""))
                writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore", lineterminator="\r\n")
                writer.writeheader()
                partition_writers[partition_key] = writer
            price = _positive_int(row.get("price_krw_observed"))
            curated = {
                **row,
                "observation_id": observation_id,
                "game_id": game_id,
                "game_name": game_name,
                "year_month": period,
                "date_quality": "known" if period != "unknown-date" else "unknown",
                "card_name": row.get("card_name_normalized") or row.get("card_name_raw") or row.get("card_key"),
                "listing_type": listing_type,
                "listing_type_label": LISTING_TYPE_LABELS[listing_type],
                "price_krw_observed": price if price is not None else "",
            }
            partition_writers[partition_key].writerow({field: _clean_csv_value(curated.get(field, "")) for field in OUTPUT_FIELDS})
            partition_rows[partition_key] += 1
            _update_bucket(partition_buckets[partition_key], row, listing_type, price)
            for bucket_map, key in (
                (game_buckets, (game_id,)),
                (month_buckets, (period,)),
                (type_buckets, (listing_type,)),
                (game_month_buckets, (game_id, period)),
                (game_month_type_buckets, (game_id, period, listing_type)),
            ):
                _update_bucket(bucket_map[key], row, listing_type, price)

    index_rows = []
    for game_id, period, listing_type in sorted(partition_rows):
        relative_path = Path("partitions") / _safe_path_part(game_id, "unknown-game") / _safe_path_part(period, "unknown-date") / f"{listing_type}.csv"
        path = output_root / relative_path
        bucket = partition_buckets[(game_id, period, listing_type)]
        index_rows.append({
            "path": relative_path.as_posix(),
            "game_id": game_id,
            "game_name": GAME_NAMES.get(game_id, game_id),
            "year_month": period,
            "listing_type": listing_type,
            "listing_type_label": LISTING_TYPE_LABELS[listing_type],
            "rows": partition_rows[(game_id, period, listing_type)],
            "bytes": path.stat().st_size,
            "price_candidate_rows": bucket["price_candidate_rows"],
            "strict_price_rows": bucket["strict_price_rows"],
            "min_posted_at": min(bucket["dates"]) if bucket["dates"] else "",
            "max_posted_at": max(bucket["dates"]) if bucket["dates"] else "",
        })
    _write_csv(output_root / "index" / "partitions.csv", INDEX_FIELDS, index_rows)

    summaries = {
        "by_game": sorted((_summary_row(key, bucket, "game") for key, bucket in game_buckets.items()), key=lambda row: row["game_id"]),
        "by_month": sorted((_summary_row(key, bucket, "month") for key, bucket in month_buckets.items()), key=lambda row: row["year_month"]),
        "by_listing_type": sorted((_summary_row(key, bucket, "type") for key, bucket in type_buckets.items()), key=lambda row: row["listing_type"]),
        "by_game_month": sorted((_summary_row(key, bucket, "game_month") for key, bucket in game_month_buckets.items()), key=lambda row: (row["game_id"], row["year_month"])),
        "by_game_month_listing_type": sorted((_summary_row(key, bucket, "game_month_type") for key, bucket in game_month_type_buckets.items()), key=lambda row: (row["game_id"], row["year_month"], row["listing_type"])),
    }
    for name, rows in summaries.items():
        _write_csv(output_root / "summary" / f"{name}.csv", SUMMARY_FIELDS, rows)

    counts = {
        "input_rows": input_rows,
        "partition_rows": sum(partition_rows.values()),
        "partitions": len(partition_rows),
        "games": len(game_buckets),
        "months": len(month_buckets),
        "listing_types": len(type_buckets),
        "unknown_date_rows": unknown_date_rows,
    }
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "path": input_csv.as_posix(),
            "rows": input_rows,
            "min_posted_at": source_min,
            "max_posted_at": source_max,
        },
        "counts": counts,
        "dimensions": {
            "games": [key[0] for key in sorted(game_buckets)],
            "year_months": [key[0] for key in sorted(month_buckets)],
            "listing_types": list(LISTING_TYPES),
        },
        "schema": list(OUTPUT_FIELDS),
        "files": {
            "partition_index": "index/partitions.csv",
            "by_game": "summary/by_game.csv",
            "by_month": "summary/by_month.csv",
            "by_listing_type": "summary/by_listing_type.csv",
            "by_game_month": "summary/by_game_month.csv",
            "by_game_month_listing_type": "summary/by_game_month_listing_type.csv",
        },
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_readme(output_root, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a deduplicated game/month/listing-type market dataset")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(export_partitioned_market(args.input, args.output_root, replace=args.replace), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
