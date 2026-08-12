import tempfile
import unittest
from pathlib import Path

from kaitori_collector.api import WorkerApplication
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


LIST_HTML = '<table><tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&amp;no=1">첫 글</a></td></tr></table>'
POST_HTML = '<span class="title_subject">판매 카드</span><div class="write_div">블루아이즈 35,000원 택포</div>'


class ApiTests(unittest.TestCase):
    def make_app(self, token: str = "secret") -> WorkerApplication:
        self.temp = tempfile.TemporaryDirectory()
        repo = Repository(Path(self.temp.name) / "kaitori.sqlite3")
        service = JobService(repo, fetcher=lambda url: LIST_HTML if "lists" in url else POST_HTML, sleep=lambda _: None)
        self.app = WorkerApplication(service, api_token=token, start_jobs=False)
        return self.app

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            self.app.service.repository.close()
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_health_is_public_and_reports_version(self):
        app = self.make_app()

        response = app.request("GET", "/health")

        self.assertEqual(response.status, 200)
        self.assertIn("version", response.body)

    def test_jobs_require_token_and_return_both_id_aliases(self):
        app = self.make_app()
        payload = {"gallery_id": "tcggame", "max_posts": 1, "delay": 0}

        unauthorized = app.request("POST", "/jobs", payload)
        authorized = app.request("POST", "/jobs", payload, {"Authorization": "Bearer secret"})

        self.assertEqual(unauthorized.status, 401)
        self.assertEqual(authorized.status, 202)
        self.assertEqual(authorized.body["job_id"], authorized.body["id"])

    def test_status_review_and_approved_results_are_exposed(self):
        app = self.make_app()
        created = app.request("POST", "/jobs", {"gallery_id": "tcggame", "max_posts": 1, "delay": 0}, {"Authorization": "Bearer secret"})
        job_id = created.body["job_id"]
        app.service.run_job(job_id)

        status = app.request("GET", f"/jobs/{job_id}", headers={"Authorization": "Bearer secret"})
        logs = app.request("GET", f"/jobs/{job_id}/logs", headers={"Authorization": "Bearer secret"})
        comments = app.request("GET", f"/jobs/{job_id}/comments", headers={"Authorization": "Bearer secret"})
        rows = app.request("GET", f"/jobs/{job_id}/results", headers={"Authorization": "Bearer secret"})
        cards = app.request("GET", "/market/cards?game_id=tcggame", headers={"Authorization": "Bearer secret"})
        listings = app.request("GET", "/market/listings?game_id=tcggame&listing_type=sell", headers={"Authorization": "Bearer secret"})
        self.assertEqual(status.status, 200)
        self.assertEqual(logs.status, 200)
        self.assertEqual(comments.status, 200)
        self.assertIn("comments", comments.body)
        self.assertTrue(logs.body["logs"])
        self.assertIn("목록", " ".join(item["message"] for item in logs.body["logs"]))
        self.assertEqual(rows.status, 200)
        self.assertEqual(len(rows.body["rows"]), 1)
        self.assertFalse(rows.body["rows"][0]["exportable"])
        self.assertEqual(cards.status, 200)
        self.assertEqual(cards.body["cards"][0]["sell_count"], 1)
        self.assertIn("demand_ratio", cards.body["cards"][0])
        self.assertIn("quality_status", cards.body["cards"][0])
        self.assertEqual(listings.status, 200)
        self.assertEqual(len(listings.body["rows"]), 1)

        row_id = rows.body["rows"][0]["id"]
        reviewed = app.request("POST", f"/rows/{row_id}/review", {"action": "approve", "actor": "tester"}, {"Authorization": "Bearer secret"})
        self.assertEqual(reviewed.status, 200)
        approved = app.request("GET", f"/jobs/{job_id}/results?approved_only=true", headers={"Authorization": "Bearer secret"})
        self.assertTrue(approved.body["rows"][0]["exportable"])

    def test_csv_export_returns_rows_without_mutating_review_status(self):
        app = self.make_app()
        created = app.request("POST", "/jobs", {"gallery_id": "tcggame", "max_posts": 1, "delay": 0}, {"Authorization": "Bearer secret"})
        job_id = created.body["job_id"]
        app.service.run_job(job_id)

        before = app.request("GET", f"/jobs/{job_id}/results", headers={"Authorization": "Bearer secret"})
        exported = app.request("GET", f"/jobs/{job_id}/csv", headers={"Authorization": "Bearer secret"})
        after = app.request("GET", f"/jobs/{job_id}/results", headers={"Authorization": "Bearer secret"})

        self.assertEqual(exported.status, 200)
        self.assertEqual(exported.content_type, "text/csv; charset=utf-8")
        self.assertIn("gallery_id,post_title,post_url", exported.body)
        self.assertIn("블루아이즈", exported.body)
        self.assertEqual(before.body["rows"][0]["review_status"], after.body["rows"][0]["review_status"])


if __name__ == "__main__":
    unittest.main()
