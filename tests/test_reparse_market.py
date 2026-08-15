import csv
import tempfile
import unittest
from pathlib import Path

from scripts.reparse_market_csv import reparse_market_csv


FIELDS = [
    "post_url", "post_title", "card_key", "card_name", "card_name_raw", "card_code", "rarity",
    "listing_type", "quantity", "raw_price", "price_krw_observed", "price_status", "price_scope",
    "price_origin", "shipping_included", "shipping_price_krw", "post_status", "analysis_status",
    "review_status", "review_reason", "raw_line",
]


class ReparseMarketTests(unittest.TestCase):
    def test_reparse_preserves_rows_and_removes_copy_count_price(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            output = Path(directory) / "output.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow({
                    "post_url": "https://example.test/post/inventory",
                    "post_title": "덱소스 일괄판매",
                    "card_name_raw": "이상한사탕",
                    "listing_type": "sell",
                    "quantity": "1",
                    "raw_price": "1",
                    "price_krw_observed": "10000",
                    "price_status": "estimated",
                    "price_scope": "per_card",
                    "price_origin": "text",
                    "post_status": "active",
                    "review_status": "needs_review",
                    "raw_line": "이상한사탕1",
                })
                writer.writerow({
                    "post_url": "https://example.test/post/amount",
                    "post_title": "카드 판매",
                    "card_name_raw": "하솔3",
                    "listing_type": "sell",
                    "quantity": "1",
                    "raw_price": "3500",
                    "price_krw_observed": "35000000",
                    "price_status": "estimated",
                    "price_scope": "per_card",
                    "price_origin": "text",
                    "post_status": "active",
                    "review_status": "needs_review",
                    "raw_line": "하솔3 3500",
                })

            report = reparse_market_csv(source, output)

            self.assertEqual(report["counts"]["rows"], 2)
            self.assertEqual(report["counts"]["price_to_missing"], 1)
            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["raw_line"], "이상한사탕1")
            self.assertEqual(rows[0]["quantity"], "1")
            self.assertEqual(rows[0]["price_krw_observed"], "")
            self.assertEqual(rows[0]["price_status"], "missing")
            self.assertEqual(rows[1]["card_name_raw"], "하솔")
            self.assertEqual(rows[1]["quantity"], "3")
            self.assertEqual(rows[1]["price_krw_observed"], "3500")

    def test_reparse_does_not_replace_an_existing_multi_price_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            output = Path(directory) / "output.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow({
                    "post_url": "https://example.test/post/multi",
                    "post_title": "카드 판매",
                    "card_name": "파닥몬 SR",
                    "card_name_raw": "파닥몬 SR",
                    "listing_type": "sell",
                    "quantity": "1",
                    "raw_price": "0.3",
                    "price_krw_observed": "3000",
                    "price_status": "estimated",
                    "price_scope": "bundle",
                    "price_origin": "text",
                    "post_status": "active",
                    "review_status": "needs_review",
                    "review_reason": "복수 카드 가격",
                    "raw_line": "파닥몬 SR 0.3, LM 0.5",
                })

            reparse_market_csv(source, output)

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["price_krw_observed"], "3000")
            self.assertEqual(row["raw_price"], "0.3")


if __name__ == "__main__":
    unittest.main()
