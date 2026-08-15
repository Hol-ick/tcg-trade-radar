"""Application service for asynchronous collection and review workflows."""
from __future__ import annotations

import csv
import io
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime
from typing import Callable, Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.error import HTTPError

from . import __version__
from .browser_transport import BrowserTransportError
from .comments import parse_comments
from .contracts import JobRequest, ReviewAction, SellerReviewAction, utc_now
from .html import DCInsideHTMLParser, parse_html, normalize_space
from .observability import inspect_source_response, is_retryable_error, retry_delay
from .parser import CSV_FIELDS, SourceResponseError, build_list_url, extract_comment_token, extract_post, fetch_comment_text_auto, fetch_text_auto
from .preprocessing import classify_post
from .storage import Repository


Fetcher = Callable[[str], str]
CommentFetcher = Callable[[str, str, str, str, int], str]


def _post_identity(post_url: str) -> str:
    parsed = urlparse(post_url)
    post_id = parse_qs(parsed.query).get("no", [""])[0]
    if not post_id:
        parts = [part for part in parsed.path.split("/") if part]
        post_id = parts[-1] if parts and parts[-1].isdigit() else ""
    return f"post:{post_id}" if post_id else f"url:{post_url}"


class _HostRequestGate:
    """Serialize request starts per host with a small, configurable floor."""

    def __init__(self, sleep: Callable[[float], None]) -> None:
        self._sleep = sleep
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str, interval: float) -> None:
        if interval <= 0:
            return
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return
        with self._lock:
            now = time.monotonic()
            remaining = self._next_allowed.get(host, 0.0) - now
            if remaining > 0:
                self._sleep(remaining)
            self._next_allowed[host] = time.monotonic() + interval


class JobService:
    def __init__(self, repository: Repository, fetcher: Fetcher | None = None, sleep: Callable[[float], None] = time.sleep, catalog: list[Any] | None = None, comment_fetcher: CommentFetcher | None = None) -> None:
        self.repository = repository
        self.fetcher = fetcher or fetch_text_auto
        self.comment_fetcher = comment_fetcher or (lambda post_url, gallery_id, post_number, ci_t, page: fetch_comment_text_auto(post_url, gallery_id, post_number, ci_t, page))
        self.sleep = sleep
        self.catalog = catalog or []
        self._threads: dict[str, threading.Thread] = {}
        self._thread_lock = threading.Lock()
        self._request_gate = _HostRequestGate(self.sleep)

    def create_job(self, request: JobRequest, *, start: bool = True) -> str:
        job_id = self.repository.create_job(request)
        if start:
            self._start_thread(job_id)
        return job_id

    def run_job(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        request = _request_from_job(job)
        self.repository.update_job(job_id, state="running", error_message="")
        subjects = request.subjects or (request.subject,)
        self._log(
            job_id,
            step="job",
            message="작업 시작",
            details={
                "gallery_id": request.gallery_id,
                "gallery_url": request.gallery_url,
                "subjects": subjects,
                "max_posts": request.max_posts,
                "max_pages": request.max_pages,
                "fetch_concurrency": request.fetch_concurrency,
                "max_retries": request.max_retries,
                "cutoff_at": request.cutoff_at,
            },
        )
        seen_urls: set[str] = set()
        posts_seen = 0
        post_fetch_pool = ThreadPoolExecutor(
            max_workers=request.fetch_concurrency,
            thread_name_prefix=f"kaitori-fetch-{request.gallery_id}",
        )
        try:
            for page in range(1, request.max_pages + 1):
                page_has_in_range_post = False
                page_has_older_post = False
                list_url = build_list_url(request.gallery_id, page, request.gallery_url)
                self._log(job_id, step="list", message=f"목록 요청 시작 · {page}페이지", details={"url": list_url})
                parser = DCInsideHTMLParser()
                list_html = self._fetch_with_retry(job_id, list_url, request, "list")
                profile = inspect_source_response(list_html, list_url, expected="list")
                self._log(job_id, step="list", message=f"목록 응답 판별 · {profile.state}", details=profile.as_dict())
                self._log(job_id, step="list", message=f"목록 응답 수신 · {len(list_html):,}자", details={"url": list_url, "characters": len(list_html)})
                parser.feed(list_html)
                all_rows = parser.list_rows
                raw_candidates = [
                    urljoin(list_url, item["href"])
                    for item in all_rows
                    if normalize_space(item.get("subject", "")) in subjects and item.get("href")
                ]
                candidates: list[str] = []
                candidate_identities: set[str] = set()
                for candidate_url in raw_candidates:
                    identity = _post_identity(candidate_url)
                    if identity in candidate_identities:
                        continue
                    candidate_identities.add(identity)
                    candidates.append(candidate_url)
                self._log(
                    job_id,
                    step="list",
                    message=f"목록 파싱 완료 · 전체 {len(all_rows)}개 / {', '.join(subjects)} {len(candidates)}개",
                    details={"page": page, "all_rows": len(all_rows), "matching_rows": len(candidates), "subjects": subjects},
                )
                if profile.state != "ok" or not all_rows:
                    self._log(
                        job_id,
                        level="warning",
                        step="list",
                        message=f"목록 응답 이상 · {profile.reason}",
                        details={"url": list_url, **profile.as_dict()},
                    )
                    if page == 1:
                        raise RuntimeError(f"목록 응답을 사용할 수 없습니다: {profile.reason}")
                elif not candidates:
                    self._log(job_id, step="list", message=f"{', '.join(subjects)} 말머리 글이 없음", details={"page": page})
                pending_fetches: dict[str, Future[str]] = {}
                existing_by_url: dict[str, dict[str, Any] | None] = {}
                remaining_slots = request.max_posts - posts_seen
                for candidate_url in candidates:
                    if candidate_url in seen_urls or remaining_slots <= 0:
                        continue
                    existing_candidate = self.repository.find_source_for_post(request.gallery_id, candidate_url)
                    existing_by_url[candidate_url] = existing_candidate
                    if existing_candidate:
                        continue
                    pending_fetches[candidate_url] = post_fetch_pool.submit(
                        self._fetch_post_html,
                        job_id,
                        candidate_url,
                        request,
                    )
                    remaining_slots -= 1

                for post_url in candidates:
                    if post_url in seen_urls or posts_seen >= request.max_posts:
                        continue
                    seen_urls.add(post_url)
                    posts_seen += 1
                    if post_url in existing_by_url:
                        existing_source = existing_by_url[post_url]
                    else:
                        existing_source = self.repository.find_source_for_post(request.gallery_id, post_url)
                    if existing_source and not existing_source.get("posted_at"):
                        page_has_in_range_post = True
                        self.repository.attach_source_to_job(job_id, existing_source["id"])
                        self._log(
                            job_id,
                            step="reuse",
                            message="기존 게시글·거래 데이터 재사용",
                            details={"url": post_url, "source_id": existing_source["id"], "posted_at": "", "date_known": False},
                        )
                        continue
                    if existing_source and existing_source.get("posted_at"):
                        posted_at = existing_source["posted_at"]
                        if request.since and _is_before_date(posted_at, request.since):
                            page_has_older_post = True
                        if _date_in_range(posted_at, request.since, request.until, request.cutoff_at):
                            page_has_in_range_post = True
                            self.repository.attach_source_to_job(job_id, existing_source["id"])
                            self._log(
                                job_id,
                                step="reuse",
                                message="기존 게시글·거래 행 재사용",
                                details={"url": post_url, "source_id": existing_source["id"], "posted_at": posted_at},
                            )
                        else:
                            self._log(
                                job_id,
                                step="reuse",
                                message="기존 게시글이 수집 범위 밖이라 제외",
                                details={"url": post_url, "source_id": existing_source["id"], "posted_at": posted_at},
                            )
                        continue
                    self._log(job_id, step="post", message=f"게시글 요청 시작 · {posts_seen}/{request.max_posts}", details={"url": post_url})
                    post_html = pending_fetches.pop(post_url).result()
                    post_profile = inspect_source_response(post_html, post_url, expected="post")
                    self._log(job_id, step="post", message=f"게시글 응답 판별 · {post_profile.state}", details=post_profile.as_dict())
                    if post_profile.state in {"empty", "blocked"}:
                        raise RuntimeError(f"게시글 응답을 사용할 수 없습니다: {post_profile.reason}")
                    self._log(job_id, step="post", message=f"게시글 응답 수신 · {len(post_html):,}자", details={"url": post_url, "characters": len(post_html)})
                    document, _ = parse_html(post_html, post_url)
                    extracted_rows = extract_post(post_html, post_url, request.gallery_id, normalize_space(request.subject))
                    posted_at = document.get("posted_at", "")
                    if request.since and _is_before_date(posted_at, request.since):
                        page_has_older_post = True
                    if _date_in_range(posted_at, request.since, request.until, request.cutoff_at):
                        page_has_in_range_post = True
                    post_quality = classify_post(
                        document.get("title", ""),
                        document.get("body", ""),
                        image_count=int(document.get("image_count") or 0),
                        row_count=len(extracted_rows),
                    )
                    self._log(
                        job_id,
                        step="parse",
                        message=f"게시글 파싱 완료 · 거래 행 {len(extracted_rows)}개",
                        details={"url": post_url, "title": document.get("title", ""), "posted_at": document.get("posted_at", ""), "rows": len(extracted_rows)},
                    )
                    if not extracted_rows:
                        body_chars = len(document.get("body", ""))
                        image_count = post_html.lower().count("<img")
                        reason = "이미지 전용 게시글 가능성" if image_count and body_chars < 80 else "가격·거래 행 패턴 미검출"
                        self._log(
                            job_id,
                            level="warning",
                            step="parse",
                            message=f"결과 0개 · {reason}",
                            details={"url": post_url, "body_characters": body_chars, "images": image_count},
                        )
                    if not _date_in_range(document.get("posted_at", ""), request.since, request.until, request.cutoff_at):
                        self._log(job_id, level="warning", step="parse", message="작성일 범위 밖이라 제외", details={"url": post_url, "posted_at": document.get("posted_at", "")})
                        continue
                    source_id, _ = self.repository.upsert_source({
                        "gallery_id": request.gallery_id,
                        "post_url": document["url"],
                        "title": document["title"],
                        "posted_at": document["posted_at"],
                        "author_name": document.get("author_name", ""),
                        "author_type": document.get("author_type", "unknown"),
                        "post_status": post_quality.status,
                        "image_count": document.get("image_count", 0),
                        "body_characters": document.get("body_characters", len(document.get("body", ""))),
                        "raw_html": post_html,
                        "keep_raw": request.keep_raw,
                    })
                    self.repository.attach_source_to_job(job_id, source_id)
                    comments_inserted = self._collect_comments(job_id, post_url, request.gallery_id, post_html, source_id, request)
                    inserted_rows = self.repository.insert_rows(job_id, source_id, extracted_rows)
                    seller = self.repository.analyze_source_risk(source_id)
                    self._log(job_id, step="risk", message="판매자 분석 완료", details={"seller_id": seller.get("seller_id"), "risk_level": seller.get("risk_level"), "risk_score": seller.get("risk_score"), "signal_count": len(seller.get("signals", []))})
                    self._log(job_id, step="store", message=f"원문·결과 저장 완료 · 신규 행 {inserted_rows}개 / 댓글 {comments_inserted}개", details={"url": post_url, "rows": len(extracted_rows), "inserted": inserted_rows, "comments": comments_inserted})
                    if self.catalog:
                        from .matcher import match_card

                        for row in self.repository.list_rows(job_id=job_id, source_id=source_id):
                            self.repository.apply_match(row["id"], match_card(row["card_name_raw"], row["rarity"], self.catalog))
                if request.since and page_has_older_post and not page_has_in_range_post:
                    self._log(
                        job_id,
                        step="list",
                        message="백필 시작일 이전 페이지에 도달하여 수집을 종료합니다",
                        details={"page": page, "since": request.since},
                    )
                    break
                if posts_seen >= request.max_posts:
                    break
                if request.delay > 0:
                    self.sleep(request.delay)
            post_fetch_pool.shutdown(wait=True)
            completed_at = utc_now()
            self.repository.update_job(job_id, state="completed", error_message="", finished_at=completed_at, last_success_at=completed_at)
            snapshot_count = self.repository.refresh_demand_snapshot(
                completed_at[:10], request.gallery_id, since=request.since, until=request.until
            )
            self._log(job_id, step="snapshot", message=f"카드 수요 스냅샷 갱신 · {snapshot_count}개", details={"game_id": request.gallery_id, "count": snapshot_count})
            daily_count = self.repository.refresh_market_daily()
            self._log(job_id, step="market_history", message=f"시장 시계열 집계 갱신 · {daily_count}개", details={"game_id": request.gallery_id, "daily_rows": daily_count})
            status = self.get_job_status(job_id)
            self._log(job_id, step="done", message=f"작업 완료 · 게시글 {posts_seen}개 / 결과 {status['counts']['rows']}개", details={"counts": status["counts"]})
        except Exception as exc:
            post_fetch_pool.shutdown(wait=True)
            error_message = f"{type(exc).__name__}: {exc}"[:500]
            self._log(job_id, level="error", step="error", message="작업 실패", details={"error": error_message})
            self.repository.update_job(job_id, state="failed", error_message=error_message, finished_at=utc_now())
        return self.get_job_status(job_id)

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        return {
            "id": job["id"],
            "gallery_id": job["gallery_id"],
            "subject": job["subject"],
            "since": job["since"],
            "until": job["until"],
            "buy_rate": job["buy_rate"],
            "state": job["state"],
            "counts": job["counts"],
            "error_message": job["error_message"] or None,
            "created_at": job["created_at"],
            "finished_at": job["finished_at"],
            "worker_version": job["worker_version"] or __version__,
            "last_success_at": job["last_success_at"],
        }

    def get_results(self, job_id: str, *, approved_only: bool = False) -> list[dict[str, Any]]:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        rows = self.repository.list_rows(job_id=job_id)
        result = []
        for row in rows:
            if approved_only and row["status"] not in {"approved", "exported"}:
                continue
            item = dict(row)
            item.pop("raw_html", None)
            item["shipping_included"] = item["shipping_included"] or "unknown"
            item["card_name"] = item["card_name_raw"]
            item["review_status"] = item["status"]
            item["source_url"] = item["post_url"]
            item["price_krw"] = item.get("price_krw_observed")
            item["buy_price_krw"] = round(item["price_krw"] * job["buy_rate"] / 100) if item["price_krw"] is not None else None
            item["listing_type"] = item.get("listing_type") or "unknown"
            item["price_type"] = item.get("price_type") or "unknown"
            item["seller_id"] = item.get("seller_id") or ""
            item["seller_name"] = item.get("seller_display_name") or item.get("author_name") or "미상"
            item["seller_risk_score"] = int(item.get("seller_risk_score") or 0)
            item["seller_risk_level"] = item.get("seller_risk_level") or "low"
            item["seller_review_status"] = item.get("seller_review_status") or "unreviewed"
            item["exportable"] = item["status"] in {"approved", "exported"}
            result.append(item)
        return result

    def get_logs(self, job_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        if self.repository.get_job(job_id) is None:
            raise KeyError(f"job not found: {job_id}")
        return self.repository.list_job_logs(job_id, limit=limit)

    def get_comments(self, job_id: str, *, limit: int = 2000) -> list[dict[str, Any]]:
        if self.repository.get_job(job_id) is None:
            raise KeyError(f"job not found: {job_id}")
        return self.repository.list_comments(job_id=job_id)[:max(1, min(limit, 5000))]

    def get_market_listings(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_market_listings(**filters)

    def get_market_cards(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.summarize_cards(**filters)

    def get_demand_snapshots(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_demand_snapshots(**filters)

    def get_sellers(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_sellers(**filters)

    def get_seller(self, seller_id: str) -> dict[str, Any]:
        seller = self.repository.get_seller(seller_id)
        if seller is None:
            raise KeyError(f"seller not found: {seller_id}")
        return seller

    def get_risk_signals(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_risk_signals(**filters)

    def review_row(self, row_id: str, action: ReviewAction) -> dict[str, Any]:
        return self.repository.record_review(row_id, action)

    def review_seller(self, seller_id: str, action: SellerReviewAction) -> dict[str, Any]:
        return self.repository.review_seller(seller_id, action)

    def export_results(self, job_id: str) -> list[dict[str, Any]]:
        rows = self.repository.export_approved_rows(job_id)
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        result = []
        for row in rows:
            item = dict(row)
            item.pop("raw_html", None)
            item["price_krw"] = item.get("price_krw_observed")
            item["buy_price_krw"] = round(item["price_krw"] * job["buy_rate"] / 100) if item["price_krw"] is not None else None
            result.append(item)
        return result

    def export_csv(self, job_id: str) -> str:
        """Serialize all extracted rows without changing their review state."""
        rows = self.get_results(job_id)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
        return "\ufeff" + output.getvalue()

    def retry_job(self, job_id: str, *, start: bool = True) -> str:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        if job["state"] not in {"failed", "completed"}:
            raise ValueError("only failed or completed jobs can be retried")
        self.repository.reset_job(job_id)
        if start:
            self._start_thread(job_id)
        return job_id

    def _start_thread(self, job_id: str) -> None:
        with self._thread_lock:
            existing = self._threads.get(job_id)
            if existing and existing.is_alive():
                return
            thread = threading.Thread(target=self.run_job, args=(job_id,), name=f"kaitori-{job_id}", daemon=True)
            self._threads[job_id] = thread
            thread.start()

    def _log(
        self,
        job_id: str,
        *,
        level: str = "info",
        step: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.repository.add_job_log(job_id, level=level, step=step, message=message, details=details)

    def _fetch_post_html(self, job_id: str, post_url: str, request: JobRequest) -> str:
        """Fetch one post in a bounded pool with host-level pacing."""
        return self._fetch_with_retry(job_id, post_url, request, "post")

    def _fetch_with_retry(self, job_id: str, url: str, request: JobRequest, step: str) -> str:
        for attempt in range(request.max_retries + 1):
            try:
                # Keep the existing user delay as the requested value, but
                # enforce a conservative floor even when it is configured as 0.
                self._request_gate.wait(url, max(0.75, request.delay))
                body = self.fetcher(url)
                if step in {"list", "post"}:
                    profile = inspect_source_response(body, url, expected=step)
                    if profile.state == "blocked":
                        self._log(
                            job_id,
                            level="error",
                            step=step,
                            message="차단 응답 감지 · 추가 요청 중단",
                            details={"url": url, **profile.as_dict()},
                        )
                        raise RuntimeError(f"공개 원본 차단 응답: {profile.reason}")
                    if profile.state in {"empty", "structure_changed", "suspicious"} and attempt < request.max_retries:
                        wait = retry_delay(attempt)
                        self._log(
                            job_id,
                            level="warning",
                            step=step,
                            message=f"원본 응답 구조 재시도 · {attempt + 1}/{request.max_retries}",
                            details={"url": url, "state": profile.state, "reason": profile.reason, "delay_seconds": wait},
                        )
                        self.sleep(wait)
                        continue
                return body
            except Exception as exc:
                if isinstance(exc, HTTPError) and 400 <= exc.code < 500:
                    self._log(
                        job_id,
                        level="error",
                        step=step,
                        message="HTTP 접근 제한 응답 · 추가 요청 중단",
                        details={"url": url, "status": exc.code, "error_type": type(exc).__name__},
                    )
                    raise
                if isinstance(exc, (SourceResponseError, BrowserTransportError)):
                    response_message = "원본 응답 구조가 인식되지 않아 fallback을 계속 시도합니다" if isinstance(exc, SourceResponseError) and "response-shape-unrecognized" in exc.fallback_error else "원본 서버가 빈 응답을 반환해 수집을 중단"
                    self._log(
                        job_id,
                        level="error",
                        step=step,
                        message=response_message,
                        details=exc.as_dict(),
                    )
                shape_retryable = isinstance(exc, SourceResponseError) and "response-shape-unrecognized" in exc.fallback_error
                if attempt >= request.max_retries or not (is_retryable_error(exc) or shape_retryable):
                    raise
                wait = retry_delay(attempt)
                self._log(job_id, level="warning", step=step, message=f"요청 재시도 대기 · {attempt + 1}/{request.max_retries}", details={"url": url, "error_type": type(exc).__name__, "delay_seconds": wait})
                self.sleep(wait)
        raise RuntimeError("unreachable fetch retry state")

    def _collect_comments(self, job_id: str, post_url: str, gallery_id: str, post_html: str, source_id: str, request: JobRequest) -> int:
        inline_comments = parse_comments(post_html, post_url, gallery_id)
        total_inserted = 0
        if inline_comments:
            inserted = self.repository.insert_comments(source_id, inline_comments)
            total_inserted += inserted
            self._log(
                job_id,
                step="comments",
                message=f"본문 포함 댓글 파싱 완료 · {len(inline_comments)}개 / 신규 {inserted}개",
                details={"url": post_url, "page": 1, "comments": len(inline_comments), "inserted": inserted, "transport": "post_html"},
            )
        ci_t = extract_comment_token(post_html)
        post_number = parse_qs(urlparse(post_url).query).get("no", [""])[0]
        if not ci_t or not post_number:
            if not inline_comments:
                self._log(job_id, level="warning", step="comments", message="댓글 조회 토큰 또는 게시글 번호 없음", details={"url": post_url})
            return total_inserted
        for page in range(1, 26):
            try:
                html = self._fetch_comment_with_retry(job_id, post_url, gallery_id, post_number, ci_t, page, request)
            except Exception as exc:
                self._log(job_id, level="warning", step="comments", message="댓글 조회 실패 · 게시글 수집은 계속", details={"url": post_url, "page": page, "error_type": type(exc).__name__, "error": str(exc)[:200]})
                break
            if not html.strip():
                self._log(job_id, level="warning", step="comments", message="댓글 응답이 비어 있음", details={"url": post_url, "page": page})
                break
            comments = parse_comments(html, post_url, gallery_id)
            inserted = self.repository.insert_comments(source_id, comments)
            total_inserted += inserted
            self._log(job_id, step="comments", message=f"댓글 파싱 완료 · {len(comments)}개 / 신규 {inserted}개", details={"url": post_url, "page": page, "comments": len(comments), "inserted": inserted})
            if len(comments) < 40:
                break
        return total_inserted

    def _fetch_comment_with_retry(self, job_id: str, post_url: str, gallery_id: str, post_number: str, ci_t: str, page: int, request: JobRequest) -> str:
        for attempt in range(request.max_retries + 1):
            try:
                self._request_gate.wait(post_url, max(0.75, request.delay))
                body = self.comment_fetcher(post_url, gallery_id, post_number, ci_t, page)
                profile = inspect_source_response(body, post_url, expected="comments")
                if profile.state == "blocked":
                    self._log(
                        job_id,
                        level="error",
                        step="comments",
                        message="댓글 차단 응답 감지 · 추가 요청 중단",
                        details={"url": post_url, "page": page, **profile.as_dict()},
                    )
                    raise RuntimeError(f"댓글 원본 차단 응답: {profile.reason}")
                return body
            except Exception as exc:
                if isinstance(exc, HTTPError) and 400 <= exc.code < 500:
                    self._log(
                        job_id,
                        level="error",
                        step="comments",
                        message="댓글 HTTP 접근 제한 응답 · 추가 요청 중단",
                        details={"url": post_url, "page": page, "status": exc.code, "error_type": type(exc).__name__},
                    )
                    raise
                if attempt >= request.max_retries or not is_retryable_error(exc):
                    raise
                wait = retry_delay(attempt)
                self._log(job_id, level="warning", step="comments", message=f"댓글 요청 재시도 대기 · {attempt + 1}/{request.max_retries}", details={"url": post_url, "page": page, "error_type": type(exc).__name__, "delay_seconds": wait})
                self.sleep(wait)
        raise RuntimeError("unreachable comment retry state")


def _request_from_job(job: dict[str, Any]) -> JobRequest:
    config = json.loads(job.get("config_json") or "{}")
    return JobRequest.from_dict({
        "gallery_id": job["gallery_id"],
        "subject": job["subject"],
        "subjects": config.get("subjects") or [],
        "since": job["since"],
        "until": job["until"],
        "cutoff_at": config.get("cutoff_at"),
        "buy_rate": job["buy_rate"],
        **config,
    })


def _date_in_range(value: str, since: str | None, until: str | None, cutoff_at: str | None = None) -> bool:
    if cutoff_at and not _at_or_before_cutoff(value, cutoff_at):
        return False
    if not value:
        return True
    value_date = value[:10]
    try:
        current = date.fromisoformat(value_date)
    except ValueError:
        return True
    if since and current < date.fromisoformat(since[:10]):
        return False
    if until and current > date.fromisoformat(until[:10]):
        return False
    return True


def _at_or_before_cutoff(value: str, cutoff_at: str) -> bool:
    if not value or not cutoff_at:
        return False
    try:
        cutoff = datetime.fromisoformat(cutoff_at.replace("Z", "+00:00"))
        posted = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if cutoff.tzinfo is None:
        return False
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=cutoff.tzinfo)
    return posted <= cutoff


def _is_before_date(value: str, boundary: str) -> bool:
    if not value or not boundary:
        return False
    try:
        return date.fromisoformat(value[:10]) < date.fromisoformat(boundary[:10])
    except ValueError:
        return False
