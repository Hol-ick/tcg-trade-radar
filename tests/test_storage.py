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
