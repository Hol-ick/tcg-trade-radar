"""TCG Trade Radar desktop explorer.

The first screen is a market view. Collection remains available in its own tab
and runs in-process, so there is no separate worker to start.
"""
from __future__ import annotations

import math
import csv
import sys
import threading
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


PRESETS = [
    {"name": "유희왕", "id": "tcggame", "subject": "판매", "subjects": ("판매", "구매", "거래", "🔁거래")},
    {"name": "원피스 카드게임", "id": "onepiececardgame", "subject": "판매", "subjects": ("판매", "구매", "거래", "🔁거래")},
    {"name": "포켓몬 카드게임", "id": "pokemoncardgame", "subject": "🔁거래", "subjects": ("판매", "구매", "거래", "🔁거래")},
    {"name": "디지몬 카드게임", "id": "digimontcg", "subject": "거래", "subjects": ("판매", "구매", "거래", "🔁거래")},
    {"name": "뱅가드", "id": "vg", "subject": "거래", "subjects": ("판매", "구매", "거래", "🔁거래")},
]


def period(days: int) -> tuple[str, str]:
    until = date.today()
    return (until - timedelta(days=max(1, days) - 1)).isoformat(), until.isoformat()


def money(value: Any) -> str:
    return f"{int(value):,}원" if value not in (None, "") else "-"


def game_name(game_id: str) -> str:
    return next((item["name"] for item in PRESETS if item["id"] == game_id), game_id or "전체")


class TradeRadarApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TCG Trade Radar")
        self.root.geometry("1280x820")
        self.root.minsize(1020, 680)
        self.db_path = PROJECT_ROOT / ".audit" / "kaitori.sqlite3"
        self.repo = Repository(self.db_path)
        self.service = JobService(self.repo)
        self.job_id: str | None = None
        self.job_thread: threading.Thread | None = None
        self.running = False
        self.last_log_count = 0

        self._style()
        self._build()
        self._refresh_cards()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("AppTitle.TLabel", font=("Segoe UI", 22, "bold"), foreground="#16202a")
        style.configure("Subtle.TLabel", foreground="#667789")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Metric.TLabel", font=("Segoe UI", 16, "bold"), foreground="#16202a")

    def _build(self) -> None:
        shell = ttk.Frame(self.root, padding=24)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="TCG TRADE RADAR", style="AppTitle.TLabel").pack(side="left")
        ttk.Label(header, text="공개 유저 거래 신호 탐색기", style="Subtle.TLabel").pack(side="left", padx=(14, 0), pady=(8, 0))
        self.header_state = ttk.Label(header, text="수집 데이터 기준", style="Subtle.TLabel")
        self.header_state.pack(side="right", pady=(8, 0))

        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True)
        self.explorer_tab = ttk.Frame(self.tabs, padding=16)
        self.collect_tab = ttk.Frame(self.tabs, padding=16)
        self.inventory_tab = ttk.Frame(self.tabs, padding=16)
        self.trend_tab = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.explorer_tab, text="매물 탐색")
        self.tabs.add(self.collect_tab, text="수집·로그")
        self.tabs.add(self.inventory_tab, text="보유 카드 수요")
        self.tabs.add(self.trend_tab, text="거래 동향")
        self._build_explorer()
        self._build_collection()
        self._build_inventory()
        self._build_trend()

    def _build_explorer(self) -> None:
        filters = ttk.LabelFrame(self.explorer_tab, text="검색", padding=12)
        filters.pack(fill="x")
        self.search_text = tk.StringVar()
        self.search_game = tk.StringVar(value="전체")
        self.search_type = tk.StringVar(value="전체")
        self.search_days = tk.StringVar(value="7")
        self.search_sort = tk.StringVar(value="수요순")
        ttk.Label(filters, text="카드명 / 코드").grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Entry(filters, textvariable=self.search_text, width=24).grid(row=0, column=1, padx=(0, 14))
        ttk.Label(filters, text="게임").grid(row=0, column=2, padx=(0, 6))
        ttk.Combobox(filters, textvariable=self.search_game, values=["전체"] + [item["name"] for item in PRESETS], state="readonly", width=17).grid(row=0, column=3, padx=(0, 14))
        ttk.Label(filters, text="유형").grid(row=0, column=4, padx=(0, 6))
        ttk.Combobox(filters, textvariable=self.search_type, values=["전체", "판매", "구매", "교환", "미확인"], state="readonly", width=9).grid(row=0, column=5, padx=(0, 14))
        ttk.Label(filters, text="최근").grid(row=0, column=6, padx=(0, 6))
        ttk.Spinbox(filters, from_=1, to=365, textvariable=self.search_days, width=5).grid(row=0, column=7, padx=(0, 4))
        ttk.Label(filters, text="일").grid(row=0, column=8, padx=(0, 14))
        ttk.Combobox(filters, textvariable=self.search_sort, values=["수요순", "최근순", "가격 낮은순", "가격 높은순"], state="readonly", width=12).grid(row=0, column=9, padx=(0, 12))
        ttk.Button(filters, text="검색", style="Primary.TButton", command=self._refresh_cards).grid(row=0, column=10)
        ttk.Button(filters, text="CSV 저장", command=self._export_cards).grid(row=0, column=11, padx=(8, 0))

        metric = ttk.Frame(self.explorer_tab)
        metric.pack(fill="x", pady=(14, 10))
        self.card_metric = self._metric(metric, "카드")
        self.demand_metric = self._metric(metric, "수요 있음")
        self.supply_metric = self._metric(metric, "판매 매물")

        table = ttk.LabelFrame(self.explorer_tab, text="카드별 요약", padding=0)
        table.pack(fill="both", expand=True)
        columns = ("card", "game", "sell", "buy", "median", "range", "status", "evidence", "latest")
        self.card_tree = ttk.Treeview(table, columns=columns, show="headings")
        headings = {"card": "카드", "game": "게임", "sell": "판매", "buy": "구매", "median": "판매 중앙값", "range": "판매가 범위", "status": "상태", "evidence": "근거", "latest": "최근 등록"}
        widths = {"card": 210, "game": 130, "sell": 65, "buy": 65, "median": 105, "range": 150, "status": 100, "evidence": 210, "latest": 150}
        for column in columns:
            self.card_tree.heading(column, text=headings[column])
            self.card_tree.column(column, width=widths[column], anchor="w" if column in {"card", "game", "range", "status", "evidence", "latest"} else "center")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.card_tree.yview)
        self.card_tree.configure(yscrollcommand=scroll.set)
        self.card_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.card_tree.bind("<Double-1>", self._show_card_detail)
        ttk.Label(self.explorer_tab, text="카드를 더블클릭하면 판매 매물과 구매 수요 원문을 함께 봅니다.", style="Subtle.TLabel").pack(anchor="e", pady=(8, 0))

    def _build_collection(self) -> None:
        controls = ttk.LabelFrame(self.collect_tab, text="수집 설정", padding=12)
        controls.pack(fill="x")
        self.collect_game = tk.StringVar(value=PRESETS[0]["name"])
        self.collect_count = tk.StringVar(value="50")
        ttk.Label(controls, text="게임").grid(row=0, column=0, padx=(0, 6))
        ttk.Combobox(controls, textvariable=self.collect_game, values=[item["name"] for item in PRESETS], state="readonly", width=18).grid(row=0, column=1, padx=(0, 14))
        ttk.Label(controls, text="최근 글 수").grid(row=0, column=2, padx=(0, 6))
        ttk.Spinbox(controls, from_=1, to=200, textvariable=self.collect_count, width=7).grid(row=0, column=3, padx=(0, 14))
        self.collect_button = ttk.Button(controls, text="수집 시작", style="Primary.TButton", command=self._start_collection)
        self.collect_button.grid(row=0, column=4, padx=(0, 14))
        self.collect_state = ttk.Label(controls, text="대기 중", style="Subtle.TLabel")
        self.collect_state.grid(row=0, column=5, sticky="w")
        self.collect_metric = ttk.Label(controls, text="", style="Subtle.TLabel")
        self.collect_metric.grid(row=0, column=6, padx=(14, 0), sticky="w")

        log_head = ttk.Frame(self.collect_tab)
        log_head.pack(fill="x", pady=(14, 6))
        ttk.Label(log_head, text="수집 로그", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.copy_log_button = ttk.Button(log_head, text="전체 복사", command=self._copy_logs)
        self.copy_log_button.pack(side="right")
        self.log_text = tk.Text(self.collect_tab, height=18, bg="#111c27", fg="#d8e2ec", insertbackground="#fff", relief="flat", padx=10, pady=8, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("warning", foreground="#ffd166")
        self.log_text.tag_configure("error", foreground="#ff8d87")
        self.log_text.configure(state="disabled")
        ttk.Label(self.collect_tab, text="수집 후 매물 탐색 탭에서 카드별 판매·구매 수요를 확인할 수 있습니다.", style="Subtle.TLabel").pack(anchor="e", pady=(8, 0))

    def _build_inventory(self) -> None:
        ttk.Label(self.inventory_tab, text="보유 카드 이름을 한 줄에 하나씩 입력하세요.", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(self.inventory_tab, text="구매글이 있는 카드만 골라서 수요 근거를 보여줍니다.", style="Subtle.TLabel").pack(anchor="w", pady=(4, 10))
        top = ttk.Frame(self.inventory_tab)
        top.pack(fill="x")
        self.inventory_text = tk.Text(top, height=6, width=42, relief="solid", borderwidth=1)
        self.inventory_text.pack(side="left")
        right = ttk.Frame(top, padding=(14, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        self.inventory_game = tk.StringVar(value="전체")
        ttk.Label(right, text="게임").pack(anchor="w")
        ttk.Combobox(right, textvariable=self.inventory_game, values=["전체"] + [item["name"] for item in PRESETS], state="readonly", width=18).pack(anchor="w", pady=(4, 10))
        ttk.Button(right, text="수요 찾기", style="Primary.TButton", command=self._refresh_inventory).pack(anchor="w")
        table = ttk.LabelFrame(self.inventory_tab, text="구매 수요가 확인된 보유 카드", padding=0)
        table.pack(fill="both", expand=True, pady=(14, 0))
        columns = ("card", "buy", "sell", "wanted", "score", "status", "evidence")
        self.inventory_tree = ttk.Treeview(table, columns=columns, show="headings")
        headings = {"card": "카드", "buy": "구매글", "sell": "판매 매물", "wanted": "희망가 중앙값", "score": "수요 점수", "status": "상태", "evidence": "근거"}
        for column in columns:
            self.inventory_tree.heading(column, text=headings[column])
            self.inventory_tree.column(column, width=150 if column in {"card", "evidence"} else 100, anchor="w" if column in {"card", "status", "evidence"} else "center")
        self.inventory_tree.pack(fill="both", expand=True)

    def _build_trend(self) -> None:
        top = ttk.Frame(self.trend_tab)
        top.pack(fill="x")
        self.trend_game = tk.StringVar(value=PRESETS[0]["name"])
        self.trend_days = tk.StringVar(value="30")
        ttk.Label(top, text="게임").pack(side="left")
        ttk.Combobox(top, textvariable=self.trend_game, values=[item["name"] for item in PRESETS], state="readonly", width=18).pack(side="left", padx=(6, 14))
        ttk.Label(top, text="기간").pack(side="left")
        ttk.Spinbox(top, from_=1, to=365, textvariable=self.trend_days, width=6).pack(side="left", padx=(6, 4))
        ttk.Label(top, text="일").pack(side="left")
        ttk.Button(top, text="현재 데이터로 스냅샷 생성", command=self._create_snapshot).pack(side="right")
        ttk.Button(top, text="새로고침", command=self._refresh_trends).pack(side="right", padx=(0, 8))
        self.trend_state = ttk.Label(self.trend_tab, text="수집 완료 후 일별 스냅샷이 쌓입니다.", style="Subtle.TLabel")
        self.trend_state.pack(anchor="w", pady=(10, 8))
        table = ttk.LabelFrame(self.trend_tab, text="카드별 동향 스냅샷", padding=0)
        table.pack(fill="both", expand=True)
        columns = ("date", "card", "sell", "buy", "median", "wanted", "score")
        self.trend_tree = ttk.Treeview(table, columns=columns, show="headings")
        headings = {"date": "기준일", "card": "카드", "sell": "판매", "buy": "구매", "median": "판매 중앙값", "wanted": "희망가 중앙값", "score": "수요 점수"}
        for column in columns:
            self.trend_tree.heading(column, text=headings[column])
            self.trend_tree.column(column, width=150 if column == "card" else 105, anchor="w" if column in {"date", "card"} else "center")
        self.trend_tree.pack(fill="both", expand=True)

    def _metric(self, parent: ttk.Frame, label: str) -> tk.StringVar:
        box = ttk.Frame(parent, relief="groove", padding=10)
        box.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(box, text=label, style="Subtle.TLabel").pack(anchor="w")
        value = tk.StringVar(value="0")
        ttk.Label(box, textvariable=value, style="Metric.TLabel").pack(anchor="w", pady=(3, 0))
        return value

    def _selected_game_id(self, value: str) -> str:
        return next((item["id"] for item in PRESETS if item["name"] == value), "")

    def _market_filters(self) -> dict[str, Any]:
        try:
            days = max(1, int(self.search_days.get()))
        except ValueError:
            days = 7
        since, until = period(days)
        type_map = {"전체": "", "판매": "sell", "구매": "buy", "교환": "trade", "미확인": "unknown"}
        sort_map = {"수요순": "demand", "최근순": "recent", "가격 낮은순": "price_asc", "가격 높은순": "price_desc"}
        return {
            "query_text": self.search_text.get().strip(),
            "game_id": self._selected_game_id(self.search_game.get()),
            "listing_type": type_map.get(self.search_type.get(), ""),
            "since": since,
            "until": until,
            "sort": sort_map.get(self.search_sort.get(), "demand"),
            "limit": 500,
        }

    def _refresh_cards(self) -> None:
        filters = self._market_filters()
        summaries = self.repo.summarize_cards(**filters)
        self.card_tree.delete(*self.card_tree.get_children())
        for index, item in enumerate(summaries):
            self.card_tree.insert("", "end", iid=f"card-{index}", values=(
                item["card_name_raw"], game_name(item["gallery_id"]), item["sell_count"], item["buy_count"], money(item["sell_price_median"]),
                f"{money(item['sell_price_min'])} ~ {money(item['sell_price_max'])}", _status_label(item["demand_status"]), item["evidence"], item["latest_posted_at"],
            ), tags=(item["card_key"], item["gallery_id"]))
        self.card_metric.set(str(len(summaries)))
        self.demand_metric.set(str(sum(1 for item in summaries if item["buy_count"] > 0)))
        self.supply_metric.set(str(sum(item["sell_count"] for item in summaries)))
        self.header_state.configure(text=f"카드 {len(summaries)}개 · 최근 {self.search_days.get()}일")

    def _show_card_detail(self, _event: tk.Event) -> None:
        selected = self.card_tree.selection()
        if not selected:
            return
        item = self.card_tree.item(selected[0])
        tags = item.get("tags", [])
        if not tags:
            return
        card_key, game_id = tags[0], tags[1]
        rows = self.repo.list_market_listings(query_text=card_key, game_id=game_id, since=self._market_filters()["since"], until=self._market_filters()["until"], limit=500)
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{item['values'][0]} · 매물과 수요")
        dialog.geometry("1050x520")
        ttk.Label(dialog, text=f"{item['values'][0]} · {game_name(game_id)}", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=16, pady=14)
        tree = ttk.Treeview(dialog, columns=("type", "price", "quantity", "confidence", "date", "title", "url"), show="headings")
        labels = {"type": "유형", "price": "가격", "quantity": "수량", "confidence": "신뢰도", "date": "등록", "title": "원문 제목", "url": "원문"}
        for col in tree["columns"]:
            tree.heading(col, text=labels[col])
            tree.column(col, width=100 if col != "title" else 270, anchor="w" if col in {"title", "url"} else "center")
        tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for row in rows:
            tree.insert("", "end", values=(_type_label(row.get("listing_type")), money(row.get("price_krw")), row.get("quantity", 1), f"{float(row.get('intent_confidence') or 0):.0%}", row.get("posted_at", ""), row.get("post_title", ""), row.get("post_url", "")))

    def _export_cards(self) -> None:
        filters = self._market_filters()
        summaries = self.repo.summarize_cards(**filters)
        if not summaries:
            return
        target = filedialog.asksaveasfilename(
            title="매물 요약 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv")],
            initialfile=f"tcg-trade-radar-{date.today():%Y%m%d}.csv",
        )
        if not target:
            return
        with open(target, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["카드", "게임", "판매 매물 수", "구매글 수", "판매 중앙값", "희망가 중앙값", "수요 상태", "수요 점수", "근거"])
            for item in summaries:
                writer.writerow([item["card_name_raw"], game_name(item["gallery_id"]), item["sell_count"], item["buy_count"], item["sell_price_median"], item["wanted_price_median"], _status_label(item["demand_status"]), item["demand_score"], item["evidence"]])

    def _refresh_inventory(self) -> None:
        names = [line.strip() for line in self.inventory_text.get("1.0", "end").splitlines() if line.strip()]
        game_id = self._selected_game_id(self.inventory_game.get())
        self.inventory_tree.delete(*self.inventory_tree.get_children())
        matched = []
        for name in names:
            cards = self.repo.summarize_cards(query_text=name, game_id=game_id, since=period(30)[0], until=period(30)[1], limit=20)
            matched.extend(item for item in cards if item["buy_count"] > 0)
        for item in matched:
            self.inventory_tree.insert("", "end", values=(item["card_name_raw"], item["buy_count"], item["sell_count"], money(item["wanted_price_median"]), item["demand_score"], _status_label(item["demand_status"]), item["evidence"]))

    def _refresh_trends(self) -> None:
        game_id = self._selected_game_id(self.trend_game.get())
        snapshots = self.repo.list_demand_snapshots(game_id=game_id, limit=500)
        self.trend_tree.delete(*self.trend_tree.get_children())
        for item in snapshots:
            self.trend_tree.insert("", "end", values=(item["snapshot_date"], item["card_name_raw"], item["sell_count"], item["buy_count"], money(item["sell_price_median"]), money(item["wanted_price_median"]), item["demand_score"]))
        self.trend_state.configure(text=f"{game_name(game_id)} · 스냅샷 {len(snapshots)}개")

    def _create_snapshot(self) -> None:
        game_id = self._selected_game_id(self.trend_game.get())
        try:
            days = max(1, int(self.trend_days.get()))
        except ValueError:
            days = 30
        since, until = period(days)
        count = self.repo.refresh_demand_snapshot(date.today().isoformat(), game_id, since=since, until=until)
        self.trend_state.configure(text=f"{game_name(game_id)} · 오늘 스냅샷 {count}개 생성")
        self._refresh_trends()

    def _start_collection(self) -> None:
        if self.running:
            return
        game = next(item for item in PRESETS if item["name"] == self.collect_game.get())
        try:
            max_posts = max(1, min(200, int(self.collect_count.get())))
        except ValueError:
            self.collect_state.configure(text="글 수를 확인하세요")
            return
        since, until = period(7)
        request = JobRequest(gallery_id=game["id"], gallery_url=f"https://gall.dcinside.com/mgallery/board/lists?id={game['id']}", subject=game["subject"], subjects=game["subjects"], since=since, until=until, max_posts=max_posts, max_pages=max(1, math.ceil(max_posts / 50)), delay=1.0, buy_rate=60, keep_raw=True, review_unmatched=True)
        self._clear_logs()
        self.job_id = self.service.create_job(request, start=False)
        self.running = True
        self.last_log_count = 0
        self.collect_state.configure(text=f"{game['name']} 수집 중")
        self.collect_button.configure(state="disabled")
        self.job_thread = threading.Thread(target=self.service.run_job, args=(self.job_id,), daemon=True)
        self.job_thread.start()
        self.root.after(300, self._poll_collection)

    def _poll_collection(self) -> None:
        if not self.job_id:
            return
        job = self.repo.get_job(self.job_id)
        if job:
            self._refresh_logs()
            counts = job["counts"]
            self.collect_metric.configure(text=f"글 {counts.get('sources', 0)} · 행 {counts.get('rows', 0)} · 구매 {counts.get('buy', 0)}")
            if job["state"] in {"completed", "failed"}:
                self.running = False
                self.collect_button.configure(state="normal")
                self.collect_state.configure(text="수집 완료" if job["state"] == "completed" else "수집 실패")
                self._refresh_cards()
                self._refresh_trends()
                return
        self.root.after(500, self._poll_collection)

    def _refresh_logs(self) -> None:
        if not self.job_id:
            return
        logs = self.repo.list_job_logs(self.job_id, limit=2000)
        for log in logs[self.last_log_count:]:
            details = log.get("details") if isinstance(log.get("details"), dict) else {}
            suffix = " · " + " · ".join(f"{key}={value}" for key, value in details.items() if value not in (None, ""))
            self._append_log(f"[{log['created_at'][-8:]}] {log['level'].upper():7} {log['message']}{suffix}", log["level"])
        self.last_log_count = len(logs)

    def _append_log(self, message: str, level: str = "info") -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n", level if level in {"warning", "error"} else "")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_logs(self) -> None:
        value = self.log_text.get("1.0", "end-1c")
        if value:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.copy_log_button.configure(text="복사됨")
            self.root.after(1200, lambda: self.copy_log_button.configure(text="전체 복사"))

    def _close(self) -> None:
        if self.running:
            return
        self.repo.close()
        self.root.destroy()


def _type_label(value: str) -> str:
    return {"sell": "판매", "buy": "구매", "trade": "교환", "unknown": "미확인"}.get(value or "unknown", "미확인")


def _status_label(value: str) -> str:
    return {"hot_demand": "구매 수요 있음", "balanced": "균형", "supply_heavy": "매물 우세", "stale_demand": "오래된 수요", "unknown": "확인 필요"}.get(value, "확인 필요")


def main() -> None:
    root = tk.Tk()
    TradeRadarApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
