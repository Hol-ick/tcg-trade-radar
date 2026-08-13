"""Single-process PySide6 desktop application for TCG Trade Radar.

The collector runs in this process. There is no HTTP worker or browser-to-local
server bridge: the UI starts ``JobService`` directly and reads the same SQLite
database for the explorer, seller review signals and CSV export.
"""
from __future__ import annotations

import csv
import math
import sys
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


PRESETS = [
    {"name": "유희왕", "id": "tcggame", "subject": "판매", "subjects": ("판매", "구매", "거래", "판매/거래")},
    {"name": "원피스 카드게임", "id": "onepiececardgame", "subject": "판매", "subjects": ("판매", "구매", "거래", "판매/거래")},
    {"name": "포켓몬 카드", "id": "pokemoncardgame", "subject": "판매", "subjects": ("판매", "구매", "거래", "판매/거래")},
    {"name": "디지몬 카드", "id": "digimontcg", "subject": "거래", "subjects": ("판매", "구매", "거래", "판매/거래")},
    {"name": "뱅드림", "id": "vg", "subject": "거래", "subjects": ("판매", "구매", "거래", "판매/거래")},
]

GAME_LABELS = {item["id"]: item["name"] for item in PRESETS}
TYPE_LABELS = {"sell": "판매", "buy": "구매", "trade": "교환", "unknown": "미분류"}
DEMAND_LABELS = {"hot_demand": "구매 수요 높음", "balanced": "균형", "supply_heavy": "판매 우세", "stale_demand": "오래된 수요", "unknown": "확인 필요"}
QUALITY_LABELS = {"observed": "관측", "low_sample": "표본 적음", "needs_review": "검토 필요"}
REVIEW_LABELS = {"watching": "관찰 중", "safe": "안전 표시", "confirmed": "검토자 확인", "noted": "메모 있음", "unreviewed": "자동 분석"}


def today_range(days: int = 7) -> tuple[str, str]:
    until = date.today()
    return (until - timedelta(days=max(1, days) - 1)).isoformat(), until.isoformat()


def money(value: Any) -> str:
    return f"{int(value):,}원" if value not in (None, "", 0) else "-"


def make_collection_request(game_id: str, *, days: int = 7, max_posts: int = 50, since: str | None = None, until: str | None = None) -> JobRequest:
    game = next((item for item in PRESETS if item["id"] == game_id), PRESETS[0])
    max_posts = max(1, min(int(max_posts), 200))
    range_start, range_end = today_range(days)
    return JobRequest(
        gallery_id=game["id"],
        gallery_url=f"https://gall.dcinside.com/mgallery/board/lists?id={game['id']}",
        subject=game["subject"],
        subjects=game["subjects"],
        since=since or range_start,
        until=until or range_end,
        max_posts=max_posts,
        max_pages=max(1, math.ceil(max_posts / 50)),
        delay=0.5,
        buy_rate=60,
        keep_raw=True,
        review_unmatched=True,
    )


def market_display_row(item: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(item.get("card_name_normalized") or item.get("card_name_raw") or "미확인 카드"),
        GAME_LABELS.get(str(item.get("gallery_id") or ""), str(item.get("gallery_id") or "-")),
        str(item.get("sell_count") or 0),
        str(item.get("buy_count") or 0),
        str(item.get("recent_buy_count") or 0),
        money(item.get("sell_price_median")),
        money(item.get("wanted_price_median")),
        f"{float(item.get('demand_score') or 0):.2f}",
        DEMAND_LABELS.get(str(item.get("demand_status") or "unknown"), "확인 필요"),
        QUALITY_LABELS.get(str(item.get("quality_status") or "needs_review"), "검토 필요"),
    )


def seller_display_row(item: dict[str, Any]) -> tuple[str, ...]:
    level = str(item.get("risk_level") or "low")
    risk = {"high": "높은", "medium": "주의", "low": "낮은"}.get(level, "낮은")
    return (
        str(item.get("display_name") or "미상"),
        "고정 닉네임" if item.get("author_type") == "registered" else "유동 / 게시글 단위",
        f"전체 {int(item.get('observed_post_count') or 0)} · 판매 {int(item.get('sell_post_count') or 0)} · 구매 {int(item.get('buy_post_count') or 0)}",
        f"반복 {int(item.get('repost_count') or 0)}",
        f"{risk} {int(item.get('risk_score') or 0)}",
        f"신호 {int(item.get('open_signal_count') or 0)} · {REVIEW_LABELS.get(str(item.get('review_status') or 'unreviewed'), '자동 분석')}",
    )


def load_korean_ui_font() -> str:
    """Load Windows' bundled Korean UI font when Qt cannot discover it itself."""
    candidates = [Path("C:/Windows/Fonts/malgun.ttf"), Path("C:/Windows/Fonts/gulim.ttc")]
    for candidate in candidates:
        if candidate.exists():
            font_id = QFontDatabase.addApplicationFont(str(candidate))
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    return families[0]
    return "Segoe UI"


class MetricCard(QFrame):
    def __init__(self, label: str, color: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.setProperty("accent", color)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(5)
        caption = QLabel(label)
        caption.setObjectName("metricCaption")
        self.value = QLabel("0")
        self.value.setObjectName("metricValue")
        layout.addWidget(caption)
        layout.addWidget(self.value)

    def set_value(self, value: str | int) -> None:
        self.value.setText(str(value))


class NavButton(QPushButton):
    def __init__(self, symbol: str, label: str) -> None:
        super().__init__(f"{symbol}  {label}")
        self.setCheckable(True)
        self.setObjectName("navButton")


class TradeRadarDesktop(QMainWindow):
    def __init__(self, database: Path | None = None) -> None:
        super().__init__()
        self.database = database or PROJECT_ROOT / ".audit" / "kaitori.sqlite3"
        self.repo = Repository(self.database)
        self.service = JobService(self.repo)
        self.job_id: str | None = None
        self.running = False
        self.last_log_count = 0
        self._nav: list[NavButton] = []
        self._market_rows: list[dict[str, Any]] = []
        self._build_window()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_collection)
        self._refresh_all()

    def _build_window(self) -> None:
        self.setWindowTitle("TCG Trade Radar")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 700)
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        side.setSpacing(7)
        mark = QLabel("TCG")
        mark.setObjectName("brandMark")
        title = QLabel("TRADE\nRADAR")
        title.setObjectName("brandTitle")
        side.addWidget(mark)
        side.addWidget(title)
        side.addWidget(self._small_label("LOCAL COLLECTOR / SQLite"))
        side.addSpacing(24)
        for symbol, label in [("◈", "대시보드"), ("◉", "실시간 수집"), ("⌕", "매물 탐색"), ("▤", "보유 카드 수요"), ("↗", "거래 동향"), ("⚑", "판매자 신호")]:
            button = NavButton(symbol, label)
            button.clicked.connect(lambda checked=False, index=len(self._nav): self._select_page(index))
            self._nav.append(button)
            side.addWidget(button)
        side.addStretch(1)
        local = QLabel("이 앱 안에서 수집합니다.\n별도 워커 연결 없음")
        local.setObjectName("localBadge")
        local.setWordWrap(True)
        side.addWidget(local)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 24, 30, 24)
        content_layout.setSpacing(18)
        content_layout.addLayout(self._header())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_collection_page())
        self.pages.addWidget(self._build_market_page())
        self.pages.addWidget(self._build_inventory_page())
        self.pages.addWidget(self._build_trends_page())
        self.pages.addWidget(self._build_sellers_page())
        content_layout.addWidget(self.pages, 1)
        outer.addWidget(content, 1)
        self._select_page(0)
        self.setStyleSheet(APP_QSS)

    def _header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.page_title = QLabel("시장 신호판")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("수집된 거래글에서 움직임을 찾습니다")
        self.page_subtitle.setObjectName("pageSubtitle")
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)
        self.connection = QLabel("● 로컬 모드")
        self.connection.setObjectName("connectionBadge")
        layout.addWidget(self.connection, alignment=Qt.AlignmentFlag.AlignTop)
        return layout

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        intro = QFrame()
        intro.setObjectName("heroPanel")
        box = QHBoxLayout(intro)
        box.setContentsMargins(26, 24, 26, 24)
        copy = QVBoxLayout()
        headline = QLabel("카드 거래의 온도를\n바로 읽습니다.")
        headline.setObjectName("heroTitle")
        sub = QLabel("수집은 이 프로그램 안에서 실행되고, 결과는 SQLite와 CSV로 남습니다.")
        sub.setObjectName("heroDescription")
        sub.setWordWrap(True)
        open_collect = QPushButton("수집 시작하기  →")
        open_collect.setObjectName("primaryButton")
        open_collect.clicked.connect(lambda: self._select_page(1))
        copy.addWidget(headline)
        copy.addSpacing(6)
        copy.addWidget(sub)
        copy.addSpacing(16)
        copy.addWidget(open_collect, alignment=Qt.AlignmentFlag.AlignLeft)
        box.addLayout(copy, 2)
        signal = QLabel("BUY\n↗\nSELL")
        signal.setObjectName("signalArt")
        signal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(signal, 1)
        layout.addWidget(intro)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.dashboard_cards = [MetricCard("관측 카드", "blue"), MetricCard("최근 구매 수요", "mint"), MetricCard("판매 매물", "violet"), MetricCard("주의 판매자", "orange")]
        for card in self.dashboard_cards:
            cards.addWidget(card)
        layout.addLayout(cards)
        recent = self._panel("최근 시장 신호")
        recent_layout = QVBoxLayout(recent)
        self.dashboard_table = self._table(["카드", "게임", "판매", "구매", "판매 중앙가", "상태"], [230, 150, 70, 70, 120, 160])
        recent_layout.addWidget(self.dashboard_table)
        layout.addWidget(recent, 1)
        return page

    def _build_collection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        controls = self._panel("수집 설정")
        grid = QGridLayout(controls)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.collect_game = QComboBox()
        self.collect_game.addItems([item["name"] for item in PRESETS])
        self.collect_start = QDateEdit(QDate.currentDate().addDays(-6))
        self.collect_end = QDateEdit(QDate.currentDate())
        for widget in (self.collect_start, self.collect_end):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy.MM.dd")
        self.collect_posts = QSpinBox()
        self.collect_posts.setRange(1, 200)
        self.collect_posts.setValue(50)
        self.collect_button = QPushButton("▶  수집 시작")
        self.collect_button.setObjectName("primaryButton")
        self.collect_button.clicked.connect(self._start_collection)
        self.collect_status = QLabel("준비됨 · 이 앱 안에서 수집합니다")
        self.collect_status.setObjectName("statusText")
        for column, (label, widget) in enumerate([( "게임", self.collect_game), ("시작일", self.collect_start), ("종료일", self.collect_end), ("최근 글 수", self.collect_posts)]):
            grid.addWidget(self._small_label(label), 0, column)
            grid.addWidget(widget, 1, column)
        grid.addWidget(self._small_label("실행"), 0, 4)
        grid.addWidget(self.collect_button, 1, 4)
        grid.addWidget(self.collect_status, 2, 0, 1, 5)
        layout.addWidget(controls)
        split = QHBoxLayout()
        split.setSpacing(14)
        log_panel = self._panel("수집 로그")
        log_layout = QVBoxLayout(log_panel)
        log_head = QHBoxLayout()
        self.log_count = QLabel("원문 0 · 결과 0 · 댓글 0")
        self.log_count.setObjectName("tableHint")
        copy_log = QPushButton("로그 복사")
        copy_log.setObjectName("ghostButton")
        copy_log.clicked.connect(self._copy_logs)
        log_head.addWidget(self.log_count)
        log_head.addStretch(1)
        log_head.addWidget(copy_log)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        log_layout.addLayout(log_head)
        log_layout.addWidget(self.log_view, 1)
        split.addWidget(log_panel, 1)
        result_panel = self._panel("이번 수집 결과")
        result_layout = QVBoxLayout(result_panel)
        result_head = QHBoxLayout()
        self.result_info = QLabel("수집 결과가 여기에 표시됩니다")
        self.result_info.setObjectName("tableHint")
        export = QPushButton("CSV 저장")
        export.setObjectName("ghostButton")
        export.clicked.connect(self._export_job_csv)
        result_head.addWidget(self.result_info)
        result_head.addStretch(1)
        result_head.addWidget(export)
        self.result_table = self._table(["카드", "유형", "가격", "판매자", "위험", "원문"], [220, 70, 100, 130, 100, 75])
        self.result_table.cellDoubleClicked.connect(self._open_selected_result)
        result_layout.addLayout(result_head)
        result_layout.addWidget(self.result_table, 1)
        split.addWidget(result_panel, 1)
        layout.addLayout(split, 1)
        return page

    def _build_market_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        filters = self._panel("카드 시장 탐색")
        line = QHBoxLayout(filters)
        line.setContentsMargins(18, 15, 18, 15)
        self.market_query = QLineEdit()
        self.market_query.setPlaceholderText("카드명 또는 코드 검색")
        self.market_game = QComboBox()
        self.market_game.addItem("전체 게임", "")
        for item in PRESETS:
            self.market_game.addItem(item["name"], item["id"])
        self.market_days = QSpinBox()
        self.market_days.setRange(1, 365)
        self.market_days.setValue(30)
        refresh = QPushButton("검색")
        refresh.setObjectName("primaryButton")
        refresh.clicked.connect(self._refresh_market)
        export = QPushButton("요약 CSV")
        export.setObjectName("ghostButton")
        export.clicked.connect(self._export_market_csv)
        line.addWidget(self.market_query, 2)
        line.addWidget(self.market_game, 1)
        line.addWidget(self._small_label("최근"))
        line.addWidget(self.market_days)
        line.addWidget(refresh)
        line.addWidget(export)
        layout.addWidget(filters)
        table_panel = self._panel("카드별 판매·구매 동향")
        table_layout = QVBoxLayout(table_panel)
        self.market_hint = QLabel("")
        self.market_hint.setObjectName("tableHint")
        self.market_table = self._table(["카드", "게임", "판매", "구매", "최근 구매", "판매 중앙가", "희망가", "수요", "상태", "신뢰도"], [220, 130, 65, 65, 85, 110, 110, 75, 135, 90])
        table_layout.addWidget(self.market_hint)
        table_layout.addWidget(self.market_table, 1)
        layout.addWidget(table_panel, 1)
        return page

    def _build_inventory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        top = self._panel("보유 카드의 구매 수요 찾기")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(20, 18, 20, 18)
        self.inventory_input = QTextEdit()
        self.inventory_input.setPlaceholderText("카드명을 한 줄에 하나씩 입력하세요\n예: 블루아이즈\n예: 리자몽")
        self.inventory_input.setFixedHeight(110)
        self.inventory_game = QComboBox()
        self.inventory_game.addItem("전체 게임", "")
        for item in PRESETS:
            self.inventory_game.addItem(item["name"], item["id"])
        find = QPushButton("수요 찾기")
        find.setObjectName("primaryButton")
        find.clicked.connect(self._refresh_inventory)
        right = QVBoxLayout()
        right.addWidget(self._small_label("게임"))
        right.addWidget(self.inventory_game)
        right.addSpacing(10)
        right.addWidget(find)
        right.addStretch(1)
        top_layout.addWidget(self.inventory_input, 3)
        top_layout.addLayout(right, 1)
        layout.addWidget(top)
        result = self._panel("구매 수요가 관측된 카드")
        result_layout = QVBoxLayout(result)
        self.inventory_table = self._table(["카드", "게임", "구매", "판매", "최근 구매", "희망가", "수요", "상태"], [250, 140, 70, 70, 90, 110, 80, 140])
        result_layout.addWidget(self.inventory_table)
        layout.addWidget(result, 1)
        return page

    def _build_trends_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        top = self._panel("거래 동향 스냅샷")
        row = QHBoxLayout(top)
        row.setContentsMargins(18, 15, 18, 15)
        self.trend_game = QComboBox()
        for item in PRESETS:
            self.trend_game.addItem(item["name"], item["id"])
        self.trend_days = QSpinBox()
        self.trend_days.setRange(1, 365)
        self.trend_days.setValue(30)
        create = QPushButton("현재 데이터로 스냅샷 만들기")
        create.setObjectName("primaryButton")
        create.clicked.connect(self._create_snapshot)
        refresh = QPushButton("새로고침")
        refresh.setObjectName("ghostButton")
        refresh.clicked.connect(self._refresh_trends)
        row.addWidget(self._small_label("게임"))
        row.addWidget(self.trend_game)
        row.addWidget(self._small_label("최근"))
        row.addWidget(self.trend_days)
        row.addStretch(1)
        row.addWidget(refresh)
        row.addWidget(create)
        layout.addWidget(top)
        panel = self._panel("일별 거래 동향")
        body = QVBoxLayout(panel)
        self.trend_hint = QLabel("")
        self.trend_hint.setObjectName("tableHint")
        self.trend_table = self._table(["기준일", "카드", "판매", "구매", "최근 구매", "판매 중앙가", "희망가", "수요 비율", "점수", "신뢰도"], [105, 230, 65, 65, 90, 110, 110, 90, 80, 90])
        body.addWidget(self.trend_hint)
        body.addWidget(self.trend_table, 1)
        layout.addWidget(panel, 1)
        return page

    def _build_sellers_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        top = self._panel("판매자 활동 신호")
        row = QHBoxLayout(top)
        row.setContentsMargins(18, 15, 18, 15)
        self.seller_game = QComboBox()
        self.seller_game.addItem("전체 게임", "")
        for item in PRESETS:
            self.seller_game.addItem(item["name"], item["id"])
        self.seller_query = QLineEdit()
        self.seller_query.setPlaceholderText("닉네임 검색")
        refresh = QPushButton("새로고침")
        refresh.setObjectName("primaryButton")
        refresh.clicked.connect(self._refresh_sellers)
        note = QLabel("위험도는 사기 확정이 아닌, 사람이 검토할 우선순위입니다.")
        note.setObjectName("tableHint")
        row.addWidget(self.seller_query, 1)
        row.addWidget(self.seller_game)
        row.addWidget(refresh)
        row.addWidget(note)
        layout.addWidget(top)
        panel = self._panel("판매자 프로필")
        body = QVBoxLayout(panel)
        self.seller_hint = QLabel("")
        self.seller_hint.setObjectName("tableHint")
        self.seller_table = self._table(["판매자", "식별", "활동", "반복", "위험도", "검토 신호"], [170, 150, 220, 90, 100, 240])
        body.addWidget(self.seller_hint)
        body.addWidget(self.seller_table, 1)
        layout.addWidget(panel, 1)
        return page

    def _panel(self, title: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setProperty("panelTitle", title)
        return panel

    def _small_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("smallLabel")
        return label

    def _table(self, headers: list[str], widths: list[int]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setObjectName("dataTable")
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        for index, width in enumerate(widths):
            header.resizeSection(index, width)
        return table

    def _select_page(self, index: int) -> None:
        titles = [
            ("시장 신호판", "수집된 거래글에서 움직임을 찾습니다"),
            ("실시간 수집", "이 프로그램이 직접 수집하고 기록합니다"),
            ("매물 탐색", "판매·구매 매물과 가격 흐름을 찾습니다"),
            ("보유 카드 수요", "내 카드에 관심 있는 구매글을 찾습니다"),
            ("거래 동향", "날짜별 시장 변화와 수요를 비교합니다"),
            ("판매자 신호", "반복 매물과 검토 신호를 한곳에서 봅니다"),
        ]
        self.pages.setCurrentIndex(index)
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])
        for button_index, button in enumerate(self._nav):
            button.setChecked(button_index == index)
        if index == 2:
            self._refresh_market()
        elif index == 4:
            self._refresh_trends()
        elif index == 5:
            self._refresh_sellers()

    def _set_table(self, table: QTableWidget, rows: list[tuple[str, ...]], accents: dict[int, str] | None = None) -> None:
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if accents and row_index in accents:
                    cell.setForeground(QColor(accents[row_index]))
                table.setItem(row_index, column_index, cell)

    def _refresh_all(self) -> None:
        self._refresh_dashboard()
        self._refresh_market()
        self._refresh_trends()
        self._refresh_sellers()

    def _refresh_dashboard(self) -> None:
        since, until = today_range(30)
        cards = self.repo.summarize_cards(since=since, until=until, limit=500)
        sellers = self.repo.list_sellers(limit=500)
        self.dashboard_cards[0].set_value(len(cards))
        self.dashboard_cards[1].set_value(sum(1 for item in cards if int(item.get("buy_count") or 0) > 0))
        self.dashboard_cards[2].set_value(sum(int(item.get("sell_count") or 0) for item in cards))
        self.dashboard_cards[3].set_value(sum(1 for item in sellers if item.get("risk_level") in {"medium", "high"}))
        rows = [(display[0], display[1], display[2], display[3], display[5], display[8]) for display in (market_display_row(item) for item in cards[:12])]
        self._set_table(self.dashboard_table, rows)

    def _refresh_market(self) -> None:
        since, until = today_range(self.market_days.value())
        self._market_rows = self.repo.summarize_cards(
            query_text=self.market_query.text().strip(), game_id=str(self.market_game.currentData() or ""),
            since=since, until=until, limit=500,
        )
        self.market_hint.setText(f"{len(self._market_rows)}개 카드 · {since} ~ {until}")
        accents = {index: "#ff8a65" for index, item in enumerate(self._market_rows) if item.get("demand_status") == "hot_demand"}
        self._set_table(self.market_table, [market_display_row(item) for item in self._market_rows], accents)

    def _refresh_inventory(self) -> None:
        names = [line.strip() for line in self.inventory_input.toPlainText().splitlines() if line.strip()]
        if not names:
            self._set_table(self.inventory_table, [])
            return
        game_id = str(self.inventory_game.currentData() or "")
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        since, until = today_range(60)
        for name in names:
            for item in self.repo.summarize_cards(query_text=name, game_id=game_id, since=since, until=until, limit=40):
                key = (str(item.get("gallery_id") or ""), str(item.get("card_key") or ""))
                if key not in seen and int(item.get("buy_count") or 0) > 0:
                    seen.add(key)
                    result.append(item)
        rows = [
            (display[0], display[1], display[3], display[2], display[4], display[6], display[7], display[8])
            for display in (market_display_row(item) for item in result)
        ]
        self._set_table(self.inventory_table, rows)

    def _refresh_trends(self) -> None:
        game_id = str(self.trend_game.currentData() or PRESETS[0]["id"])
        rows = self.repo.list_demand_snapshots(game_id=game_id, limit=500)
        self.trend_hint.setText(f"{GAME_LABELS.get(game_id, game_id)} · 스냅샷 {len(rows)}개")
        display = [
            (str(item.get("snapshot_date") or ""), str(item.get("card_name_normalized") or item.get("card_name_raw") or ""), str(item.get("sell_count") or 0), str(item.get("buy_count") or 0), str(item.get("recent_buy_count") or 0), money(item.get("sell_price_median")), money(item.get("wanted_price_median")), f"{float(item.get('demand_ratio') or 0):.2f}", f"{float(item.get('demand_score') or 0):.2f}", QUALITY_LABELS.get(str(item.get("quality_status") or "needs_review"), "검토 필요"))
            for item in rows
        ]
        self._set_table(self.trend_table, display)

    def _create_snapshot(self) -> None:
        game_id = str(self.trend_game.currentData() or PRESETS[0]["id"])
        since, until = today_range(self.trend_days.value())
        count = self.repo.refresh_demand_snapshot(date.today().isoformat(), game_id, since=since, until=until)
        self.trend_hint.setText(f"오늘 스냅샷 생성 완료 · 카드 {count}개")
        self._refresh_trends()

    def _refresh_sellers(self) -> None:
        sellers = self.repo.list_sellers(game_id=str(self.seller_game.currentData() or ""), query_text=self.seller_query.text().strip(), limit=500)
        self.seller_hint.setText(f"{len(sellers)}명 · 위험도는 자동 판정이 아닌 검토 신호입니다")
        accents = {index: "#ff8a65" for index, item in enumerate(sellers) if item.get("risk_level") == "high"}
        accents.update({index: "#ffd166" for index, item in enumerate(sellers) if item.get("risk_level") == "medium"})
        self._set_table(self.seller_table, [seller_display_row(item) for item in sellers], accents)

    def _start_collection(self) -> None:
        if self.running:
            return
        start = self.collect_start.date().toString("yyyy-MM-dd")
        end = self.collect_end.date().toString("yyyy-MM-dd")
        if start > end:
            QMessageBox.warning(self, "기간 확인", "시작일은 종료일보다 늦을 수 없습니다.")
            return
        game = PRESETS[self.collect_game.currentIndex()]
        request = make_collection_request(game["id"], max_posts=self.collect_posts.value(), since=start, until=end)
        self.job_id = self.service.create_job(request, start=False)
        self.running = True
        self.last_log_count = 0
        self.collect_button.setEnabled(False)
        self.collect_status.setText(f"{game['name']} 수집 중 · 이 창을 닫지 마세요")
        self.log_view.clear()
        self.result_table.setRowCount(0)
        threading.Thread(target=self.service.run_job, args=(self.job_id,), daemon=True, name="tcg-collector").start()
        self.poll_timer.start(350)

    def _poll_collection(self) -> None:
        if not self.job_id:
            self.poll_timer.stop()
            return
        job = self.repo.get_job(self.job_id)
        if job is None:
            return
        self._refresh_logs()
        counts = job.get("counts") or {}
        self.log_count.setText(f"원문 {counts.get('sources', 0)} · 결과 {counts.get('rows', 0)} · 댓글 {counts.get('comments', 0)}")
        if job.get("state") not in {"completed", "failed"}:
            return
        self.poll_timer.stop()
        self.running = False
        self.collect_button.setEnabled(True)
        failed = job.get("state") == "failed"
        self.collect_status.setText("수집 실패 · 로그를 확인하세요" if failed else "수집 완료 · 결과를 CSV로 저장할 수 있습니다")
        if failed:
            self.log_view.appendPlainText(f"\n[ERROR] {job.get('error_message') or '알 수 없는 오류'}")
        self._load_job_results()
        self._refresh_all()

    def _refresh_logs(self) -> None:
        if not self.job_id:
            return
        logs = self.repo.list_job_logs(self.job_id, limit=2000)
        for log in logs[self.last_log_count:]:
            detail = log.get("details") if isinstance(log.get("details"), dict) else {}
            compact = " · ".join(f"{key}={value}" for key, value in detail.items() if key in {"url", "rows", "inserted", "comments", "error", "risk_level", "risk_score"} and value not in (None, ""))
            tail = f" · {compact}" if compact else ""
            self.log_view.appendPlainText(f"[{str(log.get('created_at') or '')[-8:]}] {str(log.get('level') or 'info').upper():7} {log.get('message') or ''}{tail}")
        self.last_log_count = len(logs)

    def _load_job_results(self) -> None:
        if not self.job_id:
            return
        rows = self.service.get_results(self.job_id)
        self.result_info.setText(f"{len(rows)}개 행 · 행을 두 번 클릭하면 원문을 엽니다")
        display = [
            (str(item.get("card_name") or item.get("card_name_raw") or "미확인"), TYPE_LABELS.get(str(item.get("listing_type") or "unknown"), "미분류"), money(item.get("price_krw")), str(item.get("seller_name") or item.get("author_name") or "미상"), f"{ {'high': '높은', 'medium': '주의', 'low': '낮은'}.get(str(item.get('seller_risk_level') or 'low'), '낮은')} {int(item.get('seller_risk_score') or 0)}", "열기")
            for item in rows
        ]
        self._set_table(self.result_table, display)
        for index, item in enumerate(rows):
            self.result_table.item(index, 0).setData(Qt.ItemDataRole.UserRole, item.get("source_url") or item.get("post_url") or "")

    def _open_selected_result(self, row: int, _column: int) -> None:
        item = self.result_table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole):
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl(str(item.data(Qt.ItemDataRole.UserRole))))

    def _copy_logs(self) -> None:
        QGuiApplication.clipboard().setText(self.log_view.toPlainText())

    def _export_job_csv(self) -> None:
        if not self.job_id:
            QMessageBox.information(self, "CSV 저장", "먼저 수집을 실행하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "수집 결과 CSV 저장", f"tcg-trade-radar-{date.today():%Y%m%d}.csv", "CSV 파일 (*.csv)")
        if not path:
            return
        rows = self.service.get_results(self.job_id)
        self._write_csv(Path(path), rows)

    def _export_market_csv(self) -> None:
        if not self._market_rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, "시장 요약 CSV 저장", f"tcg-market-{date.today():%Y%m%d}.csv", "CSV 파일 (*.csv)")
        if not path:
            return
        fields = ["card_name_raw", "card_name_normalized", "gallery_id", "sell_count", "buy_count", "recent_buy_count", "sell_price_median", "wanted_price_median", "demand_score", "demand_status", "quality_status"]
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self._market_rows)

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fields = ["card_name", "card_name_raw", "post_title", "listing_type", "price_krw", "quantity", "seller_name", "seller_risk_level", "seller_risk_score", "post_status", "analysis_status", "source_url"]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API spelling
        if self.running:
            choice = QMessageBox.question(self, "수집 진행 중", "수집이 진행 중입니다. 창을 닫을까요?")
            if choice != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.repo.close()
        event.accept()


APP_QSS = """
* { font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif; color: #e8edf7; }
QMainWindow { background: #0b1020; }
#appRoot { background: #0b1020; }
#sidebar { background: #11182c; border-right: 1px solid #26304b; }
#brandMark { color: #09101d; background: #6b8cff; border-radius: 9px; font-size: 13px; font-weight: 800; padding: 8px; max-width: 30px; }
#brandTitle { color: #f6f8ff; font-size: 21px; font-weight: 800; letter-spacing: 1.4px; }
#smallLabel { color: #8f9ab4; font-size: 11px; font-weight: 700; letter-spacing: .5px; }
#navButton { background: transparent; color: #9faac2; border: 0; border-radius: 9px; padding: 11px 12px; font-size: 13px; font-weight: 650; text-align: left; }
#navButton:hover { background: #19233e; color: #edf2ff; }
#navButton:checked { background: #263b71; color: #ffffff; }
#localBadge { color: #97e6c1; background: #173a39; border: 1px solid #275b57; border-radius: 9px; padding: 12px; font-size: 11px; }
#pageTitle { color: #f7f9ff; font-size: 26px; font-weight: 750; }
#pageSubtitle { color: #8f9ab4; font-size: 12px; }
#connectionBadge { color: #8ee9b7; background: #173a39; border: 1px solid #275b57; border-radius: 14px; padding: 7px 10px; font-size: 11px; font-weight: 700; }
#panel { background: #121a2f; border: 1px solid #253252; border-radius: 13px; }
#heroPanel { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a2a57, stop:.56 #172343, stop:1 #301d59); border: 1px solid #42598e; border-radius: 16px; }
#heroTitle { color: #ffffff; font-size: 31px; font-weight: 800; line-height: 1.12; }
#heroDescription { color: #b6c4e8; font-size: 13px; }
#signalArt { color: #d8d1ff; background: rgba(255,255,255,.06); border: 1px solid #596b9e; border-radius: 100px; font-size: 24px; font-weight: 800; letter-spacing: 3px; min-width: 170px; max-width: 170px; min-height: 170px; }
#primaryButton { color: #ffffff; background: #587bff; border: 1px solid #7895ff; border-radius: 8px; padding: 10px 15px; font-size: 13px; font-weight: 750; }
#primaryButton:hover { background: #7090ff; }
#primaryButton:disabled { color: #9ca6bf; background: #253150; border-color: #344364; }
#ghostButton { color: #cbd5ea; background: #18223a; border: 1px solid #354564; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 650; }
#ghostButton:hover { color: #ffffff; border-color: #6b8cff; }
#metricCard { background: #121a2f; border: 1px solid #283658; border-radius: 12px; min-height: 85px; }
#metricCaption { color: #8f9ab4; font-size: 11px; font-weight: 700; }
#metricValue { color: #f4f7ff; font-size: 25px; font-weight: 800; }
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit { background: #0e1528; color: #edf2fb; border: 1px solid #30405f; border-radius: 8px; padding: 8px 10px; font-size: 12px; selection-background-color: #587bff; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus, QTextEdit:focus { border-color: #7190ff; }
QComboBox::drop-down { border: 0; width: 26px; }
QComboBox QAbstractItemView { background: #172039; border: 1px solid #3b4c70; selection-background-color: #304b93; }
#statusText { color: #97e6c1; font-size: 12px; font-weight: 600; padding-top: 8px; }
#tableHint { color: #8f9ab4; font-size: 11px; }
#logView { background: #09101d; border: 1px solid #283858; border-radius: 8px; color: #b8c8e8; font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px; padding: 8px; }
#dataTable { background: #10182c; alternate-background-color: #131f38; border: 1px solid #253252; border-radius: 8px; gridline-color: #24314e; color: #dce5f7; font-size: 12px; }
#dataTable::item { padding: 6px 8px; border-bottom: 1px solid #202d49; }
#dataTable::item:selected { background: #294687; color: #ffffff; }
QHeaderView::section { background: #18233e; color: #91a2c5; border: 0; border-bottom: 1px solid #30405f; padding: 9px 8px; font-size: 10px; font-weight: 750; }
QScrollBar:vertical { background: #10182c; width: 10px; margin: 4px; }
QScrollBar::handle:vertical { background: #3a4d75; border-radius: 5px; min-height: 26px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("TCG Trade Radar")
    app.setFont(QFont(load_korean_ui_font(), 10))
    window = TradeRadarDesktop()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
