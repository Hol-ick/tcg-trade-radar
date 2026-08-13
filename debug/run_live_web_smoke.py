from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.locator("#max-posts").fill("1")
        page.locator("#max-pages").fill("1")
        page.locator("#delay").fill("0")
        page.locator("button[type='submit']").click()
        page.get_by_role("heading", name="수집 완료").wait_for(timeout=90_000)
        if page.get_by_text("원문 0 · 결과 0 · 댓글 0").count():
            raise AssertionError("수집 완료 후 결과 카운트가 0입니다")
        if page.get_by_text("수집을 시작하면 단계별 로그가 표시됩니다.").count():
            raise AssertionError("수집 로그가 표시되지 않았습니다")
        print({
            "status": page.get_by_role("heading", name="수집 완료").inner_text(),
            "result_rows": page.locator("tbody tr").count(),
            "log_rows": page.locator(".log-row").count(),
        })
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
