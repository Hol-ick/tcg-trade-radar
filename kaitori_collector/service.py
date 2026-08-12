"""Application service for asynchronous collection and review workflows."""
from __future__ import annotations

import json
import threading
import time
from datetime import date
from typing import Callable, Any
from urllib.parse import parse_qs, urljoin, urlparse

from . import __version__
from .browser_transport import BrowserTransportError
from .comments import parse_comments
from .contracts import JobRequest, ReviewAction, utc_now
from .html import DCInsideHTMLParser, parse_html, normalize_space
from .observability import inspect_source_response, is_retryable_error, retry_delay
from .parser import SourceResponseError, build_list_url, extract_comment_token, extract_post, fetch_comment_text_auto, fetch_text_auto
from .storage import Repository


Fetcher = Callable[[str], str]
CommentFetcher = Callable[[str, str, str, str, int], str]


class JobService:
    def __init__(self, repository: Repository, fetcher: Fetcher | None = None, sleep: Callable[[float], None] = time.sleep, catalog: list[Any] | None = None, comment_fetcher: CommentFetcher | None = None) -> None:
        self.repository = repository
        self.fetcher = fetcher or fetch_text_auto
        self.comment_fetcher = comment_fetcher or (lambda post_url, gallery_id, post_number, ci_t, page: fetch_comment_text_auto(post_url, gallery_id, post_number, ci_t, page))
        self.sleep = sleep
        self.catalog = catalog or []
        self._threads: dict[str, threading.Thread] = {}
        self._thread_lock = threading.Lock()

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
                "max_retries": request.max_retries,
            },
        )
        seen_urls: set[str] = set()
        posts_seen = 0
        try:
            for page in range(1, request.max_pages + 1):
                list_url = build_list_url(request.gallery_id, page, request.gallery_url)
                self._log(job_id, step="list", message=f"목록 요청 시작 · {page}페이지", details={"url": list_url})
                parser = DCInsideHTMLParser()
                list_html = self._fetch_with_retry(job_id, list_url, request, "list")
                profile = inspect_source_response(list_html, list_url, expected="list")
                self._log(job_id, step="list", message=f"목록 응답 판별 · {profile.state}", details=profile.as_dict())
                self._log(job_id, step="list", message=f"목록 응답 수신 · {len(list_html):,}자", details={"url": list_url, "characters": len(list_html)})
                parser.feed(list_html)
                all_rows = parser.list_rows
                candidates = [
                    urljoin(list_url, item["href"])
                    for item in all_rows
                    if normalize_space(item.get("subject", "")) in subjects and item.get("href")
                ]
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
                for post_url in candidates:
                    if post_url in seen_urls or posts_seen >= request.max_posts:
                        continue
                    seen_urls.add(post_url)
                    posts_seen += 1
                    self._log(job_id, step="post", message=f"게시글 요청 시작 · {posts_seen}/{request.max_posts}", details={"url": post_url})
                    post_html = self._fetch_with_retry(job_id, post_url, request, "post")
                    post_profile = inspect_source_response(post_html, post_url, expected="post")
                    self._log(job_id, step="post", message=f"게시글 응답 판별 · {post_profile.state}", details=post_profile.as_dict())
                    if post_profile.state in {"empty", "blocked"}:
                        raise RuntimeError(f"게시글 응답을 사용할 수 없습니다: {post_profile.reason}")
                    self._log(job_id, step="post", message=f"게시글 응답 수신 · {len(post_html):,}자", details={"url": post_url, "characters": len(post_html)})
                    document, _ = parse_html(post_html, post_url)
                    extracted_rows = extract_post(post_html, post_url, request.gallery_id, normalize_space(request.subject))
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
                    if not _date_in_range(document.get("posted_at", ""), request.since, request.until):
                        self._log(job_id, level="warning", step="parse", message="작성일 범위 밖이라 제외", details={"url": post_url, "posted_at": document.get("posted_at", "")})
                        continue
                    source_id, _ = self.repository.upsert_source({
                        "gallery_id": request.gallery_id,
                        "post_url": document["url"],
                        "title": document["title"],
                        "posted_at": document["posted_at"],
                        "author_name": document.get("author_name", ""),
                        "author_type": document.get("author_type", "unknown"),
                        "raw_html": post_html,
                        "keep_raw": request.keep_raw,
                    })
                    self.repository.attach_source_to_job(job_id, source_id)
                    comments_inserted = self._collect_comments(job_id, post_url, request.gallery_id, post_html, source_id, request)
                    inserted_rows = self.repository.insert_rows(job_id, source_id, extracted_rows)
                    self._log(job_id, step="store", message=f"원문·결과 저장 완료 · 신규 행 {inserted_rows}개 / 댓글 {comments_inserted}개", details={"url": post_url, "rows": len(extracted_rows), "inserted": inserted_rows, "comments": comments_inserted})
                    if self.catalog:
                        from .matcher import match_card

                        for row in self.repository.list_rows(job_id=job_id):
                            if row["source_id"] == source_id:
                                self.repository.apply_match(row["id"], match_card(row["card_name_raw"], row["rarity"], self.catalog))
                    if request.delay > 0:
                        self.sleep(request.delay)
                if posts_seen >= request.max_posts:
                    break
                if request.delay > 0:
                    self.sleep(request.delay)
            completed_at = utc_now()
            self.repository.update_job(job_id, state="completed", error_message="", finished_at=completed_at, last_success_at=completed_at)
            snapshot_count = self.repository.refresh_demand_snapshot(
                completed_at[:10], request.gallery_id, since=request.since, until=request.until
            )
            self._log(job_id, step="snapshot", message=f"카드 수요 스냅샷 갱신 · {snapshot_count}개", details={"game_id": request.gallery_id, "count": snapshot_count})
            status = self.get_job_status(job_id)
            self._log(job_id, step="done", message=f"작업 완료 · 게시글 {posts_seen}개 / 결과 {status['counts']['rows']}개", details={"counts": status["counts"]})
        except Exception as exc:
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
            item["buy_price_krw"] = round(item["price_krw"] * job["buy_rate"] / 100)
            item["listing_type"] = item.get("listing_type") or "unknown"
            item["price_type"] = item.get("price_type") or "unknown"
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

    def review_row(self, row_id: str, action: ReviewAction) -> dict[str, Any]:
        return self.repository.record_review(row_id, action)

    def export_results(self, job_id: str) -> list[dict[str, Any]]:
        rows = self.repository.export_approved_rows(job_id)
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        result = []
        for row in rows:
            item = dict(row)
            item.pop("raw_html", None)
            item["buy_price_krw"] = round(item["price_krw"] * job["buy_rate"] / 100)
            result.append(item)
        return result

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

    def _fetch_with_retry(self, job_id: str, url: str, request: JobRequest, step: str) -> str:
        for attempt in range(request.max_retries + 1):
            try:
                return self.fetcher(url)
            except Exception as exc:
                if isinstance(exc, (SourceResponseError, BrowserTransportError)):
                    self._log(
                        job_id,
                        level="error",
                        step=step,
                        message="원본 서버가 빈 응답을 반환해 수집을 중단",
                        details=exc.as_dict(),
                    )
                if attempt >= request.max_retries or not is_retryable_error(exc):
                    raise
                wait = retry_delay(attempt)
                self._log(job_id, level="warning", step=step, message=f"요청 재시도 대기 · {attempt + 1}/{request.max_retries}", details={"url": url, "error_type": type(exc).__name__, "delay_seconds": wait})
                self.sleep(wait)
        raise RuntimeError("unreachable fetch retry state")

    def _collect_comments(self, job_id: str, post_url: str, gallery_id: str, post_html: str, source_id: str, request: JobRequest) -> int:
        ci_t = extract_comment_token(post_html)
        post_number = parse_qs(urlparse(post_url).query).get("no", [""])[0]
        if not ci_t or not post_number:
            self._log(job_id, level="warning", step="comments", message="댓글 조회 토큰 또는 게시글 번호 없음", details={"url": post_url})
            return 0
        total_inserted = 0
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
                return self.comment_fetcher(post_url, gallery_id, post_number, ci_t, page)
            except Exception as exc:
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
        "buy_rate": job["buy_rate"],
        **config,
    })


def _date_in_range(value: str, since: str | None, until: str | None) -> bool:
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
