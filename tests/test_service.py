import tempfile
import unittest
from pathlib import Path

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


LIST_HTML = """
<table><tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&amp;no=1">첫 글</a></td></tr></table>
"""
LIST_PAGE_2_HTML = """
<table><tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&amp;no=2">오래된 글</a></td></tr></table>
"""
LIST_PAGE_3_HTML = """
<table><tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&amp;no=3">더 오래된 글</a></td></tr></table>
"""
POST_HTML = """
<html><head><input type="hidden" name="ci_t" value="fixture-token"><script type="application/ld+json">
{"headline":"판매 카드","datePublished":"2026-08-12T10:00:00+09:00","articleBody":"블루아이즈 울레 35,000원 택포"}
</script></head><body><span class="title_subject">판매 카드</span><div class="write_div">블루아이즈 울레 35,000원 택포</div></body></html>
"""
OLD_POST_HTML = POST_HTML.replace("2026-08-12T10:00:00+09:00", "2026-05-12T10:00:00+09:00")
COMMENT_HTML = """
<div class="gallery_re_contents"><table><tr class="reply_line">
<td class="user user_layer" user_name="거래상대" user_id="dealer01">거래상대</td>
<td class="reply">구매 의사 있어요.</td><td class="retime">2026-08-12 10:20:00</td>
</tr></table></div>
"""
MOBILE_POST_WITH_COMMENTS = """
<html><head><script type="application/ld+json">
{"headline":"판매 카드","datePublished":"2026-08-12T10:00:00+09:00","articleBody":"블루아이즈 울레 35,000원 택포"}
</script></head><body>
<span class="gallview-tit-box"><button class="nick">판매자</button><span class="sp-nick gonick"></span></span>
<div class="thum-txtin">블루아이즈 울레 35,000원 택포</div>
<ul class="all-comment-lst"><li class="comment" no="88"><div class="ginfo-area"><button class="nick">구매자</button><span class="sp-nick gonick"></span></div><p class="txt">구매할게요.</p><span class="date">08.12 10:20</span></li></ul>
</body></html>
"""


class JobServiceTests(unittest.TestCase):
    def test_backfill_stops_after_a_page_wholly_older_than_since(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            calls: list[str] = []

            def fetcher(url: str) -> str:
                calls.append(url)
                if "lists" in url:
                    if "page=2" in url:
                        return LIST_PAGE_2_HTML
                    if "page=3" in url:
                        return LIST_PAGE_3_HTML
                    return LIST_HTML
                if "no=2" in url:
                    return OLD_POST_HTML
                return POST_HTML

            service = JobService(repo, fetcher=fetcher, sleep=lambda _: None)
            request = JobRequest(
                gallery_id="tcggame",
                subject="판매",
                subjects=("판매",),
                since="2026-05-13",
                until="2026-08-13",
                max_posts=20,
                max_pages=20,
                delay=0,
            )
            job_id = service.create_job(request, start=False)

            status = service.run_job(job_id)

            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["counts"]["sources"], 1)
            self.assertTrue(any("page=2" in url for url in calls))
            self.assertFalse(any("page=3" in url for url in calls))
            repo.close()

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

    def test_structure_changed_list_is_retried_before_failing(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            calls = {"list": 0}

            def shape_flaky_fetcher(url: str) -> str:
                if "lists" in url:
                    calls["list"] += 1
                    if calls["list"] == 1:
                        return "<html><head><title>잠시만 기다려 주세요</title></head><body>retry</body></html>"
                    return LIST_HTML
                return POST_HTML

            service = JobService(repo, fetcher=shape_flaky_fetcher, sleep=lambda _: None)
            job_id = service.create_job(JobRequest(gallery_id="tcggame", max_posts=1, max_retries=1), start=False)

            status = service.run_job(job_id)

            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["counts"]["rows"], 1)
            self.assertEqual(calls["list"], 2)
            self.assertTrue(any("구조" in log["message"] and "재시도" in log["message"] for log in service.get_logs(job_id)))
            repo.close()

    def test_job_collects_public_comments_and_author_type(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            service = JobService(
                repo,
                fetcher=lambda url: LIST_HTML if "lists" in url else POST_HTML,
                comment_fetcher=lambda post_url, gallery_id, post_number, ci_t, page: COMMENT_HTML,
            )
            job_id = service.create_job(JobRequest(gallery_id="tcggame", max_posts=1), start=False)

            status = service.run_job(job_id)

            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["counts"]["comments"], 1)
            comments = repo.list_comments(job_id=job_id)
            self.assertEqual(comments[0]["author_name"], "거래상대")
            self.assertEqual(comments[0]["author_type"], "registered")
            repo.close()

    def test_job_collects_inline_mobile_comments_without_comment_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "kaitori.sqlite3")
            service = JobService(
                repo,
                fetcher=lambda url: LIST_HTML if "lists" in url else MOBILE_POST_WITH_COMMENTS,
                comment_fetcher=lambda *_args: "",
            )
            job_id = service.create_job(JobRequest(gallery_id="tcggame", max_posts=1), start=False)

            status = service.run_job(job_id)

            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["counts"]["comments"], 1)
            comments = repo.list_comments(job_id=job_id)
            self.assertEqual(comments[0]["author_name"], "구매자")
            self.assertEqual(comments[0]["author_type"], "registered")
            repo.close()


if __name__ == "__main__":
    unittest.main()
