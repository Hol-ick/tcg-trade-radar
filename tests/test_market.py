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
            self.assertEqual(summaries[0]["sell_post_count"], 2)
            self.assertEqual(summaries[0]["buy_post_count"], 1)
            self.assertEqual(summaries[0]["sell_price_median"], 32500)
            self.assertEqual(summaries[0]["demand_status"], "balanced")
            self.assertEqual(len(repo.list_card_listings(summaries[0]["card_key"], game_id="tcggame")), 3)
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

    def test_recent_buy_demand_is_weighted_and_same_post_rows_have_one_post(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            for index, intent in enumerate(("buy", "buy", "buy", "sell")):
                post_id = "buy-post" if intent == "buy" else "sell-post"
                source_id, _ = repo.upsert_source({
                    "gallery_id": "tcggame",
                    "post_url": f"https://example.test/post/{post_id}",
                    "title": "테스트 카드",
                    "posted_at": f"2026-08-{12 - index:02d}T10:00:00+09:00",
                    "raw_html": "<html />",
                })
                repo.attach_source_to_job(job_id, source_id)
                repo.insert_rows(job_id, source_id, [row(f"https://example.test/post/{post_id}", "테스트 카드", intent, 10000 + index, f"2026-08-{12 - index:02d}T10:00:00+09:00")])

            summary = repo.summarize_cards(until="2026-08-12")[0]

            self.assertEqual(summary["buy_count"], 3)
            self.assertEqual(summary["buy_post_count"], 1)
            self.assertEqual(summary["sell_post_count"], 1)
            self.assertEqual(summary["recent_buy_count"], 3)
            self.assertEqual(summary["demand_status"], "hot_demand")
            self.assertGreater(summary["demand_score"], 1)
            repo.close()

    def test_old_buy_is_marked_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            source_id, _ = repo.upsert_source({
                "gallery_id": "tcggame",
                "post_url": "https://example.test/post/old",
                "title": "오래된 구매글",
                "posted_at": "2026-07-01T10:00:00+09:00",
                "raw_html": "<html />",
            })
            repo.attach_source_to_job(job_id, source_id)
            repo.insert_rows(job_id, source_id, [row("https://example.test/post/old", "오래된 카드", "buy", 0, "2026-07-01T10:00:00+09:00")])

            summary = repo.summarize_cards(until="2026-08-12")[0]

            self.assertEqual(summary["recent_buy_count"], 0)
            self.assertEqual(summary["demand_status"], "stale_demand")
            repo.close()

    def test_completed_and_bundle_rows_do_not_enter_current_price_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            for index, (name, post_status, scope, price) in enumerate((
                ("블루아이즈", "completed", "per_card", 30000),
                ("블루아이즈", "active", "bundle", 100000),
                ("블루아이즈", "active", "per_card", 35000),
            )):
                source_id, _ = repo.upsert_source({"gallery_id": "tcggame", "post_url": f"https://example.test/post/quality-{index}", "title": name, "posted_at": "2026-08-12", "raw_html": "", "post_status": post_status})
                repo.attach_source_to_job(job_id, source_id)
                current = row(f"https://example.test/post/quality-{index}", name, "sell", price, "2026-08-12")
                current = current.__class__(**{**current.__dict__, "post_status": post_status, "price_scope": scope, "analysis_status": "context_only" if post_status != "active" else "needs_review" if scope != "per_card" else "usable"})
                repo.insert_rows(job_id, source_id, [current])
            summary = repo.summarize_cards()[0]
            self.assertEqual(summary["sell_count"], 1)
            self.assertEqual(summary["sell_price_median"], 35000)
            self.assertEqual(summary["context_only_count"], 1)
            self.assertEqual(summary["review_count"], 1)
            repo.close()

    def test_demand_snapshot_keeps_new_market_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "market.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            source_id, _ = repo.upsert_source({
                "gallery_id": "tcggame",
                "post_url": "https://example.test/post/snapshot",
                "title": "스냅샷 카드",
                "posted_at": "2026-08-12T10:00:00+09:00",
                "raw_html": "<html />",
            })
            repo.attach_source_to_job(job_id, source_id)
            repo.insert_rows(job_id, source_id, [row("https://example.test/post/snapshot", "스냅샷 카드", "buy", 0, "2026-08-12")])

            self.assertEqual(repo.refresh_demand_snapshot("2026-08-12", "tcggame", until="2026-08-12"), 1)
            snapshot = repo.list_demand_snapshots(game_id="tcggame")[0]

            self.assertEqual(snapshot["recent_buy_count"], 1)
            self.assertIn("quality_status", snapshot)
            repo.close()


if __name__ == "__main__":
    unittest.main()
