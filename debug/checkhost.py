"""Read-only Windows environment and public source preflight for TCG Trade Radar.

This module intentionally uses only the Python standard library so it can run
before the project dependencies are installed. It reports response shape and
status only; it never stores or prints HTML, cookies, authorization headers,
or post contents.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


MIN_PYTHON = (3, 11)
MAX_SAMPLE_BYTES = 64 * 1024
DEFAULT_TARGETS = (
    "https://m.dcinside.com/board/tcggame",
    "https://m.dcinside.com/board/onepiececardgame",
    "https://m.dcinside.com/board/pokemoncardgame",
    "https://m.dcinside.com/board/digimontcg",
    "https://m.dcinside.com/board/vg",
    "https://github.com/Hol-ick/tcg-trade-radar",
)


def parse_python_version(value: str) -> tuple[int, int, int] | None:
    """Extract a semantic Python version from launcher or interpreter output."""
    match = re.search(r"(?:Python\s+)?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_supported_python(version: tuple[int, int, int] | None) -> bool:
    return version is not None and version[:2] >= MIN_PYTHON


def classify_response(
    status_code: int | None,
    body_bytes: int,
    *,
    error_type: str | None = None,
) -> str:
    """Classify transport shape without interpreting source HTML."""
    if error_type:
        return "error"
    if status_code in {401, 403, 406, 429, 503}:
        return "blocked"
    if status_code is None or status_code < 200 or status_code >= 400:
        return "error"
    if body_bytes <= 0:
        return "empty"
    return "ok"


def _browser_paths() -> list[str]:
    candidates = [
        shutil.which("chrome.exe"),
        shutil.which("msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
    ]
    return list(dict.fromkeys(str(Path(item)) for item in candidates if item and Path(item).exists()))


def _package_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def build_environment_report(project_root: Path, *, executable: str | None = None) -> dict[str, Any]:
    """Return a local-only report suitable for console or JSON output."""
    executable_path = Path(executable or sys.executable)
    version = tuple(sys.version_info[:3]) if executable is None or executable == sys.executable else None
    if version is None:
        version = parse_python_version(" ".join(str(part) for part in sys.version_info[:3]))
    browsers = _browser_paths()
    packages = {"PySide6": _package_available("PySide6"), "playwright": _package_available("playwright")}
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    storage_dir = project_root / ".audit"
    report: dict[str, Any] = {
        "python_executable": executable_path.name,
        "python_version": ".".join(str(part) for part in version) if version else None,
        "python_supported": is_supported_python(version),
        "venv_present": venv_python.exists(),
        "venv_python_present": venv_python.exists(),
        "packages": packages,
        "browser_paths": browsers,
        "browser_available": bool(browsers),
        "project_file_present": (project_root / "pyproject.toml").exists(),
        "storage_dir_present": storage_dir.exists(),
    }
    report["ready"] = bool(
        report["python_supported"]
        and report["project_file_present"]
        and all(packages.values())
        and report["browser_available"]
    )
    return report


def _target_label(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.netloc}{path}"


def probe_url(url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    """Probe a public URL and return metadata without retaining response text."""
    started = time.monotonic()
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
            "User-Agent": "TCG-Trade-Radar/1.0 read-only preflight",
        },
        method="GET",
    )
    status_code: int | None = None
    body_bytes = 0
    content_type = ""
    error_type: str | None = None
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = int(response.status)
            content_type = response.headers.get_content_type()
            body_bytes = len(response.read(MAX_SAMPLE_BYTES))
    except HTTPError as error:
        status_code = int(error.code)
        content_type = error.headers.get_content_type() if error.headers else ""
        error_type = "HTTPError"
    except (URLError, TimeoutError, OSError) as error:
        error_type = type(error).__name__
    return {
        "target": _target_label(url),
        "state": classify_response(status_code, body_bytes, error_type=error_type),
        "status_code": status_code,
        "body_bytes_sampled": body_bytes,
        "content_type": content_type,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "error_type": error_type,
    }


def run_report(project_root: Path, *, skip_network: bool = False, timeout: float = 8.0) -> dict[str, Any]:
    environment = build_environment_report(project_root)
    report: dict[str, Any] = {"environment": environment, "network": []}
    if not skip_network:
        report["network"] = [probe_url(url, timeout=timeout) for url in DEFAULT_TARGETS]
    report["network_checked"] = not skip_network
    report["network_ready"] = all(item["state"] == "ok" for item in report["network"])
    report["ready"] = bool(environment["ready"] and (skip_network or report["network_ready"]))
    return report


def _state_label(state: str) -> str:
    return {"ok": "정상", "empty": "빈 응답", "blocked": "차단/제한", "error": "오류"}.get(state, state)


def render_report(report: dict[str, Any]) -> str:
    environment = report["environment"]
    packages = environment["packages"]
    lines = ["TCG Trade Radar 환경 점검", "=" * 30]
    lines.append(f"Python: {_state_label('ok') if environment['python_supported'] else '설치 필요'} {environment.get('python_version') or '확인 불가'}")
    lines.append(f"프로젝트: {_state_label('ok') if environment['project_file_present'] else '확인 필요'}")
    lines.append(f"가상환경: {_state_label('ok') if environment['venv_python_present'] else '설치 필요'}")
    lines.append(f"PySide6: {_state_label('ok') if packages['PySide6'] else '설치 필요'}")
    lines.append(f"Playwright: {_state_label('ok') if packages['playwright'] else '설치 필요'}")
    lines.append(f"브라우저: {_state_label('ok') if environment['browser_available'] else '설치 필요 (Chrome/Edge 또는 Chromium)'}")
    lines.append(f"저장 폴더: {_state_label('ok') if environment['storage_dir_present'] else '첫 실행 때 생성'}")
    if report["network_checked"]:
        lines.append("")
        lines.append("공개 주소 점검")
        for item in report["network"]:
            suffix = f"HTTP {item['status_code']}" if item["status_code"] else (item["error_type"] or "응답 없음")
            lines.append(f"- {_state_label(item['state']):8} {item['target']} · {suffix} · {item['elapsed_ms']}ms")
    lines.append("")
    if not environment["ready"]:
        lines.append("결과: 설치가 더 필요합니다. debug\\setup-trade-radar.bat를 먼저 실행하세요.")
    elif report["network_checked"] and not report["network_ready"]:
        lines.append("결과: 로컬 실행 환경은 준비됐지만 공개 주소 점검에 실패했습니다. 로그의 상태를 확인하세요.")
    else:
        lines.append("결과: 데스크톱 앱을 실행할 준비가 됐습니다.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TCG Trade Radar read-only environment and host check")
    parser.add_argument("--skip-network", action="store_true", help="공개 주소 요청을 생략합니다")
    parser.add_argument("--json", action="store_true", help="기계 판독용 JSON만 출력합니다")
    parser.add_argument("--timeout", type=float, default=8.0, help="주소별 제한 시간(초)")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    report = run_report(args.project_root.resolve(), skip_network=args.skip_network, timeout=max(1.0, args.timeout))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_report(report))
    if not report["environment"]["ready"]:
        return 2
    if report["network_checked"] and not report["network_ready"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
