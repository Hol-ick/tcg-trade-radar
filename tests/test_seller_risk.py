import tempfile
import unittest
from pathlib import Path

from kaitori_collector.api import WorkerApplication
from kaitori_collector.contracts import ExtractedRow, JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.seller_risk import build_post_family_id, build_seller_identity
from kaitori_collector.storage import Repository


def extracted(url: str, author: str = "seller-a") -> ExtractedRow:
    return ExtractedRow(
        gallery_id="tcggame", post_title="Card sale", post_url=url, posted_at="2026-08-12T10:00:00+09:00",
        card_name="Blue-Eyes", rarity="UR", raw_price="30000", price_krw=30000, price_unit="원",
        quantity=1, shipping_included=True, shipping_price_krw=None, review_status="parsed", review_reason="",
        raw_line="Blue-Eyes 30000원", listing_type="sell", intent_confidence=0.9, price_type="asking",
        author_name=author, author_type="registered",
    )


class SellerRiskTests(unittest.TestCase):
    def test_registered_names_are_grouped_but_guest_names_are_post_scoped(self):
        first = build_seller_identity("tcggame", " Seller A ", "registered", "source-1")
        second = build_seller_identity("tcggame", "seller a", "registered", "source-2")
        guest_first = build_seller_identity("tcggame", "ㅇㅇ", "guest", "source-1")
        guest_second = build_seller_identity("tcggame", "ㅇㅇ", "guest", "source-2")

        self.assertEqual(first.seller_id, second.seller_id)
        self.assertNotEqual(guest_first.seller_id, guest_second.seller_id)
        self.assertEqual(build_post_family_id("tcggame", "https://example.test/view?id=tcggame&no=10"), build_post_family_id("tcggame", "https://example.test/view?id=tcggame&no=10"))

    def test_repost_and_external_messenger_create_review_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "seller.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            first_id, _ = repo.upsert_source({
                "gallery_id": "tcggame", "post_url": "https://example.test/view?id=tcggame&no=1",
                "title": "Card sale", "posted_at": "2026-08-11T10:00:00+09:00", "author_name": "Seller A",
                "author_type": "registered", "raw_html": "<p>오픈카톡으로 연락</p>",
            })
            repo.attach_source_to_job(job_id, first_id)
            repo.insert_rows(job_id, first_id, [extracted("https://example.test/view?id=tcggame&no=1")])
            repo.analyze_source_risk(first_id)
            second_id, _ = repo.upsert_source({
                "gallery_id": "tcggame", "post_url": "https://example.test/view?id=tcggame&no=2",
                "title": "Card sale", "posted_at": "2026-08-12T10:00:00+09:00", "author_name": "Seller A",
                "author_type": "registered", "raw_html": "<p>오픈카톡으로 연락</p>",
            })
            repo.attach_source_to_job(job_id, second_id)
            repo.insert_rows(job_id, second_id, [extracted("https://example.test/view?id=tcggame&no=2")])
            seller = repo.analyze_source_risk(second_id)

            codes = {signal["code"] for signal in seller["signals"]}
            self.assertIn("external_messenger", codes)
            self.assertIn("repeated_listing", codes)
            self.assertEqual(seller["observed_post_count"], 2)
            self.assertGreaterEqual(seller["risk_score"], 20)
            self.assertEqual(repo.list_sellers(game_id="tcggame")[0]["seller_id"], seller["seller_id"])
            repo.close()

    def test_seller_api_exposes_profile_and_review_action(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "seller.sqlite3")
            service = JobService(repo, fetcher=lambda _: "", sleep=lambda _: None)
            app = WorkerApplication(service, start_jobs=False)
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            source_id, _ = repo.upsert_source({"gallery_id": "tcggame", "post_url": "https://example.test/1", "title": "Card", "posted_at": "2026-08-12", "author_name": "Seller", "author_type": "registered"})
            repo.attach_source_to_job(job_id, source_id)
            repo.insert_rows(job_id, source_id, [extracted("https://example.test/1")])
            seller = repo.analyze_source_risk(source_id)

            listed = app.request("GET", "/market/sellers?game_id=tcggame")
            profile = app.request("GET", f"/sellers/{seller['seller_id']}")
            reviewed = app.request("POST", f"/sellers/{seller['seller_id']}/review", {"action": "watch", "actor": "tester", "note": "확인 대기"})

            self.assertEqual(listed.status, 200)
            self.assertEqual(profile.status, 200)
            self.assertEqual(reviewed.status, 200)
            self.assertEqual(reviewed.body["review_status"], "watching")
            repo.close()


if __name__ == "__main__":
    unittest.main()
