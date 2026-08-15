"""Reparse an exported market CSV without discarding the original observations."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaitori_collector.normalization import normalize_listing_card_label
from kaitori_collector.parser import parse_sale_line
from kaitori_collector.preprocessing import analysis_status, append_quality_reason, classify_price, fallback_card_match


def _shipping_value(value: str) -> bool | None:
    normalized = (value or "").strip().casefold()
    if normalized in {"included", "true"}:
        return True
    if normalized in {"separate", "false"}:
        return False
    return None


def _shipping_price(value: str) -> int | None:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _public_shipping(value: bool | None) -> str:
    if value is True:
        return "included"
    if value is False:
        return "separate"
    return "unknown"


def _positive_price(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _reparse_row(row: dict[str, str]) -> tuple[dict[str, str], str]:
    raw_line = str(row.get("raw_line") or "").strip()
    title = str(row.get("post_title") or "")
    post_status = str(row.get("post_status") or "active") or "active"
    listing_type = str(row.get("listing_type") or "unknown") or "unknown"
    old_price = _positive_price(row.get("price_krw_observed"))
    old_raw_price = str(row.get("raw_price") or "")
    old_quantity = str(row.get("quantity") or "1")
    old_card_name = str(row.get("card_name_raw") or row.get("card_name") or "")
    old_card_normalized = str(row.get("card_name") or old_card_name)
    old_rarity = str(row.get("rarity") or "")
    preserve_old_label = False
    quantity_context = "일괄" in title or "덱소스" in title
    parsed = parse_sale_line(
        raw_line,
        _shipping_value(str(row.get("shipping_included") or "")),
        _shipping_price(str(row.get("shipping_price_krw") or "")),
        quantity_context=quantity_context,
    ) if raw_line else None

    if parsed is None:
        card_name = str(row.get("card_name_raw") or row.get("card_name") or "")
        rarity = str(row.get("rarity") or "")
        quantity = max(1, int(row.get("quantity") or 1))
        raw_price = ""
        price = None
        price_status = "removed" if post_status in {"completed", "price_removed"} else "missing"
        price_scope = "unknown"
        price_origin = "unknown"
        parser_reason = "가격 후보 재검토 필요"
        row["review_status"] = "needs_review"
        mode = "unparsed"
    else:
        card_name = str(parsed["card_name"])
        rarity = str(parsed["rarity"])
        quantity = max(1, int(parsed["quantity"] or 1))
        raw_price = str(parsed["raw_price"] or "")
        price = _positive_price(parsed.get("price_krw"))
        price_status = str(parsed["price_status"])
        price_scope = str(parsed["price_scope"])
        price_origin = str(parsed["price_origin"])
        parser_reason = str(parsed["review_reason"] or "")
        row["review_status"] = str(parsed["review_status"] or "needs_review")
        mode = "reparsed"

        parser_is_multi_price = "복수 카드 가격" in parser_reason or "일괄·세트 가격" in parser_reason
        parser_is_quantity_aware = "수량 표기 감지" in parser_reason
        embedded_old_number = bool(
            old_raw_price
            and re.search(
                rf"(?<=[A-Za-z가-힣0-9_-]){re.escape(old_raw_price)}(?=[A-Za-z가-힣0-9_-])",
                raw_line,
            )
        )
        if old_price is not None and price is not None and old_price != price and parser_is_multi_price and not parser_is_quantity_aware and not embedded_old_number:
            # A multi-card line has several legitimate price candidates. Keep
            # the previously selected amount unless the old candidate was
            # visibly embedded in a card code/name.
            price = old_price
            raw_price = old_raw_price
            card_name = old_card_name
            rarity = old_rarity
            preserve_old_label = True
            parser_reason = str(row.get("review_reason") or parser_reason)
            mode = "preserved_multi_price"

    price_status, price_scope, price_origin = classify_price(
        raw_price=raw_price,
        price_unit=str(parsed.get("price_unit") if parsed else row.get("price_unit") or ""),
        quantity=quantity,
        raw_line=raw_line,
        post_status=post_status,
    )
    quality = analysis_status(
        post_status=post_status,
        listing_type=listing_type,
        card_name=card_name,
        price_status=price_status,
        price_scope=price_scope,
    )
    reason = append_quality_reason(
        parser_reason,
        post_status=post_status,
        price_status=price_status,
        price_scope=price_scope,
        analysis=quality,
    )
    normalized_name = old_card_normalized if preserve_old_label else normalize_listing_card_label(card_name, listing_type)
    row.update({
        "card_key": str(row.get("card_code") or normalized_name),
        "card_name": normalized_name,
        "card_name_raw": card_name,
        "rarity": rarity,
        "quantity": str(quantity),
        "raw_price": raw_price,
        "price_krw_observed": str(price) if price is not None else "",
        "price_status": price_status,
        "price_scope": price_scope,
        "price_origin": price_origin,
        "price_confidence": price_status,
        "price_candidate": "yes" if price is not None and post_status == "active" and price_status in {"exact", "estimated"} and price_scope == "per_card" else "no",
        "include_in_price_stats": "yes" if price is not None and post_status == "active" and quality == "usable" and price_status == "exact" and price_scope == "per_card" else "no",
        "analysis_status": quality,
        "review_reason": reason,
    })
    if "card_name_normalized" in row:
        row["card_name_normalized"] = normalized_name
    parsed_shipping = parsed.get("shipping_included") if parsed else _shipping_value(str(row.get("shipping_included") or ""))
    row["shipping_included"] = _public_shipping(parsed_shipping)
    if parsed and parsed.get("shipping_price_krw") is not None:
        row["shipping_price_krw"] = str(parsed["shipping_price_krw"])
    changed_fields = []
    if old_price != price or old_raw_price != raw_price:
        changed_fields.append("price")
    if old_quantity != str(quantity):
        changed_fields.append("quantity")
    if mode == "unparsed":
        changed_fields.append("unparsed")
    return row, ",".join(changed_fields)


def reparse_market_csv(input_csv: Path, output_csv: Path) -> dict[str, Any]:
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    if not input_csv.is_file():
        raise FileNotFoundError(input_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    counts = {"rows": 0, "reparsed": 0, "changed": 0, "price_to_missing": 0, "quantity_recovered": 0, "unparsed": 0}
    examples: list[dict[str, str]] = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as source_handle:
        reader = csv.DictReader(source_handle)
        if not reader.fieldnames or "raw_line" not in reader.fieldnames:
            raise ValueError("input CSV must contain raw_line")
        with output_csv.open("w", encoding="utf-8-sig", newline="") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=reader.fieldnames, extrasaction="ignore", lineterminator="\r\n")
            writer.writeheader()
            for raw in reader:
                counts["rows"] += 1
                before_price = _positive_price(raw.get("price_krw_observed"))
                before_quantity = str(raw.get("quantity") or "1")
                row, change = _reparse_row({field: raw.get(field, "") or "" for field in reader.fieldnames})
                counts["reparsed"] += 1
                if change:
                    counts["changed"] += 1
                if before_price is not None and not _positive_price(row.get("price_krw_observed")):
                    counts["price_to_missing"] += 1
                if before_quantity != str(row.get("quantity") or "1"):
                    counts["quantity_recovered"] += 1
                if "unparsed" in change:
                    counts["unparsed"] += 1
                if change and len(examples) < 30:
                    examples.append({
                        "post_url": str(row.get("post_url") or ""),
                        "raw_line": str(row.get("raw_line") or ""),
                        "old_price_krw": str(raw.get("price_krw_observed") or ""),
                        "new_price_krw": str(row.get("price_krw_observed") or ""),
                        "new_quantity": str(row.get("quantity") or ""),
                        "change": change,
                    })
                writer.writerow(row)
    return {"input": str(input_csv), "output": str(output_csv), "counts": counts, "examples": examples}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(reparse_market_csv(args.input, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
