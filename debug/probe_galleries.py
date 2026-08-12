"""Read-only gallery probe inspired by GhostProtocol's source sampler.

It checks gallery responses without creating jobs or writing SQLite state.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kaitori_collector.html import DCInsideHTMLParser, normalize_space
from kaitori_collector.observability import inspect_source_response
from kaitori_collector.parser import build_list_url, fetch_text


def probe_gallery(gallery_id: str, subjects: tuple[str, ...], pages: int, limit: int) -> dict[str, object]:
    pages_result: list[dict[str, object]] = []
    for page in range(1, pages + 1):
        url = build_list_url(gallery_id, page)
        try:
            html = fetch_text(url)
            profile = inspect_source_response(html, url, expected="list")
            parser = DCInsideHTMLParser()
            parser.feed(html)
            matching = [
                {"subject": normalize_space(item.get("subject", "")), "url": urljoin(url, item["href"]), "title": item.get("title", "")}
                for item in parser.list_rows
                if normalize_space(item.get("subject", "")) in subjects and item.get("href")
            ][:limit]
            pages_result.append({"page": page, "url": url, "profile": profile.as_dict(), "matching": matching})
        except Exception as exc:
            pages_result.append({"page": page, "url": url, "error": {"type": type(exc).__name__, "message": str(exc)[:300]}})
    return {"gallery_id": gallery_id, "subjects": subjects, "pages": pages_result}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Read-only DCInside gallery response probe")
    parser.add_argument("--gallery", action="append", required=True, help="gallery id; repeat for multiple galleries")
    parser.add_argument("--subjects", default="판매,구매,거래,🔁거래")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.pages <= 20:
        raise ValueError("--pages must be between 1 and 20")
    subjects = tuple(dict.fromkeys(item.strip() for item in args.subjects.split(",") if item.strip()))
    result = [probe_gallery(gallery_id.strip(), subjects, args.pages, max(1, min(args.limit, 100))) for gallery_id in args.gallery if gallery_id.strip()]
    print(json.dumps({"mode": "read_only_probe", "galleries": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
