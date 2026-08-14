"""Export card, seller, price and quality-aware market observations."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
from kaitori_collector.normalization import normalize_listing_card_label


OBSERVATION_FIELDS = (
    "gallery_id", "source_id", "row_id", "post_id", "posted_at", "date_quality", "post_url", "post_title",
    "seller_id", "seller_name", "author_type", "card_key", "card_name_raw", "card_name_normalized", "card_code",
    "rarity", "listing_type", "quantity", "raw_price", "price_krw_observed", "price_status", "price_scope",
    "price_origin", "shipping_included", "shipping_price_krw", "post_status", "analysis_status", "review_status",
    "review_reason", "price_confidence", "price_candidate", "include_in_price_stats", "raw_line",
)

SUMMARY_FIELDS = (
    "gallery_id", "card_key", "card_name_normalized", "listing_type", "observation_count", "price_observation_count",
    "exact_price_count", "post_count", "seller_count", "quantity_total", "price_min_krw", "price_median_krw",
    "price_max_krw", "exact_price_min_krw", "exact_price_median_krw", "exact_price_max_krw", "latest_posted_at",
    "earliest_posted_at", "needs_review_count",
)

SELLER_SUMMARY_FIELDS = (
    "gallery_id", "seller_id", "seller_name", "card_key", "card_name_normalized", "listing_type",
    "observation_count", "price_observation_count", "exact_price_count", "post_count", "quantity_total", "price_min_krw",
    "price_median_krw", "price_max_krw", "exact_price_min_krw", "exact_price_median_krw", "exact_price_max_krw", "latest_posted_at",
)


def _csv_write(path: Path, fields: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
            count += 1
    return count


def _price_value(row: dict[str, Any]) -> int | None:
    value = row.get("price_krw_observed")
    if value is None or value == "":
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _include_in_price_stats(row: dict[str, Any], price: int | None) -> bool:
    return bool(
        price is not None
        and row.get("post_status") == "active"
        and row.get("analysis_status") == "usable"
        and row.get("price_status") == "exact"
        and row.get("price_scope") == "per_card"
    )


def _price_candidate(row: dict[str, Any], price: int | None) -> bool:
    return bool(
        price is not None
        and row.get("post_status") == "active"
        and row.get("price_status") in {"exact", "estimated"}
        and row.get("price_scope") == "per_card"
    )


def _card_key(row: dict[str, Any]) -> tuple[str, str]:
    code = str(row.get("card_code") or "").strip().upper().replace("_", "-")
    normalized = normalize_listing_card_label(str(row.get("card_name_raw") or ""), str(row.get("listing_type") or ""))
    return code or normalized, normalized


def _seller_key(row: dict[str, Any]) -> tuple[str, str]:
    seller_id = str(row.get("seller_id") or "").strip()
    seller_name = str(row.get("seller_display_name") or row.get("author_name") or "미상").strip() or "미상"
    return seller_id or f"author:{row.get('gallery_id', '')}:{seller_name.casefold()}", seller_name


def _base_query(game_ids: list[str], since: str | None, until: str | None) -> tuple[str, list[Any]]:
    clauses = ["1=1"]
    values: list[Any] = []
    if game_ids:
        marks = ",".join("?" for _ in game_ids)
        clauses.append(f"s.gallery_id IN ({marks})")
        values.extend(game_ids)
    if since:
        clauses.append("(COALESCE(s.posted_at, '') = '' OR substr(s.posted_at, 1, 10) >= ?)")
        values.append(since[:10])
    if until:
        clauses.append("(COALESCE(s.posted_at, '') = '' OR substr(s.posted_at, 1, 10) <= ?)")
        values.append(until[:10])
    query = f"""
        SELECT s.gallery_id, s.id AS source_id, s.post_id, s.posted_at, s.post_url, s.title AS post_title,
               s.author_name, s.author_type, s.seller_id, sl.display_name AS seller_display_name,
               r.id AS row_id, r.card_name_raw, r.card_code, r.rarity, r.listing_type, r.quantity,
               r.raw_price, r.price_krw_observed, r.price_status, r.price_scope, r.price_origin,
               r.shipping_included, r.shipping_price_krw, r.post_status, r.analysis_status,
               r.status AS review_status, r.review_reason, r.raw_line
        FROM kaitori_rows r
        JOIN kaitori_sources s ON s.id = r.source_id
        LEFT JOIN kaitori_sellers sl ON sl.seller_id = s.seller_id
        WHERE {' AND '.join(clauses)}
        ORDER BY s.gallery_id, s.posted_at, r.id
    """
    return query, values


def _summary_row(key: tuple[Any, ...], bucket: dict[str, Any]) -> dict[str, Any]:
    prices = bucket["prices"]
    exact_prices = bucket["exact_prices"]
    return {
        "gallery_id": key[0],
        "card_key": key[1],
        "card_name_normalized": key[2],
        "listing_type": key[3],
        "observation_count": bucket["observations"],
        "price_observation_count": len(prices),
        "exact_price_count": len(exact_prices),
        "post_count": len(bucket["posts"]),
        "seller_count": len(bucket["sellers"]),
        "quantity_total": bucket["quantity"],
        "price_min_krw": min(prices) if prices else None,
        "price_median_krw": int(median(prices)) if prices else None,
        "price_max_krw": max(prices) if prices else None,
        "exact_price_min_krw": min(exact_prices) if exact_prices else None,
        "exact_price_median_krw": int(median(exact_prices)) if exact_prices else None,
        "exact_price_max_krw": max(exact_prices) if exact_prices else None,
        "latest_posted_at": max(bucket["dates"]) if bucket["dates"] else "",
        "earliest_posted_at": min(bucket["dates"]) if bucket["dates"] else "",
        "needs_review_count": bucket["needs_review"],
    }


def export_market(db_path: Path, output_root: Path, game_ids: list[str], since: str | None, until: str | None) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    observations_path = output_root / "observations.csv"
    card_summary_path = output_root / "card_summary.csv"
    seller_summary_path = output_root / "seller_card_summary.csv"
    query, values = _base_query(game_ids, since, until)
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    card_groups: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(lambda: {"observations": 0, "prices": [], "exact_prices": [], "posts": set(), "sellers": set(), "quantity": 0, "dates": [], "needs_review": 0})
    seller_groups: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(lambda: {"observations": 0, "prices": [], "exact_prices": [], "posts": set(), "quantity": 0, "dates": []})
    observation_count = 0
    price_count = 0
    exact_price_count = 0
    unknown_date_count = 0
    try:
        with observations_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OBSERVATION_FIELDS, extrasaction="ignore", lineterminator="\r\n")
            writer.writeheader()
            for raw in connection.execute(query, values):
                row = dict(raw)
                card_key, normalized_name = _card_key(row)
                seller_key, seller_name = _seller_key(row)
                price = _price_value(row)
                include = _include_in_price_stats(row, price)
                candidate = _price_candidate(row, price)
                posted_at = str(row.get("posted_at") or "")
                if not posted_at:
                    unknown_date_count += 1
                observation = {
                    **row,
                    "date_quality": "known" if posted_at else "unknown",
                    "seller_name": seller_name,
                    "card_key": card_key,
                    "card_name_normalized": normalized_name,
                    "price_krw_observed": price,
                    "price_confidence": str(row.get("price_status") or "unknown"),
                    "price_candidate": "yes" if candidate else "no",
                    "include_in_price_stats": "yes" if include else "candidate_estimated" if candidate else "no",
                }
                writer.writerow({field: "" if observation.get(field) is None else observation.get(field) for field in OBSERVATION_FIELDS})
                observation_count += 1
                if candidate:
                    price_count += 1
                if include:
                    exact_price_count += 1
                if not card_key:
                    continue
                group_key = (row["gallery_id"], card_key, normalized_name, row.get("listing_type") or "unknown")
                bucket = card_groups[group_key]
                bucket["observations"] += 1
                bucket["posts"].add(row["source_id"])
                bucket["sellers"].add(seller_key)
                bucket["quantity"] += max(1, int(row.get("quantity") or 1))
                if posted_at:
                    bucket["dates"].append(posted_at)
                if not include:
                    bucket["needs_review"] += 1
                if candidate:
                    bucket["prices"].append(price)
                if include:
                    bucket["exact_prices"].append(price)
                seller_key_tuple = (row["gallery_id"], seller_key, seller_name, card_key, normalized_name, row.get("listing_type") or "unknown")
                seller_bucket = seller_groups[seller_key_tuple]
                seller_bucket["observations"] += 1
                seller_bucket["posts"].add(row["source_id"])
                seller_bucket["quantity"] += max(1, int(row.get("quantity") or 1))
                if posted_at:
                    seller_bucket["dates"].append(posted_at)
                if candidate:
                    seller_bucket["prices"].append(price)
                if include:
                    seller_bucket["exact_prices"].append(price)
    finally:
        connection.close()
    card_rows = [_summary_row(key, bucket) for key, bucket in card_groups.items()]
    card_rows.sort(key=lambda row: (-row["price_observation_count"], row["gallery_id"], row["card_key"], row["listing_type"]))
    seller_rows = []
    for key, bucket in seller_groups.items():
        prices = bucket["prices"]
        exact_prices = bucket["exact_prices"]
        seller_rows.append({
            "gallery_id": key[0], "seller_id": key[1], "seller_name": key[2], "card_key": key[3],
            "card_name_normalized": key[4], "listing_type": key[5], "observation_count": bucket["observations"],
            "price_observation_count": len(prices), "exact_price_count": len(exact_prices), "post_count": len(bucket["posts"]), "quantity_total": bucket["quantity"],
            "price_min_krw": min(prices) if prices else None, "price_median_krw": int(median(prices)) if prices else None,
            "price_max_krw": max(prices) if prices else None,
            "exact_price_min_krw": min(exact_prices) if exact_prices else None,
            "exact_price_median_krw": int(median(exact_prices)) if exact_prices else None,
            "exact_price_max_krw": max(exact_prices) if exact_prices else None,
            "latest_posted_at": max(bucket["dates"]) if bucket["dates"] else "",
        })
    seller_rows.sort(key=lambda row: (-row["price_observation_count"], row["gallery_id"], row["card_key"], row["seller_name"]))
    _csv_write(card_summary_path, SUMMARY_FIELDS, card_rows)
    _csv_write(seller_summary_path, SELLER_SUMMARY_FIELDS, seller_rows)
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "since": since, "until": until, "games": game_ids,
        "counts": {"observations": observation_count, "price_candidates": price_count, "strict_price_observations": exact_price_count, "cards": len(card_rows), "seller_card_groups": len(seller_rows)},
        "unknown_date_observations": unknown_date_count,
        "price_candidate_rule": "active + (exact or estimated) + per_card + positive price_krw_observed",
        "price_stats_rule": "active + usable + exact + per_card + positive price_krw_observed",
        "files": {"observations": observations_path.name, "card_summary": card_summary_path.name, "seller_card_summary": seller_summary_path.name},
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Export preprocessed card, seller and price observations")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / ".audit" / "preprocessed-market")
    parser.add_argument("--game-id", action="append", default=[])
    parser.add_argument("--since")
    parser.add_argument("--until")
    args = parser.parse_args(argv)
    print(json.dumps(export_market(args.db, args.output_root, args.game_id, args.since, args.until), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
