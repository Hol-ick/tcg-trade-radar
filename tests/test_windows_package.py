from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_windows_package import build


class WindowsPackageTests(unittest.TestCase):
    def test_build_contains_runtime_and_setup_files_without_local_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = build(Path(temporary), version="test")

            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
                self.assertIn("tcg-trade-radar-windows-test/TCG Trade Radar.bat", names)
                self.assertIn("tcg-trade-radar-windows-test/debug/setup-trade-radar.bat", names)
                self.assertIn("tcg-trade-radar-windows-test/debug/checkhost.bat", names)
                self.assertIn("tcg-trade-radar-windows-test/debug/trade_radar_desktop.py", names)
                self.assertIn("tcg-trade-radar-windows-test/kaitori_collector/service.py", names)
                self.assertIn("tcg-trade-radar-windows-test/PACKAGE-README.txt", names)
                self.assertNotIn("tcg-trade-radar-windows-test/debug/run-kaitori.bat", names)
                self.assertFalse(any(".venv" in name or ".audit" in name for name in names))
                self.assertIsNone(package.testzip())


if __name__ == "__main__":
    unittest.main()
