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


def test_market_and_seller_rows_are_display_ready_without_qt_widgets():
    market = DESKTOP.market_display_row({
        "card_name_raw": "블루아이즈", "card_name_normalized": "Blue-Eyes", "gallery_id": "tcggame",
        "sell_count": 3, "buy_count": 2, "recent_buy_count": 1, "sell_price_median": 35000,
        "wanted_price_median": 31000, "demand_score": 2.5, "demand_status": "hot_demand", "quality_status": "observed",
    })
    seller = DESKTOP.seller_display_row({
        "display_name": "카드상인", "author_type": "registered", "observed_post_count": 4,
        "sell_post_count": 3, "buy_post_count": 1, "repost_count": 1, "risk_level": "medium",
        "risk_score": 35, "open_signal_count": 2, "review_status": "watching",
    })

    assert market[0] == "Blue-Eyes"
    assert market[5] == "35,000원"
    assert market[8] == "구매 수요 높음"
    assert seller[0] == "카드상인"
    assert seller[4] == "주의 35"
    assert seller[5] == "신호 2 · 관찰 중"


def test_desktop_window_has_local_collection_and_explorer_pages(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = DESKTOP.TradeRadarDesktop(tmp_path / "desktop.sqlite3")

    assert window.windowTitle() == "TCG Trade Radar"
    assert window.pages.count() == 6
    assert "워커" not in window.collect_status.text()

    window.close()
