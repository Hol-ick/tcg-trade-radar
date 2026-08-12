import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from socket import socket

from kaitori_collector.api import WorkerApplication
from kaitori_collector.contracts import JobRequest
from kaitori_collector.server import make_handler
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository
from http.server import ThreadingHTTPServer


class ServerTests(unittest.TestCase):
    def test_real_http_server_serves_health_and_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory) / "kaitori.sqlite3")
            application = WorkerApplication(JobService(repository, sleep=lambda _: None), api_token="secret", start_jobs=False)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(application))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                connection.request("GET", "/health")
                health = connection.getresponse()
                self.assertEqual(health.status, 200)
                self.assertIn("version", json.loads(health.read()))

                connection.request("POST", "/jobs", body="{}", headers={"Content-Type": "application/json"})
                unauthorized = connection.getresponse()
                self.assertEqual(unauthorized.status, 401)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                repository.close()
                thread.join(timeout=3)

    def test_repository_serializes_job_and_polling_access(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory) / "kaitori.sqlite3")
            request = JobRequest(gallery_id="tcggame")
            job_id = repository.create_job(request)
            barrier = threading.Barrier(2)
            errors = []

            def update_job():
                try:
                    barrier.wait()
                    repository.update_job(job_id, state="running")
                except Exception as error:  # pragma: no cover - assertion below reports it
                    errors.append(error)

            def poll_job():
                try:
                    barrier.wait()
                    for _ in range(20):
                        repository.get_job(job_id)
                except Exception as error:  # pragma: no cover - assertion below reports it
                    errors.append(error)

            first = threading.Thread(target=update_job)
            second = threading.Thread(target=poll_job)
            first.start()
            second.start()
            first.join(timeout=3)
            second.join(timeout=3)
            self.assertFalse(first.is_alive() or second.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(repository.get_job(job_id)["state"], "running")
            repository.close()


if __name__ == "__main__":
    unittest.main()
