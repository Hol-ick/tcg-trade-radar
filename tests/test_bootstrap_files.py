from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootstrapFileTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_setup_script_is_location_independent_and_uses_venv(self) -> None:
        text = self.read("debug/setup-trade-radar.bat")
        self.assertIn("%~dp0", text)
        self.assertIn(".venv\\Scripts\\python.exe", text)
        self.assertIn("py -3.11", text)
        self.assertIn("pip install -e .", text)
        self.assertIn("--skip-browser", text)
        self.assertNotIn("KAITORI_API_TOKEN=", text)

    def test_batch_files_use_windows_line_endings(self) -> None:
        for relative in ("TCG Trade Radar.bat", "debug/setup-trade-radar.bat", "debug/checkhost.bat"):
            raw = (ROOT / relative).read_bytes()
            self.assertIn(b"\r\n", raw, relative)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), relative)

        self.assertIn(".venv/", self.read(".gitignore"))

    def test_root_launcher_runs_setup_only_once_and_prefers_virtual_environment(self) -> None:
        launcher = self.read("TCG Trade Radar.bat")
        self.assertIn(".venv\\Scripts\\python.exe", launcher)
        self.assertIn("FIRST_RUN_MARKER", launcher)
        self.assertIn('if exist "%FIRST_RUN_MARKER%" goto :launch', launcher)
        self.assertIn('call "%ROOT%\\debug\\setup-trade-radar.bat" --no-pause', launcher)
        self.assertIn('call "%ROOT%\\debug\\checkhost.bat" --skip-network', launcher)
        self.assertIn("trade_radar_desktop.py", launcher)
        self.assertNotIn("run-kaitori.bat", launcher)

    def test_guide_mentions_first_run_and_troubleshooting(self) -> None:
        guide = self.read("docs/windows-setup.md")
        for phrase in ("setup-trade-radar.bat", "checkhost.bat", "Python 3.11", "Playwright", "GitHub Pages"):
            self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
