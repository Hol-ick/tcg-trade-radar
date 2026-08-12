"""Playwright smoke test for the static weekly collection console."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def range_dates(value: str) -> tuple[date, date]:
    start, end = [date.fromisoformat(item.strip().replace(".", "-")) for item in value.split("—")]
    return start, end


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--path", default="/")
    arguments.add_argument("--base-url", default="http://127.0.0.1:5173")
    options = arguments.parse_args()
    ARTIFACTS.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page: Page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"{options.base_url}{options.path}", wait_until="networkidle")
        page.screenshot(path=str(ARTIFACTS / "weekly-console-before.png"), full_page=True)
        page.get_by_role("heading", name="판매글을 주 단위로 확인합니다.").wait_for()
        assert page.get_by_role("button", name="이전 주").is_enabled()
        current_text = page.locator(".week-buttons strong").inner_text()
        current_start, current_end = range_dates(current_text)
        page.get_by_role("button", name="이전 주").click()
        page.get_by_text("이 기간의 수집 데이터가 없습니다.").wait_for(timeout=10_000)
        previous_text = page.locator(".week-buttons strong").inner_text()
        previous_start, previous_end = range_dates(previous_text)
        assert previous_start == current_start - timedelta(days=7)
        assert previous_end == current_end - timedelta(days=7)
        page.get_by_role("button", name="다음 주").click()
        page.locator(".week-buttons strong").filter(has_text=current_text).wait_for(timeout=10_000)
        page.locator(".count-badge").filter(has_text=re.compile(r"[1-9]\d* rows")).wait_for(timeout=10_000)
        next_button = page.get_by_role("button", name="다음 주")
        assert not next_button.is_enabled()

        csv_download = None
        if page.get_by_role("link", name="CSV 저장").count():
            with page.expect_download() as download_info:
                page.get_by_role("link", name="CSV 저장").click()
            csv_download = download_info.value
            csv_download.save_as(str(ARTIFACTS / "weekly-console.csv"))

        body = page.locator("body").inner_text()
        result = {
            "path": options.path,
            "current_range": current_text,
            "previous_range": previous_text,
            "shifted_by_days": (current_start - previous_start).days,
            "next_disabled": not next_button.is_enabled(),
            "rows_text": next((line for line in body.splitlines() if re.fullmatch(r"\d+ rows", line)), "0 rows"),
            "csv_downloaded": csv_download is not None,
            "worker_copy_present": bool(re.search(r"worker|폴링|API 토큰", body, re.IGNORECASE)),
            "dev_tag_present": "DEV" in body if options.path.rstrip("/") == "/dev" else None,
        }
        page.screenshot(path=str(ARTIFACTS / "weekly-console-after.png"), full_page=True)
        (ARTIFACTS / "weekly-console-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        browser.close()
        return 0 if result["shifted_by_days"] == 7 and not result["worker_copy_present"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
