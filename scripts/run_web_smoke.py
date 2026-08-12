"""Browser smoke test for the local web surface and one bounded live crawl."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.screenshot(path=str(ARTIFACTS / "web-ui-before-crawl.png"), full_page=True)
        page.get_by_text("실행 상태", exact=True).wait_for()
        page.get_by_label("최대 게시글").fill("3")
        page.get_by_role("button", name="실제 수집 시작").click()

        page.get_by_text("worker polling", exact=False).wait_for(timeout=10_000)
        terminal_badge = page.locator("[data-slot='badge']").filter(has_text=re.compile(r"^(완료|실패)$"))
        terminal_badge.wait_for(timeout=180_000)
        page.wait_for_timeout(1_000)
        page.screenshot(path=str(ARTIFACTS / "web-ui-after-crawl.png"), full_page=True)

        body_text = page.locator("body").inner_text()
        state = "completed" if terminal_badge.filter(has_text="완료").count() else "failed"
        print(json.dumps({
            "state": state,
            "contains_source_setup": "수집 범위를 고르세요" in body_text,
            "contains_result_panel": "추출 결과" in body_text,
            "contains_diagnostics": "HTTP" in body_text or "응답" in body_text or "목록" in body_text,
            "body_excerpt": body_text[-1600:],
            "screenshots": [
                "artifacts/web-ui-before-crawl.png",
                "artifacts/web-ui-after-crawl.png",
            ],
        }, ensure_ascii=False, indent=2))
        browser.close()
        return 0 if state in {"completed", "failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
