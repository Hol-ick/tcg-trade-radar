from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "debug" / "checkhost.py"
SPEC = importlib.util.spec_from_file_location("checkhost", MODULE_PATH)
assert SPEC and SPEC.loader
CHECKHOST = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKHOST
SPEC.loader.exec_module(CHECKHOST)


class CheckhostTests(unittest.TestCase):
    def test_parse_python_version(self) -> None:
        self.assertEqual(CHECKHOST.parse_python_version("Python 3.12.4"), (3, 12, 4))
        self.assertEqual(CHECKHOST.parse_python_version("3.11.9"), (3, 11, 9))
        self.assertIsNone(CHECKHOST.parse_python_version("Python unknown"))

    def test_classify_response_distinguishes_empty_and_blocked(self) -> None:
        self.assertEqual(CHECKHOST.classify_response(200, 42), "ok")
        self.assertEqual(CHECKHOST.classify_response(200, 0), "empty")
        self.assertEqual(CHECKHOST.classify_response(403, 128), "blocked")
        self.assertEqual(CHECKHOST.classify_response(None, 0, error_type="TimeoutError"), "error")

    def test_environment_report_does_not_include_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = CHECKHOST.build_environment_report(root, executable=sys.executable)
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("Authorization", encoded)
        self.assertNotIn("Bearer", encoded)
        self.assertIn("python_supported", report)
        self.assertIn("packages", report)

    def test_default_targets_are_read_only_https_urls(self) -> None:
        self.assertTrue(CHECKHOST.DEFAULT_TARGETS)
        self.assertTrue(all(url.startswith("https://") for url in CHECKHOST.DEFAULT_TARGETS))
        self.assertTrue(all("/write" not in url and "/comment" not in url for url in CHECKHOST.DEFAULT_TARGETS))


if __name__ == "__main__":
    unittest.main()
