from __future__ import annotations

import importlib.util
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

MODULE_PATH = Path(__file__).parents[1] / "debug" / "trade_radar_desktop.py"
SPEC = importlib.util.spec_from_file_location("trade_radar_desktop", MODULE_PATH)
assert SPEC and SPEC.loader
DESKTOP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DESKTOP)


def test_collection_request_uses_selected_preset_and_bounds_post_limit():
    request = DESKTOP.make_collection_request("yugioh", days=7, max_posts=500)

    assert request.gallery_id == "tcggame"
    assert request.max_posts == 200
    assert request.max_pages == 4
    assert request.subjects == ("판매", "구매", "거래", "판매/거래")


def test_desktop_window_is_collection_only_and_has_easy_range_controls(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = DESKTOP.TradeRadarDesktop(tmp_path / "desktop.sqlite3")

    assert window.windowTitle() == "TCG Trade Radar · 실시간 수집"
    assert not hasattr(window, "pages")
    assert window.collect_posts.value() == 50
    assert window.collect_posts_slider.value() == 50
    assert any(button.isChecked() and button.days == 7 for button in window.range_group.buttons())
    assert "워커" not in window.collect_status.text()
    assert not window.export_button.isEnabled()

    window._set_range_days(30)
    assert window.collect_start.date().daysTo(window.collect_end.date()) + 1 == 30
    window.collect_posts.setValue(100)
    assert window.collect_posts_slider.value() == 100
    window._focus_custom_dates()

    window.close()
