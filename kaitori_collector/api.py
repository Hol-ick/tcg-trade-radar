"""HTTP-independent route application used by the JSON worker server and tests."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .contracts import JobRequest, ReviewAction, SellerReviewAction
from .service import JobService


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: Any
    content_type: str = "application/json; charset=utf-8"


class WorkerApplication:
    def __init__(self, service: JobService, *, api_token: str = "", start_jobs: bool = True) -> None:
        self.service = service
        self.api_token = api_token.strip()
        self.start_jobs = start_jobs

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> ApiResponse:
        headers = {key.lower(): value for key, value in (headers or {}).items()}
        parsed = urlparse(path)
        route = parsed.path.rstrip("/") or "/"
        if method.upper() == "OPTIONS":
            return ApiResponse(204, None)
        if route == "/health" and method.upper() == "GET":
            return ApiResponse(200, {"version": __version__})
        if not self._authorized(headers):
            return ApiResponse(401, {"error": "authorization required"})
        try:
            return self._route(method.upper(), route, parse_qs(parsed.query), payload or {})
        except KeyError as exc:
            return ApiResponse(404, {"error": str(exc).strip("'")})
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return ApiResponse(400, {"error": str(exc)})
        except Exception as exc:  # keep server alive and avoid leaking internals
            return ApiResponse(500, {"error": str(exc)[:500]})

    def _route(self, method: str, route: str, query: dict[str, list[str]], payload: dict[str, Any]) -> ApiResponse:
        if route == "/jobs" and method == "POST":
            request = JobRequest.from_dict(payload)
            job_id = self.service.create_job(request, start=self.start_jobs)
            return ApiResponse(202, {"job_id": job_id, "id": job_id})

        if route == "/market/listings" and method == "GET":
            return ApiResponse(200, {"rows": self.service.get_market_listings(**_market_filters(query))})
        if route == "/market/cards" and method == "GET":
            filters = _market_filters(query)
            filters.pop("min_price", None)
            filters.pop("max_price", None)
            filters.pop("status", None)
            return ApiResponse(200, {"cards": self.service.get_market_cards(**filters)})
        if route == "/market/snapshots" and method == "GET":
            return ApiResponse(200, {"snapshots": self.service.get_demand_snapshots(
                game_id=_query_value(query, "game_id"),
                card_key=_query_value(query, "card_key"),
                limit=int(_query_value(query, "limit") or 365),
            )})
        if route == "/market/snapshots" and method == "POST":
            game_id = str(payload.get("game_id") or "").strip()
            snapshot_date = str(payload.get("snapshot_date") or "").strip()
            if not game_id or not snapshot_date:
                raise ValueError("game_id and snapshot_date are required")
            count = self.service.repository.refresh_demand_snapshot(snapshot_date, game_id, since=payload.get("since"), until=payload.get("until"))
            return ApiResponse(201, {"game_id": game_id, "snapshot_date": snapshot_date, "count": count})
        if route == "/market/sellers" and method == "GET":
            return ApiResponse(200, {"sellers": self.service.get_sellers(
                game_id=_query_value(query, "game_id"),
                query_text=_query_value(query, "q"),
                risk_level_filter=_query_value(query, "risk_level"),
                limit=int(_query_value(query, "limit") or 200),
            )})
        if route == "/market/risk-signals" and method == "GET":
            return ApiResponse(200, {"signals": self.service.get_risk_signals(
                seller_id=_query_value(query, "seller_id"),
                severity=_query_value(query, "severity"),
                status=_query_value(query, "status"),
                limit=int(_query_value(query, "limit") or 200),
            )})

        parts = [part for part in route.split("/") if part]
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "csv" and method == "GET":
            return ApiResponse(200, self.service.export_csv(parts[1]), "text/csv; charset=utf-8")
        if len(parts) == 2 and parts[0] == "jobs" and method == "GET":
            return ApiResponse(200, self.service.get_job_status(parts[1]))
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "logs" and method == "GET":
            limit = int(query.get("limit", ["500"])[0])
            return ApiResponse(200, {"job_id": parts[1], "logs": self.service.get_logs(parts[1], limit=limit)})
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "comments" and method == "GET":
            limit = int(query.get("limit", ["2000"])[0])
            return ApiResponse(200, {"job_id": parts[1], "comments": self.service.get_comments(parts[1], limit=limit)})
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "results" and method == "GET":
            approved_only = query.get("approved_only", ["false"])[0].lower() == "true"
            return ApiResponse(200, {"job_id": parts[1], "rows": self.service.get_results(parts[1], approved_only=approved_only)})
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "retry" and method == "POST":
            self.service.retry_job(parts[1], start=self.start_jobs)
            return ApiResponse(202, {"job_id": parts[1], "id": parts[1]})
        if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "export" and method == "POST":
            return ApiResponse(200, {"job_id": parts[1], "rows": self.service.export_results(parts[1])})
        if len(parts) == 3 and parts[0] == "rows" and parts[2] == "review" and method == "POST":
            action = ReviewAction.from_dict(payload)
            return ApiResponse(200, self.service.review_row(parts[1], action))
        if len(parts) == 3 and parts[0] == "sellers" and parts[2] == "review" and method == "POST":
            action = SellerReviewAction.from_dict(payload)
            return ApiResponse(200, self.service.review_seller(parts[1], action))
        if len(parts) == 2 and parts[0] == "sellers" and method == "GET":
            return ApiResponse(200, self.service.get_seller(parts[1]))
        return ApiResponse(404, {"error": "route not found"})

    def _authorized(self, headers: dict[str, str]) -> bool:
        if not self.api_token:
            return True
        return headers.get("authorization", "") == f"Bearer {self.api_token}"


def _query_value(query: dict[str, list[str]], key: str) -> str:
    return str(query.get(key, [""])[0] or "").strip()


def _market_filters(query: dict[str, list[str]]) -> dict[str, Any]:
    def optional_int(key: str) -> int | None:
        value = _query_value(query, key)
        return int(value) if value else None

    return {
        "query_text": _query_value(query, "q"),
        "game_id": _query_value(query, "game_id"),
        "listing_type": _query_value(query, "listing_type"),
        "since": _query_value(query, "since") or None,
        "until": _query_value(query, "until") or None,
        "min_price": optional_int("min_price"),
        "max_price": optional_int("max_price"),
        "status": _query_value(query, "status"),
        "sort": _query_value(query, "sort") or "recent",
        "limit": int(_query_value(query, "limit") or 200),
    }
