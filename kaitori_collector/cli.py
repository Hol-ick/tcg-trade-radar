"""Command line entry point for extraction and the worker server."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import __version__
from .parser import DEFAULT_USER_AGENT, run_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kaitori-collector")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--db", type=Path, default=Path(os.getenv("KAITORI_DB", "kaitori.sqlite3")))
    parser.add_argument("--serve", action="store_true", help="run the HTTP worker API")
    parser.add_argument("--host", default=os.getenv("KAITORI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("KAITORI_PORT", "8787")))
    parser.add_argument("--api-token", default=os.getenv("KAITORI_API_TOKEN", ""))
    parser.add_argument("--data-root", type=Path, default=Path(os.getenv("KAITORI_DATA_ROOT", "data")))
    parser.add_argument("--post-url")
    parser.add_argument("--gallery-id")
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--subject", default="판매")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--max-posts", type=int, default=20)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.serve:
        from .server import serve

        serve(args.host, args.port, args.db, args.data_root, args.api_token)
        return 0
    if not args.post_url and not args.gallery_id:
        parser.error("one of --post-url, --gallery-id, or --serve is required")
    if args.post_url and args.gallery_id:
        parser.error("--post-url and --gallery-id are mutually exclusive")
    try:
        return run_cli(args)
    except ValueError as exc:
        parser.error(str(exc))
    return 2
