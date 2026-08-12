"""Single-process desktop UI for the Kaitori collector.

Run from the project root with:
    python debug/kaitori_app.py

The crawler runs in a background thread inside this process. No HTTP worker
server or separate browser connection is required.
"""
from __future__ import annotations

import csv
import math
import sys
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kaitori_collector.contracts import JobRequest
from kaitori_collector.service import JobService
from kaitori_collector.storage import Repository


PRESETS = [
    {"name": "유희왕", "id": "tcggame", "subject": "판매", "url": "https://gall.dcinside.com/mgallery/board/lists?id=tcggame"},
    {"name": "원피스 카드게임", "id": "onepiececardgame", "subject": "판매", "url": "https://gall.dcinside.com/mgallery/board/lists?id=onepiececardgame"},
    {"name": "포켓몬 카드게임", "id": "pokemoncardgame", "subject": "🔁거래", "url": "https://gall.dcinside.com/mgallery/board/lists?id=pokemoncardgame"},
    {"name": "디지몬 카드게임", "id": "digimontcg", "subject": "거래", "url": "https://gall.dcinside.com/mgallery/board/lists?id=digimontcg"},
    {"name": "뱅가드", "id": "vg", "subject": "거래", "url": "https://gall.dcinside.com/mgallery/board/lists?id=vg"},
]

COLLECTION_DAYS = 7
MAX_POSTS_PER_GAME = 200
MAX_PAGES_PER_GAME = 20


def collection_period() -> tuple[str, str]:
    until = date.today()
    since = until - timedelta(days=COLLECTION_DAYS - 1)
    return since.isoformat(), until.isoformat()


def money(value: Any) -> str:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,}원" if amount > 0 else "-"


def shipping_label(value: Any) -> str:
    return {"included": "포함", "separate": "별도", "unknown": "미확인"}.get(str(value), "미확인")


def status_label(value: Any) -> str:
    return {
        "parsed": "검토 대기",
        "needs_review": "검토 대기",
        "approved": "승인",
        "rejected": "반려",
        "exported": "내보냄",
    }.get(str(value), str(value or "확인 필요"))


class KaitoriApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Kaitori Collector")
        self.root.geometry("1180x760")
        self.root.minsize(900, 620)

        self.db_path = PROJECT_ROOT / ".audit" / "kaitori.sqlite3"
        self.service_repo = Repository(self.db_path)
        self.reader_repo = Repository(self.db_path)
        self.worker_service = JobService(self.service_repo)
        self.reader_service = JobService(self.reader_repo)

        self.selected_index = 0
        self.job_id: str | None = None
        self.job_thread: threading.Thread | None = None
        self.running = False
        self.last_log_count = 0
        self.logs: list[dict[str, Any]] = []

        self._configure_style()
        self._build_ui()
        self._select_game(0)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"), foreground="#17212b")
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground="#344252")
        style.configure("Muted.TLabel", font=("Segoe UI", 9), foreground="#718096")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Game.TButton", font=("Segoe UI", 10), padding=(12, 12))
        style.configure("Selected.Game.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 12))

    def _build_ui(self) -> None:
        self.root.configure(bg="#f3f5f7")
        shell = ttk.Frame(self.root, padding=22)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text="KAITORI", font=("Segoe UI", 12, "bold"), foreground="#17212b").pack(side="left")
        self.connection_label = ttk.Label(header, text="같은 프로그램에서 실행", style="Muted.TLabel")
        self.connection_label.pack(side="right")

        top = ttk.Frame(shell)
        top.pack(fill="both", expand=False)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=2)

        control = ttk.LabelFrame(top, text="수집", padding=16)
        control.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(control, text="게임", style="Section.TLabel").pack(anchor="w", pady=(0, 9))
        self.game_buttons: list[ttk.Button] = []
        for index, game in enumerate(PRESETS):
            button = ttk.Button(control, text=game["name"], style="Game.TButton", command=lambda i=index: self._select_game(i))
            button.pack(fill="x", pady=3)
            self.game_buttons.append(button)

        count_row = ttk.Frame(control)
        count_row.pack(fill="x", pady=(15, 0))
        ttk.Label(count_row, text="최근 글 수", style="Section.TLabel").pack(side="left")
        self.post_limit = tk.Spinbox(count_row, from_=1, to=200, width=7, justify="right", font=("Segoe UI", 10))
        self.post_limit.delete(0, "end")
        self.post_limit.insert(0, "20")
        self.post_limit.pack(side="right")
        self.start_button = ttk.Button(control, text="수집 시작", style="Primary.TButton", command=self._start_collection)
        self.start_button.pack(fill="x", pady=(15, 0))

        monitor = ttk.LabelFrame(top, text="실행", padding=16)
        monitor.grid(row=0, column=1, sticky="nsew")
        state_row = ttk.Frame(monitor)
        state_row.pack(fill="x")
        self.state_label = ttk.Label(state_row, text="대기 중", style="Section.TLabel")
        self.state_label.pack(side="left")
        self.job_label = ttk.Label(state_row, text="-", style="Muted.TLabel")
        self.job_label.pack(side="right")
        self.target_label = ttk.Label(monitor, text="유희왕 · tcggame", font=("Segoe UI", 16, "bold"), foreground="#17212b")
        self.target_label.pack(anchor="w", pady=(14, 12))

        metric_row = ttk.Frame(monitor)
        metric_row.pack(fill="x")
        self.source_value = self._metric(metric_row, "읽은 글")
        self.row_value = self._metric(metric_row, "결과")
        self.review_value = self._metric(metric_row, "검토 대기")

        log_head = ttk.Frame(monitor)
        log_head.pack(fill="x", pady=(15, 6))
        ttk.Label(log_head, text="로그", style="Section.TLabel").pack(side="left")
        self.copy_button = ttk.Button(log_head, text="전체 복사", command=self._copy_logs)
        self.copy_button.pack(side="right")
        self.log_text = tk.Text(monitor, height=10, wrap="none", bg="#111c27", fg="#d8e2ec", insertbackground="#fff", relief="flat", padx=10, pady=8, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("warning", foreground="#ffd166")
        self.log_text.tag_configure("error", foreground="#ff8d87")
        self.log_text.configure(state="disabled")

        action_row = ttk.Frame(monitor)
        action_row.pack(fill="x", pady=(10, 0))
        self.reset_button = ttk.Button(action_row, text="새 수집", command=self._reset, state="disabled")
        self.reset_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.export_button = ttk.Button(action_row, text="승인 결과 CSV", command=self._export_csv, state="disabled")
        self.export_button.pack(side="left", fill="x", expand=True, padx=(5, 0))

        results = ttk.LabelFrame(shell, text="결과", padding=0)
        results.pack(fill="both", expand=True, pady=(15, 0))
        columns = ("card", "price", "buy", "quantity", "shipping", "status", "url")
        self.tree = ttk.Treeview(results, columns=columns, show="headings", selectmode="browse")
        headings = {"card": "카드 / 원문", "price": "판매가", "buy": "매입가", "quantity": "수량", "shipping": "배송", "status": "상태", "url": "원문"}
        widths = {"card": 270, "price": 100, "buy": 100, "quantity": 60, "shipping": 70, "status": 90, "url": 75}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w" if column in {"card", "url"} else "center")
        scroll = ttk.Scrollbar(results, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected_url)

        review_row = ttk.Frame(shell)
        review_row.pack(fill="x", pady=(9, 0))
        self.approve_button = ttk.Button(review_row, text="선택 승인", command=lambda: self._review_selected("approve"), state="disabled")
        self.approve_button.pack(side="left")
        self.reject_button = ttk.Button(review_row, text="선택 반려", command=lambda: self._review_selected("reject"), state="disabled")
        self.reject_button.pack(side="left", padx=(6, 0))
        ttk.Label(review_row, text="행을 더블클릭하면 원문을 엽니다.", style="Muted.TLabel").pack(side="right")

    def _metric(self, parent: ttk.Frame, label: str) -> tk.StringVar:
        box = ttk.Frame(parent, relief="groove", padding=9)
        box.pack(side="left", fill="x", expand=True, padx=3)
        ttk.Label(box, text=label, style="Muted.TLabel").pack(anchor="w")
        value = tk.StringVar(value="0")
        ttk.Label(box, textvariable=value, font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(2, 0))
        return value

    def _select_game(self, index: int) -> None:
        if self.running:
            return
        self.selected_index = index
        game = PRESETS[index]
        self.target_label.configure(text=f"{game['name']} · {game['id']}")
        for button_index, button in enumerate(self.game_buttons):
            button.configure(style="Selected.Game.TButton" if button_index == index else "Game.TButton")

    def _set_state(self, text: str) -> None:
        self.state_label.configure(text=text)

    def _start_collection(self) -> None:
        if self.running:
            return
        try:
            max_posts = max(1, min(200, int(self.post_limit.get())))
        except ValueError:
            messagebox.showerror("입력 오류", "최근 글 수는 숫자로 입력하세요.")
            return

        game = PRESETS[self.selected_index]
        request = JobRequest(
            gallery_id=game["id"],
            gallery_url=game["url"],
            subject=game["subject"],
            since=collection_period()[0],
            until=collection_period()[1],
            max_posts=max_posts,
            max_pages=max(1, min(MAX_PAGES_PER_GAME, math.ceil(max_posts / 50))),
            delay=1.0,
            buy_rate=60,
            keep_raw=True,
            review_unmatched=True,
        )
        self._clear_results()
        self._clear_logs()
        self.running = True
        self.job_id = self.worker_service.create_job(request, start=False)
        self.job_label.configure(text=f"#{self.job_id[:8]}")
        self._set_state("수집 중")
        self._set_controls(running=True)
        self.job_thread = threading.Thread(target=self.worker_service.run_job, args=(self.job_id,), daemon=True)
        self.job_thread.start()
        self.root.after(300, self._poll_job)

    def _poll_job(self) -> None:
        if not self.job_id:
            return
        try:
            job = self.reader_repo.get_job(self.job_id)
            if job is None:
                raise RuntimeError("작업을 찾을 수 없습니다.")
            self._update_metrics(job["counts"])
            self._refresh_logs()
            if job["state"] in {"completed", "failed"}:
                self.running = False
                self._set_state("완료" if job["state"] == "completed" else "실패")
                if job["state"] == "failed":
                    self._append_local_log("error", job.get("error_message") or "작업 실패")
                self._load_results()
                self._set_controls(running=False)
                return
        except Exception as exc:
            self.running = False
            self._set_state("실패")
            self._append_local_log("error", str(exc))
            self._set_controls(running=False)
            return
        self.root.after(500, self._poll_job)

    def _update_metrics(self, counts: dict[str, int]) -> None:
        self.source_value.set(str(counts.get("sources", 0)))
        self.row_value.set(str(counts.get("rows", 0)))
        self.review_value.set(str(counts.get("parsed", 0) + counts.get("needs_review", 0)))

    def _refresh_logs(self) -> None:
        if not self.job_id:
            return
        logs = self.reader_repo.list_job_logs(self.job_id, limit=1000)
        if len(logs) <= self.last_log_count:
            return
        self.logs = logs
        for log in logs[self.last_log_count:]:
            details = self._log_details(log.get("details"))
            suffix = f" · {details}" if details else ""
            self._append_log_line(log["created_at"], log["level"], f"{log['message']}{suffix}")
        self.last_log_count = len(logs)

    def _log_details(self, details: Any) -> str:
        if not isinstance(details, dict):
            return ""
        keys = ("url", "characters", "body_characters", "images", "all_rows", "matching_rows", "rows", "inserted", "posted_at", "error")
        return " · ".join(f"{key}={details[key]}" for key in keys if details.get(key) not in (None, ""))

    def _append_log_line(self, created_at: str, level: str, message: str) -> None:
        try:
            stamp = datetime.fromisoformat(created_at).strftime("%H:%M:%S")
        except (TypeError, ValueError):
            stamp = str(created_at)[-8:]
        self.log_text.configure(state="normal")
        start = self.log_text.index("end-1c")
        self.log_text.insert("end", f"[{stamp}] {level.upper():7} {message}\n")
        if level in {"warning", "error"}:
            self.log_text.tag_add(level, start, "end-1c")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _append_local_log(self, level: str, message: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self._append_log_line(now, level, message)

    def _clear_logs(self) -> None:
        self.logs = []
        self.last_log_count = 0
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_logs(self) -> None:
        text = self.log_text.get("1.0", "end-1c")
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.copy_button.configure(text="복사됨")
        self.root.after(1200, lambda: self.copy_button.configure(text="전체 복사"))

    def _load_results(self) -> None:
        if not self.job_id:
            return
        rows = self.reader_service.get_results(self.job_id)
        self._clear_results()
        for row in rows:
            self.tree.insert("", "end", iid=row["id"], values=(
                f"{row.get('card_name') or row.get('card_name_raw') or '이름 미확인'}\n{row.get('post_title') or ''}",
                money(row.get("price_krw")),
                money(row.get("buy_price_krw")),
                row.get("quantity", 1),
                shipping_label(row.get("shipping_included")),
                status_label(row.get("review_status")),
                "원문",
            ), tags=(row.get("source_url") or row.get("post_url") or "",))
        self._set_controls(running=False)

    def _clear_results(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.source_value.set("0")
        self.row_value.set("0")
        self.review_value.set("0")

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self.tree.selection()
        if not selected or not self.job_id:
            return None
        row_id = selected[0]
        rows = self.reader_service.get_results(self.job_id)
        return next((row for row in rows if row["id"] == row_id), None)

    def _review_selected(self, action: str) -> None:
        if self.running:
            return
        row = self._selected_row()
        if not row:
            messagebox.showinfo("검토", "검토할 결과를 선택하세요.")
            return
        try:
            self.reader_service.review_row(row["id"], {"approve": self._review_action("approve"), "reject": self._review_action("reject")} [action])
            self._load_results()
        except Exception as exc:
            messagebox.showerror("검토 실패", str(exc))

    @staticmethod
    def _review_action(action: str):
        from kaitori_collector.contracts import ReviewAction

        return ReviewAction(action=action, actor="admin")

    def _export_csv(self) -> None:
        if not self.job_id or self.running:
            return
        try:
            rows = self.reader_service.export_results(self.job_id)
            if not rows:
                messagebox.showinfo("내보내기", "승인된 결과가 없습니다.")
                return
            target = filedialog.asksaveasfilename(
                title="승인 결과 저장",
                defaultextension=".csv",
                filetypes=[("CSV 파일", "*.csv")],
                initialfile=f"kaitori-{datetime.now():%Y%m%d-%H%M}.csv",
            )
            if not target:
                return
            game = PRESETS[self.selected_index]
            with open(target, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["게임명", "카드명", "원문명", "판매가", "매입가", "수량", "배송", "상태", "원문 URL"])
                for row in rows:
                    writer.writerow([
                        game["name"], row.get("card_name_raw", ""), row.get("post_title", ""), row.get("price_krw", ""),
                        round(row.get("price_krw", 0) * 0.6), row.get("quantity", 1), shipping_label(row.get("shipping_included")),
                        status_label(row.get("status")), row.get("post_url", ""),
                    ])
            self._load_results()
            messagebox.showinfo("내보내기 완료", f"{len(rows)}건을 저장했습니다.")
        except Exception as exc:
            messagebox.showerror("내보내기 실패", str(exc))

    def _open_selected_url(self, _event: tk.Event) -> None:
        row = self._selected_row()
        if not row:
            return
        import webbrowser

        webbrowser.open(row.get("source_url") or row.get("post_url") or "")

    def _set_controls(self, *, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.reset_button.configure(state="disabled" if running or not self.job_id else "normal")
        self.approve_button.configure(state="disabled" if running or not self.job_id else "normal")
        self.reject_button.configure(state="disabled" if running or not self.job_id else "normal")
        self.export_button.configure(state="disabled" if running or not self.job_id else "normal")
        for button in self.game_buttons:
            button.configure(state="disabled" if running else "normal")

    def _reset(self) -> None:
        if self.running:
            return
        self.job_id = None
        self.job_label.configure(text="-")
        self._set_state("대기 중")
        self._clear_results()
        self._clear_logs()
        self._set_controls(running=False)

    def _close(self) -> None:
        if self.running and not messagebox.askyesno("종료", "수집 중입니다. 종료할까요?"):
            return
        self.service_repo.close()
        self.reader_repo.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    KaitoriApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
