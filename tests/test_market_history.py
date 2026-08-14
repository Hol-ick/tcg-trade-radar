import tempfile
import unittest
from pathlib import Path

from kaitori_collector.contracts import ExtractedRow, JobRequest
from kaitori_collector.storage import Repository


def listing(name: str, intent: str, price: int) -> ExtractedRow:
    return ExtractedRow(
        gallery_id="tcggame",
        post_title=name,
        post_url="",
        posted_at="2026-01-02T10:00:00+09:00",
        card_name=name,
        rarity="",
        raw_price=str(price),
        price_krw=price,
        price_unit="원",
        quantity=2,
        shipping_included=True,
        shipping_price_krw=None,
        review_status="parsed",
        review_reason="",
        raw_line=f"{name} {price}원",
        listing_type=intent,
        intent_confidence=0.9,
        price_type="wanted" if intent == "buy" else "asking",
    )


class MarketHistoryTests(unittest.TestCase):
    def test_history_keeps_event_and_observation_dates_and_supply_demand_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            for index, (intent, price, fetched_at) in enumerate(
                (("sell", 30000, "2026-08-10T09:00:00+09:00"), ("buy", 32000, "2026-08-11T09:00:00+09:00"))
            ):
                source_id, _ = repo.upsert_source(
                    {
                        "gallery_id": "tcggame",
                        "post_url": f"https://example.test/history/{index}",
                        "title": "Blue Eyes",
                        "posted_at": "2026-01-02T10:00:00+09:00",
                        "fetched_at": fetched_at,
                        "raw_html": f"<html>{index}</html>",
                    }
                )
                repo.attach_source_to_job(job_id, source_id)
                current = listing("Blue Eyes", intent, price)
                current = current.__class__(**{**current.__dict__, "post_url": f"https://example.test/history/{index}"})
                self.assertEqual(repo.insert_rows(job_id, source_id, [current]), 1)

            first = repo.refresh_market_history()
            second = repo.refresh_market_history()

            self.assertEqual(first, {"observations": 2, "daily_rows": 2})
            self.assertEqual(second, first)
            observations = repo.connection.execute(
                "SELECT event_date, observed_date, posted_at, observed_at FROM kaitori_market_observations ORDER BY observed_date"
            ).fetchall()
            self.assertEqual([(row["event_date"], row["observed_date"]) for row in observations], [
                ("2026-01-02", "2026-08-10"),
                ("2026-01-02", "2026-08-11"),
            ])
            daily = repo.list_market_daily(game_id="tcggame", observed_since="2026-08-11")
            self.assertEqual(len(daily), 1)
            self.assertEqual(daily[0]["unmatched_listing_count"], 1)
            self.assertEqual(daily[0]["review_count"], 0)
            self.assertEqual(daily[0]["demand_listing_count"], 1)
            self.assertEqual(daily[0]["demand_quantity"], 2)
            self.assertEqual(daily[0]["demand_price_median"], 32000)
            self.assertEqual(daily[0]["supply_listing_count"], 0)
            repo.close()


if __name__ == "__main__":
    unittest.main()
