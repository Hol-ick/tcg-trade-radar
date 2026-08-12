"""Playwright-backed read-only transport for public gallery pages."""
from __future__ import annotations

import atexit
import os
import shutil
import threading
from typing import Any
from urllib.parse import urlencode


class BrowserTransportError(RuntimeError):
    """The browser could not obtain a usable public HTML response."""

    def __init__(self, url: str, *, status: int | None, characters: int, title: str, reason: str) -> None:
        self.url = url
        self.status = status
        self.characters = characters
        self.title = title
        self.reason = reason
        super().__init__(f"브라우저 응답을 사용할 수 없습니다 (url={url}, status={status}, characters={characters}, reason={reason})")

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "characters": self.characters,
            "title": self.title,
            "reason": self.reason,
            "transport": "playwright",
        }


class PlaywrightTransport:
    """Reuse one browser page for bounded, read-only page fetches."""

    def __init__(self, *, headless: bool = True, executable_path: str = "", user_agent: str = "") -> None:
        self.headless = headless
        self.executable_path = executable_path
        self.user_agent = user_agent
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._lock = threading.RLock()

    def fetch(self, url: str, timeout: float = 30.0) -> str:
        with self._lock:
            page = self._ensure_page()
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=max(1, int(timeout * 1000)))
                page.wait_for_timeout(350)
                html = page.content()
                status = response.status if response is not None else None
                title = page.title()
            except Exception as exc:
                raise BrowserTransportError(url, status=None, characters=0, title="", reason=f"navigation_failed:{exc}") from exc
            if len(html.strip()) <= 80:
                raise BrowserTransportError(url, status=status, characters=len(html), title=title, reason="empty_or_shell")
            return html

    def fetch_comment(
        self,
        post_url: str,
        gallery_id: str,
        post_number: str,
        ci_t: str,
        page: int = 1,
        timeout: float = 30.0,
    ) -> str:
        with self._lock:
            browser_page = self._ensure_page()
            current_url = browser_page.url
            if not current_url.startswith(post_url):
                browser_page.goto(post_url, wait_until="domcontentloaded", timeout=max(1, int(timeout * 1000)))
            payload = urlencode({"ci_t": ci_t, "id": gallery_id, "no": post_number, "comment_page": str(page)})
            return browser_page.evaluate(
                """
                async ({endpoint, payload}) => {
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        body: payload
                    });
                    return await response.text();
                }
                """,
                {"endpoint": "https://gall.dcinside.com/comment/view", "payload": payload},
            )

    def close(self) -> None:
        with self._lock:
            if self._browser is not None:
                self._browser.close()
            if self._playwright is not None:
                self._playwright.stop()
            self._browser = None
            self._playwright = None
            self._page = None

    def _ensure_page(self) -> Any:
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserTransportError("playwright", status=None, characters=0, title="", reason="playwright_not_installed") from exc

        self._playwright = sync_playwright().start()
        launch_options: dict[str, Any] = {"headless": self.headless}
        if self.executable_path:
            launch_options["executable_path"] = self.executable_path
        try:
            self._browser = self._playwright.chromium.launch(**launch_options)
        except Exception as exc:
            self.close()
            raise BrowserTransportError("playwright", status=None, characters=0, title="", reason=f"launch_failed:{exc}") from exc
        context_options: dict[str, Any] = {"locale": "ko-KR"}
        if self.user_agent:
            context_options["user_agent"] = self.user_agent
        context = self._browser.new_context(**context_options)
        self._page = context.new_page()
        return self._page


def browser_headless_from_env() -> bool:
    return os.environ.get("TCG_TRADE_BROWSER_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}


def browser_executable_from_env() -> str:
    configured = os.environ.get("TCG_TRADE_BROWSER_EXECUTABLE", "").strip()
    if configured:
        return configured
    for candidate in (
        shutil.which("chrome.exe"),
        shutil.which("msedge.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


_default_transport: PlaywrightTransport | None = None
_default_lock = threading.Lock()


def get_default_transport(*, user_agent: str = "") -> PlaywrightTransport:
    global _default_transport
    with _default_lock:
        if _default_transport is None:
            _default_transport = PlaywrightTransport(
                headless=browser_headless_from_env(),
                executable_path=browser_executable_from_env(),
                user_agent=user_agent,
            )
        return _default_transport


def close_default_transport() -> None:
    global _default_transport
    with _default_lock:
        if _default_transport is not None:
            _default_transport.close()
        _default_transport = None


atexit.register(close_default_transport)
