"""Threaded HTTP server adapter for the worker application."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Type

from .api import WorkerApplication
from .service import JobService
from .storage import Repository


def make_handler(application: WorkerApplication) -> Type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "KaitoriCollector/0.1"

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_OPTIONS(self) -> None:
            self._dispatch("OPTIONS")

        def _dispatch(self, method: str) -> None:
            payload = None
            if method == "POST":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length) if length else b"{}"
                    payload = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._write(400, {"error": "request body must be valid JSON"})
                    return
            response = application.request(method, self.path, payload, dict(self.headers.items()))
            self._write(response.status, response.body, response.content_type)

        def _write(self, status: int, body: object, content_type: str = "application/json; charset=utf-8") -> None:
            raw = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            if raw:
                self.wfile.write(raw)

        def log_message(self, _format: str, *args: object) -> None:
            return

    return RequestHandler


def serve(host: str, port: int, db_path: Path, data_root: Path, api_token: str) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    repository = Repository(db_path)
    application = WorkerApplication(JobService(repository), api_token=api_token)
    server = ThreadingHTTPServer((host, port), make_handler(application))
    try:
        print(f"kaitori collector listening on http://{host}:{port}")
        server.serve_forever()
    finally:
        server.server_close()
        repository.close()
