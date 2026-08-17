#!/usr/bin/env python3
"""Build the Windows source package published on the GitHub release page."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
ROOT_FILES = (".env.example", ".gitattributes", "README.md", "pyproject.toml")
DIRECTORIES = ("kaitori_collector", "migrations")
DEBUG_FILES = (
    "checkhost.bat",
    "checkhost.py",
    "probe_galleries.py",
    "run-kaitori.bat",
    "run-probe.bat",
    "run_week_collection.py",
    "run_yugioh_sample.py",
    "setup-trade-radar.bat",
    "trade_radar_desktop.py",
)
DOC_FILES = ("desktop-app.md", "preprocessing-quality.md", "windows-setup.md")


def project_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"^version\s*=\s*['\"]([^'\"]+)['\"]\s*$", pyproject, re.MULTILINE)
    if not match:
        raise RuntimeError("pyproject.toml에 프로젝트 버전이 없습니다.")
    return match.group(1)


def source_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip()


def iter_directory_files(directory: str) -> list[Path]:
    base = ROOT / directory
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def package_files() -> list[Path]:
    paths = [ROOT / path for path in ROOT_FILES]
    for directory in DIRECTORIES:
        paths.extend(iter_directory_files(directory))
    paths.extend(ROOT / "debug" / path for path in DEBUG_FILES)
    paths.extend(ROOT / "docs" / path for path in DOC_FILES)

    missing = [path.relative_to(ROOT).as_posix() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"릴리스 패키지에 필요한 파일이 없습니다: {', '.join(missing)}")
    return sorted(set(paths), key=lambda path: path.relative_to(ROOT).as_posix())


def package_readme(version: str, commit: str) -> str:
    return f"""TCG Trade Radar Windows 패키지
================================

버전: {version}
소스 커밋: {commit}

1. 이 폴더를 원하는 위치에 압축 해제합니다.
2. debug\\setup-trade-radar.bat 를 한 번 실행합니다.
3. debug\\checkhost.bat 를 실행해 설치 상태를 확인합니다.
4. debug\\run-kaitori.bat 를 실행해 수집기를 엽니다.

이 패키지는 Python/PySide6 기반의 로컬 수집기 소스 패키지입니다.
휴대형 Collector.exe, 기존 수집 데이터, 가상환경, Git 기록은 포함하지 않습니다.
실행 중 .venv 및 .audit 폴더가 패키지 루트에 만들어집니다.

자세한 설명은 docs\\windows-setup.md 를 확인하세요.
"""


def build(output_dir: Path, version: str | None = None) -> Path:
    version = version or project_version()
    commit = source_commit()
    package_name = f"tcg-trade-radar-windows-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{package_name}.zip"
    files = package_files()
    manifest = {
        "package": package_name,
        "version": version,
        "source_commit": commit,
        "included_files": [path.relative_to(ROOT).as_posix() for path in files],
        "excluded": [".git", ".venv", ".audit", "data", "web/public/data", "web/node_modules"],
    }

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        root_prefix = f"{package_name}/"
        readme_info = zipfile.ZipInfo(f"{root_prefix}PACKAGE-README.txt", FIXED_ZIP_TIME)
        readme_info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(readme_info, package_readme(version, commit).encode("utf-8"))

        manifest_info = zipfile.ZipInfo(f"{root_prefix}package-manifest.json", FIXED_ZIP_TIME)
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(
            manifest_info,
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )

        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{root_prefix}{relative}", FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TCG Trade Radar Windows 릴리스 ZIP 생성")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", help="패키지 버전 (기본값: pyproject.toml에서 읽음)")
    args = parser.parse_args()
    archive = build(args.output_dir.resolve(), args.version)
    with zipfile.ZipFile(archive) as package:
        print(f"생성 완료: {archive}")
        print(f"파일 수: {len(package.namelist())}")
        print(f"크기: {archive.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
