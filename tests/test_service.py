import tempfile
import unittest
from pathlib import Path

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


LIST_HTML = """
<table><tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&amp;no=1">첫 글</a></td></tr></table>
"""
POST_HTML = """
<html><head><script type="application/ld+json">
{"headline":"판매 카드","datePublished":"2026-08-12T10:00:00+09:00","articleBody":"블루아이즈 울레 35,000원 택포"}
</script></head><body><span class="title_subject">판매 카드</span><div class="write_div">블루아이즈 울레 35,000원 택포</div></body></html>
"""


class JobServiceTests(unittest.TestCase):
    def test_job_collects_rows_and_calculates_buy_price_without_mutating_user_price(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            service = JobService(repo, fetcher=lambda url: LIST_HTML if "lists" in url else POST_HTML)
            job_id = service.create_job(JobRequest(gallery_id="tcggame", max_posts=2), start=False)

            service.run_job(job_id)
            service.run_job(job_id)

            job = service.get_job_status(job_id)
            results = service.get_results(job_id)
            self.assertEqual(job["state"], "completed")
            self.assertEqual(job["counts"]["rows"], 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["price_krw"], 35000)
            self.assertEqual(results[0]["buy_price_krw"], 21000)
            repo.close()

    def test_failed_job_can_be_retried_and_existing_rows_are_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            calls = {"count": 0}

            def failing_fetcher(url: str) -> str:
                calls["count"] += 1
                if calls["count"] > 1:
                    raise RuntimeError("fixture fetch failed")
                return LIST_HTML

            service = JobService(repo, fetcher=failing_fetcher)
            job_id = service.create_job(JobRequest(gallery_id="tcggame"), start=False)
            service.run_job(job_id)
            self.assertEqual(service.get_job_status(job_id)["state"], "failed")
            self.assertIn("fixture fetch failed", service.get_job_status(job_id)["error_message"])

            service.retry_job(job_id, start=False)
            self.assertEqual(service.get_job_status(job_id)["state"], "queued")
            repo.close()

    def test_transient_fetch_error_is_retried_and_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            calls = {"list": 0}

            def flaky_fetcher(url: str) -> str:
                if "lists" in url:
                    calls["list"] += 1
                    if calls["list"] == 1:
                        raise OSError("temporary connection reset")
                    return LIST_HTML
                return POST_HTML

            service = JobService(repo, fetcher=flaky_fetcher, sleep=lambda _: None)
            job_id = service.create_job(JobRequest(gallery_id="tcggame", max_retries=1), start=False)

            status = service.run_job(job_id)

            self.assertEqual(status["state"], "completed")
            self.assertTrue(any("재시도" in log["message"] for log in service.get_logs(job_id)))
            repo.close()


if __name__ == "__main__":
    unittest.main()
