"""Single-purpose PySide6 desktop collector for TCG Trade Radar.

The desktop app intentionally does one job: collect public trade posts and
let the user save the current job's normalized rows as CSV.  Analysis views
live in the web app; this window is the local collection control deck.
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
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
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

TYPE_LABELS = {"sell": "판매", "buy": "구매", "trade": "교환", "unknown": "미분류"}


def today_range(days: int = 7) -> tuple[str, str]:
    until = date.today()
    return (until - timedelta(days=max(1, days) - 1)).isoformat(), until.isoformat()


def money(value: Any) -> str:
    return f"{int(value):,}원" if value not in (None, "", 0) else "-"


def make_collection_request(
    game_id: str,
    *,
    days: int = 7,
    max_posts: int = 50,
    since: str | None = None,
    until: str | None = None,
) -> JobRequest:
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


class RangeButton(QPushButton):
    def __init__(self, label: str, days: int | None = None) -> None:
        super().__init__(label)
        self.days = days
        self.setCheckable(True)
        self.setObjectName("rangeChip")


class WorkflowStep(QFrame):
    def __init__(self, number: str, title: str, description: str, active: bool = False) -> None:
        super().__init__()
        self.setObjectName("workflowStep")
        self.setProperty("active", "true" if active else "false")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(10)
        number_label = QLabel(number)
        number_label.setObjectName("workflowNumber")
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("workflowTitle")
        description_label = QLabel(description)
        description_label.setObjectName("workflowDescription")
        copy.addWidget(title_label)
        copy.addWidget(description_label)
        layout.addWidget(number_label)
        layout.addLayout(copy, 1)


class TradeRadarDesktop(QMainWindow):
    def __init__(self, database: Path | None = None) -> None:
        super().__init__()
        self.database = database or PROJECT_ROOT / ".audit" / "kaitori.sqlite3"
        self.repo = Repository(self.database)
        self.service = JobService(self.repo)
        self.job_id: str | None = None
        self.running = False
        self.last_log_count = 0
        self.job_result_rows: list[dict[str, Any]] = []
        self._syncing_range = False
        self._build_window()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_collection)

    def _build_window(self) -> None:
        self.setWindowTitle("TCG Trade Radar · 실시간 수집")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(236)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        side.setSpacing(0)

        mark = QLabel("TCG")
        mark.setObjectName("brandMark")
        brand = QLabel("TRADE\nRADAR")
        brand.setObjectName("brandTitle")
        brand_subtitle = QLabel("LOCAL COLLECTION DESK")
        brand_subtitle.setObjectName("brandSubtitle")
        side.addWidget(mark, alignment=Qt.AlignmentFlag.AlignLeft)
        side.addSpacing(12)
        side.addWidget(brand)
        side.addSpacing(6)
        side.addWidget(brand_subtitle)
        side.addSpacing(38)

        section = QLabel("WORKFLOW")
        section.setObjectName("sideSection")
        side.addWidget(section)
        side.addSpacing(9)
        side.addWidget(WorkflowStep("01", "수집 설정", "게임 · 기간 · 글 수", active=True))
        side.addSpacing(6)
        side.addWidget(WorkflowStep("02", "실행 상태", "로그와 수집 진행률"))
        side.addSpacing(6)
        side.addWidget(WorkflowStep("03", "CSV 저장", "정리된 결과 내보내기"))
        side.addStretch(1)

        local_badge = QLabel("●  로컬 수집 엔진\n\n수집 데이터는 이 PC에\nSQLite로 먼저 저장됩니다.")
        local_badge.setObjectName("localBadge")
        local_badge.setWordWrap(True)
        side.addWidget(local_badge)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 28, 34, 28)
        content_layout.setSpacing(18)
        content_layout.addLayout(self._header())
        content_layout.addWidget(self._build_collection_page(), 1)
        outer.addWidget(content, 1)
        self.setStyleSheet(APP_QSS)

    def _header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        eyebrow = QLabel("DATA INGESTION")
        eyebrow.setObjectName("eyebrow")
        self.page_title = QLabel("실시간 수집")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("거래글을 직접 수집하고, 바로 CSV로 가져가세요.")
        self.page_subtitle.setObjectName("pageSubtitle")
        copy.addWidget(eyebrow)
        copy.addWidget(self.page_title)
        copy.addWidget(self.page_subtitle)
        layout.addLayout(copy)
        layout.addStretch(1)
        self.connection = QLabel("●  로컬 모드")
        self.connection.setObjectName("connectionBadge")
        layout.addWidget(self.connection, alignment=Qt.AlignmentFlag.AlignTop)
        return layout

    def _build_collection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        controls = QFrame()
        controls.setObjectName("controlCard")
        control_layout = QVBoxLayout(controls)
        control_layout.setContentsMargins(22, 20, 22, 20)
        control_layout.setSpacing(16)

        control_head = QHBoxLayout()
        head_copy = QVBoxLayout()
        head_copy.setSpacing(3)
        control_eyebrow = QLabel("COLLECTION CONTROL")
        control_eyebrow.setObjectName("eyebrow")
        control_title = QLabel("수집 범위를 정하세요")
        control_title.setObjectName("sectionTitle")
        control_description = QLabel("게임을 고르고 기간과 최근 글 수를 조절한 뒤 수집을 시작합니다.")
        control_description.setObjectName("sectionDescription")
        head_copy.addWidget(control_eyebrow)
        head_copy.addWidget(control_title)
        head_copy.addWidget(control_description)
        control_head.addLayout(head_copy)
        control_head.addStretch(1)
        self.collect_status = QLabel("준비됨")
        self.collect_status.setObjectName("readyPill")
        control_head.addWidget(self.collect_status, alignment=Qt.AlignmentFlag.AlignTop)
        control_layout.addLayout(control_head)

        fields = QHBoxLayout()
        fields.setSpacing(14)

        game_field = QVBoxLayout()
        game_field.setSpacing(7)
        game_field.addWidget(self._field_label("게임"))
        self.collect_game = QComboBox()
        self.collect_game.setObjectName("fieldControl")
        self.collect_game.addItems([item["name"] for item in PRESETS])
        game_field.addWidget(self.collect_game)
        fields.addLayout(game_field, 2)

        period_field = QVBoxLayout()
        period_field.setSpacing(7)
        period_field.addWidget(self._field_label("수집 기간"))
        range_chips = QHBoxLayout()
        range_chips.setSpacing(5)
        self.range_group = QButtonGroup(self)
        self.range_group.setExclusive(True)
        for label, days in (("오늘", 1), ("3일", 3), ("7일", 7), ("14일", 14), ("30일", 30), ("직접", None)):
            button = RangeButton(label, days)
            self.range_group.addButton(button)
            range_chips.addWidget(button)
            if days == 7:
                button.setChecked(True)
            if days is None:
                button.clicked.connect(self._focus_custom_dates)
            else:
                button.clicked.connect(lambda _checked=False, value=days: self._set_range_days(value))
        period_field.addLayout(range_chips)
        date_row = QHBoxLayout()
        date_row.setSpacing(6)
        self.collect_start = self._date_edit(QDate.currentDate().addDays(-6))
        self.collect_end = self._date_edit(QDate.currentDate())
        self.collect_start.dateChanged.connect(self._mark_custom_range)
        self.collect_end.dateChanged.connect(self._mark_custom_range)
        date_row.addWidget(self.collect_start)
        arrow = QLabel("→")
        arrow.setObjectName("dateArrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_row.addWidget(arrow)
        date_row.addWidget(self.collect_end)
        period_field.addLayout(date_row)
        fields.addLayout(period_field, 4)

        posts_field = QVBoxLayout()
        posts_field.setSpacing(7)
        posts_field.addWidget(self._field_label("최근 글 수"))
        posts_row = QHBoxLayout()
        posts_row.setSpacing(8)
        self.collect_posts_slider = QSlider(Qt.Orientation.Horizontal)
        self.collect_posts_slider.setObjectName("postsSlider")
        self.collect_posts_slider.setRange(10, 200)
        self.collect_posts_slider.setSingleStep(10)
        self.collect_posts_slider.setPageStep(20)
        self.collect_posts_slider.setValue(50)
        self.collect_posts = QSpinBox()
        self.collect_posts.setObjectName("postCount")
        self.collect_posts.setRange(10, 200)
        self.collect_posts.setSingleStep(10)
        self.collect_posts.setValue(50)
        self.collect_posts.setSuffix(" 개")
        self.collect_posts.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.collect_posts_slider.valueChanged.connect(self.collect_posts.setValue)
        self.collect_posts.valueChanged.connect(self.collect_posts_slider.setValue)
        posts_row.addWidget(self.collect_posts_slider, 1)
        posts_row.addWidget(self.collect_posts)
        posts_field.addLayout(posts_row)
        post_chips = QHBoxLayout()
        post_chips.setSpacing(5)
        for count in (30, 50, 100, 200):
            button = QPushButton(str(count))
            button.setObjectName("countChip")
            button.setCheckable(False)
            button.clicked.connect(lambda _checked=False, value=count: self.collect_posts.setValue(value))
            post_chips.addWidget(button)
        post_chips.addStretch(1)
        posts_field.addLayout(post_chips)
        fields.addLayout(posts_field, 4)

        action_field = QVBoxLayout()
        action_field.setSpacing(7)
        action_field.addWidget(self._field_label("실행"))
        self.collect_button = QPushButton("▶  수집 시작")
        self.collect_button.setObjectName("primaryButton")
        self.collect_button.setMinimumHeight(42)
        self.collect_button.clicked.connect(self._start_collection)
        action_field.addWidget(self.collect_button)
        action_field.addStretch(1)
        fields.addLayout(action_field, 2)
        control_layout.addLayout(fields)
        layout.addWidget(controls)

        status = QFrame()
        status.setObjectName("statusCard")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(18, 13, 18, 13)
        status_layout.setSpacing(9)
        status_head = QHBoxLayout()
        status_copy = QHBoxLayout()
        status_copy.setSpacing(8)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_title = QLabel("수집 대기 중")
        self.status_title.setObjectName("statusTitle")
        status_copy.addWidget(self.status_dot)
        status_copy.addWidget(self.status_title)
        self.log_count = QLabel("원문 0  ·  결과 0  ·  댓글 0")
        self.log_count.setObjectName("statusMeta")
        status_head.addLayout(status_copy)
        status_head.addStretch(1)
        status_head.addWidget(self.log_count)
        self.progress = QProgressBar()
        self.progress.setObjectName("progressBar")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        status_layout.addLayout(status_head)
        status_layout.addWidget(self.progress)
        layout.addWidget(status)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)
        log_panel = self._panel("실행 로그", "수집 단계와 오류를 확인합니다")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(16, 14, 16, 16)
        log_layout.setSpacing(9)
        log_head = QHBoxLayout()
        log_head.addWidget(self._panel_title("실행 로그"))
        log_head.addStretch(1)
        copy_log = QPushButton("로그 복사")
        copy_log.setObjectName("ghostButton")
        copy_log.clicked.connect(self._copy_logs)
        log_head.addWidget(copy_log)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        log_layout.addLayout(log_head)
        log_layout.addWidget(self.log_view, 1)
        workspace.addWidget(log_panel, 5)

        result_panel = self._panel("수집 결과", "정규화된 행을 CSV로 저장합니다")
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(16, 14, 16, 16)
        result_layout.setSpacing(9)
        result_head = QHBoxLayout()
        result_head.addWidget(self._panel_title("수집 결과"))
        result_head.addStretch(1)
        self.result_info = QLabel("수집을 시작하면 결과가 표시됩니다")
        self.result_info.setObjectName("tableHint")
        result_head.addWidget(self.result_info)
        self.export_button = QPushButton("CSV 저장")
        self.export_button.setObjectName("ghostButton")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_job_csv)
        result_head.addWidget(self.export_button)
        self.result_table = self._table(["카드", "구분", "가격", "수량", "판매자", "원문"], [185, 60, 90, 55, 110, 55])
        self.result_table.cellDoubleClicked.connect(self._open_selected_result)
        result_layout.addLayout(result_head)
        result_layout.addWidget(self.result_table, 1)
        workspace.addWidget(result_panel, 7)
        layout.addLayout(workspace, 1)
        return page

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _date_edit(self, value: QDate) -> QDateEdit:
        widget = QDateEdit(value)
        widget.setObjectName("dateControl")
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("yyyy.MM.dd")
        return widget

    def _panel(self, title: str, description: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setProperty("panelTitle", title)
        panel.setProperty("panelDescription", description)
        return panel

    def _panel_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("panelTitle")
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
        table.verticalHeader().setDefaultSectionSize(42)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        for index, width in enumerate(widths):
            header.resizeSection(index, width)
        return table

    def _set_table(self, table: QTableWidget, rows: list[tuple[str, ...]], accents: dict[int, str] | None = None) -> None:
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if accents and row_index in accents:
                    cell.setForeground(QColor(accents[row_index]))
                table.setItem(row_index, column_index, cell)

    def _set_range_days(self, days: int) -> None:
        self._syncing_range = True
        start, end = today_range(days)
        self.collect_start.setDate(QDate.fromString(start, "yyyy-MM-dd"))
        self.collect_end.setDate(QDate.fromString(end, "yyyy-MM-dd"))
        self._syncing_range = False

    def _focus_custom_dates(self) -> None:
        self.collect_start.setFocus()

    def _mark_custom_range(self) -> None:
        if self._syncing_range:
            return
        for button in self.range_group.buttons():
            button.setChecked(button.days is None)

    def _set_collection_state(self, title: str, pill: str, state: str) -> None:
        self.status_title.setText(title)
        self.collect_status.setText(pill)
        self.status_dot.setProperty("state", state)
        self.collect_status.setProperty("state", state)
        for widget in (self.status_dot, self.collect_status):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

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
        self.job_result_rows = []
        self.collect_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.collect_status.setEnabled(True)
        self._set_collection_state(f"{game['name']} 수집 중", "수집 중", "running")
        self.log_view.clear()
        self.result_table.setRowCount(0)
        self.result_info.setText("수집 중입니다…")
        self.progress.setRange(0, 0)
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
        self.log_count.setText(f"원문 {counts.get('sources', 0)}  ·  결과 {counts.get('rows', 0)}  ·  댓글 {counts.get('comments', 0)}")
        if job.get("state") not in {"completed", "failed"}:
            return
        self.poll_timer.stop()
        self.running = False
        self.collect_button.setEnabled(True)
        failed = job.get("state") == "failed"
        if failed:
            self._set_collection_state("수집에 문제가 있습니다", "오류", "error")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.log_view.appendPlainText(f"\n[ERROR] {job.get('error_message') or '알 수 없는 오류'}")
        else:
            self._set_collection_state("수집 완료 · CSV로 저장할 수 있습니다", "완료", "done")
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
        self._load_job_results()

    def _refresh_logs(self) -> None:
        if not self.job_id:
            return
        logs = self.repo.list_job_logs(self.job_id, limit=2000)
        for log in logs[self.last_log_count:]:
            detail = log.get("details") if isinstance(log.get("details"), dict) else {}
            compact = " · ".join(
                f"{key}={value}"
                for key, value in detail.items()
                if key in {"url", "rows", "inserted", "comments", "error", "risk_level", "risk_score"}
                and value not in (None, "")
            )
            tail = f" · {compact}" if compact else ""
            self.log_view.appendPlainText(f"[{str(log.get('created_at') or '')[-8:]}] {str(log.get('level') or 'info').upper():7} {log.get('message') or ''}{tail}")
        self.last_log_count = len(logs)

    def _load_job_results(self) -> None:
        if not self.job_id:
            return
        self.job_result_rows = self.service.get_results(self.job_id)
        self.result_info.setText(f"{len(self.job_result_rows):,}개 행")
        self.export_button.setEnabled(bool(self.job_result_rows))
        display = [
            (
                str(item.get("card_name") or item.get("card_name_raw") or "미확인"),
                TYPE_LABELS.get(str(item.get("listing_type") or "unknown"), "미분류"),
                money(item.get("price_krw")),
                str(item.get("quantity") or "-"),
                str(item.get("seller_name") or item.get("author_name") or "미상"),
                "열기",
            )
            for item in self.job_result_rows
        ]
        self._set_table(self.result_table, display)
        for index, item in enumerate(self.job_result_rows):
            self.result_table.item(index, 0).setData(Qt.ItemDataRole.UserRole, item.get("source_url") or item.get("post_url") or "")

    def _open_selected_result(self, row: int, _column: int) -> None:
        item = self.result_table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl(str(item.data(Qt.ItemDataRole.UserRole))))

    def _copy_logs(self) -> None:
        QGuiApplication.clipboard().setText(self.log_view.toPlainText())

    def _export_job_csv(self) -> None:
        if not self.job_result_rows:
            QMessageBox.information(self, "CSV 저장", "저장할 수집 결과가 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "수집 CSV 저장", f"tcg-trade-radar-{date.today():%Y%m%d}.csv", "CSV 파일 (*.csv)")
        if path:
            self._write_csv(Path(path), self.job_result_rows)

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
* { font-family: 'Malgun Gothic', 'Segoe UI Variable', 'Segoe UI', sans-serif; color: #e9eef8; }
QMainWindow, #appRoot { background: #0b1220; }
#sidebar { background: #10192b; border-right: 1px solid #21304a; }
#brandMark { color: #0b1220; background: #91a7ff; border-radius: 10px; font-size: 13px; font-weight: 900; padding: 9px 10px; max-width: 34px; }
#brandTitle { color: #f7f9ff; font-size: 22px; font-weight: 900; letter-spacing: 1.6px; line-height: 1.1; }
#brandSubtitle, #sideSection { color: #71809e; font-size: 10px; font-weight: 800; letter-spacing: 1.15px; }
#sideSection { color: #91a2c6; }
#workflowStep { background: transparent; border: 1px solid transparent; border-radius: 12px; }
#workflowStep[active="true"] { background: #1b2c51; border-color: #2c4d85; }
#workflowNumber { color: #6f83a9; background: #18243b; border-radius: 8px; padding: 6px 5px; font-size: 10px; font-weight: 900; }
#workflowStep[active="true"] #workflowNumber { color: #dce5ff; background: #5d78db; }
#workflowTitle { color: #dce5f7; font-size: 12px; font-weight: 750; }
#workflowDescription { color: #7e8eae; font-size: 10px; }
#localBadge { color: #a2e8ca; background: #123a38; border: 1px solid #205e56; border-radius: 12px; padding: 13px; font-size: 10px; line-height: 1.45; }
#eyebrow { color: #8ca4ff; font-size: 10px; font-weight: 850; letter-spacing: 1.1px; }
#pageTitle { color: #f8faff; font-size: 29px; font-weight: 850; }
#pageSubtitle { color: #8999b8; font-size: 12px; }
#connectionBadge, #readyPill { color: #9deac9; background: #143c39; border: 1px solid #256259; border-radius: 15px; padding: 8px 11px; font-size: 11px; font-weight: 750; }
#readyPill[state="running"] { color: #d6e0ff; background: #263a75; border-color: #4765bb; }
#readyPill[state="done"] { color: #a2f0ce; background: #144e43; border-color: #2b806d; }
#readyPill[state="error"] { color: #ffc0b0; background: #4a2528; border-color: #9e4845; }
#controlCard { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243e, stop:1 #18213a); border: 1px solid #2e426c; border-radius: 17px; }
#sectionTitle { color: #f6f8ff; font-size: 18px; font-weight: 820; }
#sectionDescription { color: #93a2c1; font-size: 11px; }
#fieldLabel { color: #9eafd0; font-size: 11px; font-weight: 760; }
#fieldControl, #dateControl, #postCount { background: #0e1729; color: #eff3fd; border: 1px solid #334769; border-radius: 9px; padding: 8px 10px; font-size: 12px; min-height: 20px; }
#fieldControl:focus, #dateControl:focus, #postCount:focus { border-color: #7894ff; }
#fieldControl QAbstractItemView { background: #16213a; border: 1px solid #3b507d; selection-background-color: #33539b; }
#dateControl { padding-right: 4px; }
#dateControl::drop-down { border: 0; width: 25px; }
#postCount { min-width: 76px; }
#dateArrow { color: #6d7fa5; font-size: 16px; }
#rangeChip, #countChip { color: #9aabca; background: #111c31; border: 1px solid #2c3c5d; border-radius: 7px; padding: 6px 8px; font-size: 10px; font-weight: 750; }
#rangeChip:hover, #countChip:hover { color: #eaf0ff; border-color: #6e89ef; background: #1b2b50; }
#rangeChip:checked { color: #ffffff; background: #526fda; border-color: #7893ff; }
#postsSlider::groove:horizontal { height: 5px; background: #2d3d5c; border-radius: 2px; }
#postsSlider::handle:horizontal { width: 17px; margin: -6px 0; border-radius: 9px; background: #91a7ff; border: 2px solid #d6deff; }
#postsSlider::sub-page:horizontal { background: #647ff0; border-radius: 2px; }
#primaryButton { color: #ffffff; background: #627ef0; border: 1px solid #8ea2ff; border-radius: 9px; padding: 10px 16px; font-size: 12px; font-weight: 820; }
#primaryButton:hover { background: #7892ff; }
#primaryButton:disabled { color: #8390ab; background: #253451; border-color: #334361; }
#ghostButton { color: #cbd7ef; background: #18253f; border: 1px solid #344b73; border-radius: 8px; padding: 7px 11px; font-size: 11px; font-weight: 720; }
#ghostButton:hover { color: #ffffff; border-color: #7894ff; }
#ghostButton:disabled { color: #687897; background: #121d31; border-color: #263653; }
#statusCard { background: #111b2e; border: 1px solid #263959; border-radius: 12px; }
#statusDot { color: #7483a3; font-size: 15px; }
#statusDot[state="running"] { color: #91a7ff; }
#statusDot[state="done"] { color: #6fe0b4; }
#statusDot[state="error"] { color: #ff8279; }
#statusTitle { color: #e9effc; font-size: 12px; font-weight: 760; }
#statusMeta, #tableHint { color: #8495b5; font-size: 11px; }
#progressBar { background: #202f4a; border: 0; border-radius: 3px; max-height: 5px; }
#progressBar::chunk { background: #738dff; border-radius: 3px; }
#panel { background: #111b2e; border: 1px solid #263959; border-radius: 14px; }
#panelTitle { color: #f0f4ff; font-size: 14px; font-weight: 800; }
#logView { background: #09111f; border: 1px solid #243653; border-radius: 9px; color: #b9c9e8; font-family: 'Cascadia Mono', Consolas, monospace; font-size: 10px; padding: 9px; selection-background-color: #3857a1; }
#dataTable { background: #10192b; alternate-background-color: #14213a; border: 1px solid #253858; border-radius: 9px; gridline-color: #233452; color: #dce6f8; font-size: 11px; }
#dataTable::item { padding: 7px 8px; border-bottom: 1px solid #1e2d49; }
#dataTable::item:selected { background: #2d4c91; color: #ffffff; }
QHeaderView::section { background: #182640; color: #96a9ce; border: 0; border-bottom: 1px solid #31466c; padding: 9px 8px; font-size: 10px; font-weight: 800; }
QScrollBar:vertical { background: #10192b; width: 10px; margin: 3px; }
QScrollBar::handle:vertical { background: #3b4e76; border-radius: 5px; min-height: 26px; }
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
