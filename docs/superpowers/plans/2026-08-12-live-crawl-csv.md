# Live Crawl and CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Make the live DCInside crawl tolerate transient unrecognized list responses, then expose and verify a usable CSV export from the Dev page.

**Architecture:** Keep the Python worker as the source of truth. The transport layer will reject an unrecognized desktop document and continue through the existing mobile/browser read-only fallbacks; the worker will expose a non-mutating CSV endpoint for all extracted rows; the React Dev page will download that endpoint after a completed job.

**Tech Stack:** Python 3.11+, stdlib `urllib`/`csv`/`http.server`, SQLite worker API, Vite, React, TypeScript, shadcn/ui components.

## Global Constraints

- Preserve public-read-only collection boundaries; do not add CAPTCHA bypass, login, posting, commenting, or trading automation.
- Preserve existing job/result API fields and review states.
- Never treat an unrecognized source response as an empty successful crawl.
- CSV export must not mutate review status or expose stored raw HTML.
- Verify with a failing regression test, the full Python suite, web lint/build, a live worker job, and a readable CSV artifact.

---

### Task 1: Reject invalid desktop responses and use the fallback transport

**Files:**
- Modify: `kaitori_collector/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- `fetch_text_auto(url, timeout, user_agent)` continues to return a source document string or raise `SourceResponseError`.
- An HTML document without the expected list/post markers is treated as a fallback candidate, not a successful source response.

- [ ] Add a regression test where desktop returns an HTML challenge with no expected source markers and mobile returns valid list markup.
- [ ] Run the focused test and confirm it fails because the desktop response is returned unchanged.
- [ ] Change `fetch_text_auto` to validate desktop shape before returning, record the shape as a fallback error, and try mobile then browser.
- [ ] Run the focused test and confirm it passes.

### Task 2: Add non-mutating CSV export to the worker and Dev page

**Files:**
- Modify: `kaitori_collector/service.py`
- Modify: `kaitori_collector/api.py`
- Modify: `kaitori_collector/server.py`
- Modify: `kaitori_collector/contracts.py` only if the public row shape requires a type adjustment
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/components/result-table.tsx`
- Modify: `web/src/dev-page.tsx`
- Test: `tests/test_api.py`

**Interfaces:**
- `GET /jobs/{job_id}/csv` returns `text/csv; charset=utf-8` for all rows belonging to the job without changing row status.
- `downloadJobCsv(jobId, token)` downloads the CSV response in the browser.

- [ ] Add an API regression test proving the endpoint returns a header and row and leaves the result status unchanged.
- [ ] Implement CSV serialization from public result fields without `raw_html`.
- [ ] Make the HTTP server write text responses as raw UTF-8 instead of JSON-quoting them.
- [ ] Add a visible CSV download action to the result card when a job has rows.
- [ ] Run the focused API test and web lint/build.

### Task 3: Run the live crawl and deliver the CSV artifact

**Files:**
- Create: `data/tcggame-live-20260812.csv` (generated evidence artifact, ignored by Git)
- Modify: `README.md` with the verified worker + CSV command
- Modify: AI_HUB `01_Projects/TCG_Trade_Radar/PROJECT_STATUS.md` and a worklog entry

- [ ] Start the worker with a fresh audit database and run a bounded `tcggame` job through the Dev page.
- [ ] Confirm the job completes, the logs show a valid list response and post parsing, and the result count is greater than zero.
- [ ] Export the same job to CSV and verify UTF-8 CSV headers, row count, and no raw HTML column.
- [ ] Run the full Python tests, compile check, web lint, web build, and `git diff --check`.
- [ ] Record exact evidence and unresolved source limitations in AI_HUB, then commit and push verified source changes and the plan/docs only; keep generated SQLite/CSV artifacts ignored unless explicitly requested for versioning.
