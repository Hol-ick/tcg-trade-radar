import tempfile
import unittest
from pathlib import Path

from kaitori_collector.contracts import ExtractedRow, JobRequest
from kaitori_collector.storage import Repository


def row(url: str, name: str, intent: str, price: int, posted: str) -> ExtractedRow:
    return ExtractedRow(
        gallery_id="tcggame",
        post_title=name,
        post_url=url,
        posted_at=posted,
        card_name=name,
        rarity="",
        raw_price=str(price),
        price_krw=price,
        price_unit="원 명시",
        quantity=1,
        shipping_included=True,
        shipping_price_krw=None,
        review_status="parsed",
        review_reason="",
        raw_line=f"{name} {price}원",
        listing_type=intent,
        intent_confidence=0.9,
        price_type="wanted" if intent == "buy" else "asking" if intent == "sell" else "unknown",
    )


class MarketTests(unittest.TestCase):
    def test_card_summary_connects_supply_and_demand(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            for index, (intent, price) in enumerate((("sell", 30000), ("sell", 35000), ("buy", 32000))):
                source_id, _ = repo.upsert_source({
                    "gallery_id": "tcggame",
                    "post_url": f"https://example.test/post/{index}",
                    "title": "블루아이즈",
                    "posted_at": f"2026-08-{10 + index:02d}T10:00:00+09:00",
                    "raw_html": "<html />",
                })
                repo.attach_source_to_job(job_id, source_id)
                self.assertEqual(repo.insert_rows(job_id, source_id, [row(f"https://example.test/post/{index}", "블루아이즈", intent, price, f"2026-08-{10 + index:02d}T10:00:00+09:00")]), 1)

            summaries = repo.summarize_cards(game_id="tcggame")

            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]["sell_count"], 2)
            self.assertEqual(summaries[0]["buy_count"], 1)
            self.assertEqual(summaries[0]["sell_price_median"], 32500)
            self.assertEqual(summaries[0]["demand_status"], "balanced")
            self.assertIn("구매글 1건", summaries[0]["evidence"])
            repo.close()

    def test_buy_listing_without_price_is_kept_in_demand_count(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            source_id, _ = repo.upsert_source({"gallery_id": "tcggame", "post_url": "https://example.test/post/buy", "title": "블루아이즈 구해요", "posted_at": "2026-08-12", "raw_html": ""})
            repo.attach_source_to_job(job_id, source_id)
            repo.insert_rows(job_id, source_id, [row("https://example.test/post/buy", "블루아이즈", "buy", 0, "2026-08-12")])

            summary = repo.summarize_cards()[0]

            self.assertEqual(summary["buy_count"], 1)
            self.assertIsNone(summary["wanted_price_median"])
            repo.close()


if __name__ == "__main__":
    unittest.main()
