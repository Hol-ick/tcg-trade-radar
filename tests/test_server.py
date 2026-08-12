import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from socket import socket

from kaitori_collector.api import WorkerApplication
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


if __name__ == "__main__":
    unittest.main()
