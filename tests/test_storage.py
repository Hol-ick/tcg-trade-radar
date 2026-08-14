import tempfile
import unittest
from pathlib import Path

from kaitori_collector.contracts import ExtractedRow, JobRequest, ReviewAction
from kaitori_collector.storage import Repository


def sample_row() -> ExtractedRow:
    return ExtractedRow(
        gallery_id="tcggame",
        post_title="판매 카드",
        post_url="https://example.test/post/1",
        posted_at="2026-08-12T10:00:00+09:00",
        card_name="블루아이즈",
        rarity="울레",
        raw_price="35000",
        price_krw=35000,
        price_unit="원 명시",
        quantity=1,
        shipping_included=True,
        shipping_price_krw=None,
        review_status="parsed",
        review_reason="",
        raw_line="블루아이즈 울레 35000원 택포",
    )


class StorageTests(unittest.TestCase):
    def test_risk_analysis_lookup_has_post_family_index(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")

            indexes = {row[1] for row in repo.connection.execute("PRAGMA index_list(kaitori_sources)").fetchall()}

            self.assertIn("kaitori_sources_post_family_idx", indexes)
            self.assertIn("kaitori_sources_gallery_url_idx", indexes)
            self.assertIn("kaitori_sources_gallery_post_idx", indexes)
            self.assertIn("kaitori_sources_seller_listing_idx", indexes)
            row_indexes = {row[1] for row in repo.connection.execute("PRAGMA index_list(kaitori_rows)").fetchall()}
            self.assertIn("kaitori_rows_source_idx", row_indexes)
            repo.close()

    def test_find_source_falls_back_to_gallery_post_id(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            source_id, _ = repo.upsert_source({
                "gallery_id": "tcggame",
                "post_id": "7",
                "post_url": "https://example.test/post/7?no=7",
                "title": "?먮ℓ 移대뱶",
                "posted_at": "2026-08-12T10:00:00+09:00",
                "raw_html": "<html>sale</html>",
            })

            found = repo.find_source_for_post("tcggame", "https://example.test/post/7?no=7&from=list")

            self.assertEqual(found["id"], source_id)
            repo.close()

    def test_attaching_existing_source_also_attaches_existing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            first_job = repo.create_job(JobRequest(gallery_id="tcggame"))
            second_job = repo.create_job(JobRequest(gallery_id="tcggame"))
            source_id, _ = repo.upsert_source({
                "gallery_id": "tcggame",
                "post_id": "1",
                "post_url": "https://example.test/post/1",
                "title": "판매 카드",
                "posted_at": "2026-08-12T10:00:00+09:00",
                "raw_html": "<html>sale</html>",
            })
            repo.attach_source_to_job(first_job, source_id)
            repo.insert_rows(first_job, source_id, [sample_row()])

            repo.attach_source_to_job(second_job, source_id)

            self.assertEqual(len(repo.list_rows(job_id=second_job)), 1)
            repo.close()

    def test_find_latest_job_matches_collection_watermark(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            cutoff_at = "2026-08-13T17:09:45+09:00"
            job_id = repo.create_job(JobRequest(
                gallery_id="tcggame",
                since="2026-02-14",
                until="2026-08-13",
                cutoff_at=cutoff_at,
            ))

            found = repo.find_latest_job("tcggame", "2026-02-14", "2026-08-13", cutoff_at)

            self.assertIsNotNone(found)
            self.assertEqual(found["id"], job_id)
            self.assertIsNone(repo.find_latest_job("tcggame", "2026-02-14", "2026-08-13", "2026-08-13T17:09:46+09:00"))
            repo.close()

    def test_same_source_and_row_are_idempotent_and_reviews_are_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            source = {
                "gallery_id": "tcggame",
                "post_id": "1",
                "post_url": "https://example.test/post/1",
                "title": "판매 카드",
                "posted_at": "2026-08-12T10:00:00+09:00",
                "raw_html": "<html>sale</html>",
            }

            first_source_id, inserted = repo.upsert_source(source)
            second_source_id, inserted_again = repo.upsert_source(source)

            self.assertEqual(first_source_id, second_source_id)
            self.assertTrue(inserted)
            self.assertFalse(inserted_again)
            repo.upsert_source({**source, "author_name": "카드상인", "author_type": "registered"})
            self.assertEqual(repo.get_source(first_source_id)["author_name"], "카드상인")
            self.assertEqual(repo.get_source(first_source_id)["author_type"], "registered")
            self.assertEqual(repo.insert_rows(job_id, first_source_id, [sample_row()]), 1)
            self.assertEqual(repo.insert_rows(job_id, first_source_id, [sample_row()]), 0)

            row = repo.list_rows(job_id=job_id)[0]
            repo.record_review(row["id"], ReviewAction(action="edit", actor="reviewer", after_data={"rarity": "시크"}))
            repo.record_review(row["id"], ReviewAction(action="approve", actor="reviewer"))

            self.assertEqual(len(repo.list_reviews(row["id"])), 2)
            exported = repo.export_approved_rows(job_id)
            self.assertEqual(len(exported), 1)
            self.assertEqual(exported[0]["status"], "exported")
            self.assertEqual(repo.export_approved_rows(job_id), [])
            self.assertEqual(repo.list_rows(job_id=job_id)[0]["status"], "exported")
            repo.close()

    def test_reprocess_quality_backfills_completed_and_price_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            job_id = repo.create_job(JobRequest(gallery_id="tcggame"))
            source_id, _ = repo.upsert_source({
                "gallery_id": "tcggame",
                "post_url": "https://example.test/post/quality",
                "title": "판매 카드 거래완료",
                "raw_html": '<span class="title_subject">판매 카드 거래완료</span><div class="write_div">블루아이즈 35,000원 거래완료</div>',
            })
            repo.attach_source_to_job(job_id, source_id)
            repo.insert_rows(job_id, source_id, [sample_row()])
            repo.connection.execute("UPDATE kaitori_rows SET price_status = 'unknown', price_scope = 'unknown', analysis_status = 'needs_review'")
            repo.connection.commit()

            counts = repo.reprocess_quality()
            processed = repo.list_rows(job_id=job_id)[0]

            self.assertEqual(counts["sources"], 1)
            self.assertEqual(counts["rows"], 1)
            self.assertEqual(processed["post_status"], "completed")
            self.assertEqual(processed["price_status"], "exact")
            self.assertEqual(processed["analysis_status"], "context_only")
            self.assertEqual(processed["price_krw_observed"], 35000)
            repo.close()


if __name__ == "__main__":
    unittest.main()
