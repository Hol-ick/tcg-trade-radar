# Workerless Weekly Collection Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Replace the worker-dependent dark console with a compact light collection console that selects seven-day windows, displays saved crawl results, and runs a one-shot weekly collector through GitHub Actions instead of a long-running worker API.

**Architecture:** The hosted React app is read-only and loads versioned weekly snapshots from `web/public/data/weeks/<since>.json`; it never polls or calls a worker. A scheduled/manual GitHub Actions job runs the existing Python collector as a one-shot process, converts its SQLite rows into a public snapshot plus CSV, and commits only generated weekly artifacts. Previous/next buttons move exactly seven calendar days and the app keeps the selected window in the URL.

**Tech Stack:** React 19, Vite, TypeScript, Outfit, flat CSS, Python collector service, SQLite, GitHub Actions, Playwright browser verification.

## Global Constraints

- No long-running worker server, worker URL, API token, job polling, or worker status copy may remain in the web UI.
- The only collection window is an inclusive seven-day range: `since` through `until`.
- Previous/next controls move exactly seven days; the next control cannot select a future window.
- Use the attached flat print-inspired design: white canvas, blue primary, emerald secondary, amber accent, sharp borders, no gradients, shadows, blur, hero copy, or decorative explanation sections.
- Preserve existing crawler and raw audit data; do not delete existing SQLite/CSV artifacts.
- Verify the live site, the local build, the weekly range controls, snapshot loading, and the one-shot collection workflow before claiming completion.

---

### Task 1: Capture the current failure boundary

**Files:**
- Inspect: `web/src/lib/api.ts`, `web/src/hooks/use-job-polling.ts`, `kaitori_collector/server.py`, `kaitori_collector/service.py`
- Create: `artifacts/workerless-diagnosis.json`

**Interfaces:**
- Produces a recorded distinction between browser-to-worker failure and crawler/source failure for the implementation tasks.

- [ ] **Step 1: Reproduce the hosted browser request**

  Load the public page and record the request/error shown by the browser. Verify whether a static GitHub Pages page has any worker endpoint to call.

- [ ] **Step 2: Exercise the existing one-shot collector locally**

  Run one bounded gallery collection with `python -m kaitori_collector --gallery-id tcg --pages 1 --max-posts 1 --format json --output artifacts/diagnosis.json` or the repository-equivalent command, and record its exit code and response.

- [ ] **Step 3: Save evidence**

  Write the observed endpoint, HTTP result, crawler result, and conclusion to `artifacts/workerless-diagnosis.json`; do not change application code until this evidence identifies the boundary.

### Task 2: Add date-window and snapshot contracts

**Files:**
- Create: `web/src/lib/week-range.ts`
- Create: `web/src/lib/snapshot.ts`
- Modify: `web/src/lib/types.ts`
- Test: `web/src/lib/week-range.test.ts`

**Interfaces:**
- `week-range.ts` exports `WEEK_DAYS = 7`, `WeekRange`, `getCurrentWeekRange(today)`, `shiftWeek(range, direction)`, `formatRange(range)`, and `toDateKey(date)`.
- `snapshot.ts` exports `loadWeekSnapshot(range)` and `downloadSnapshotCsv(snapshot)`.
- Snapshot rows reuse the public `ExtractedRow` shape; snapshot metadata contains `since`, `until`, `generated_at`, `gallery_id`, `row_count`, `review_count`, and `rows`.

- [ ] **Step 1: Write failing date-range tests**

  Cover Monday-based seven-day ranges, exact `-7/+7` shifts, future-window clamping, and stable `YYYY-MM-DD` formatting.

- [ ] **Step 2: Run the focused test**

  Run `pnpm --dir web exec vitest run src/lib/week-range.test.ts` and confirm it fails because the contract is not implemented.

- [ ] **Step 3: Implement pure date helpers**

  Use local calendar dates only; do not use timezone-sensitive `Date.parse` for date-only keys.

- [ ] **Step 4: Implement snapshot loading**

  Resolve `import.meta.env.BASE_URL`, fetch `/data/weeks/<since>.json`, validate required metadata, and return a typed empty state for a missing snapshot while surfacing network/JSON errors as user-readable status.

- [ ] **Step 5: Run focused tests and typecheck**

  Run `pnpm --dir web exec vitest run src/lib/week-range.test.ts` and `pnpm --dir web typecheck`; both must exit 0.

### Task 3: Replace the worker UI with the functional weekly console

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/dev-page.tsx`
- Modify: `web/src/index.css`
- Modify: `web/src/components/result-table.tsx`
- Remove from active imports: `web/src/components/collector-form.tsx`, `web/src/components/job-status.tsx`, `web/src/components/job-logs.tsx`, `web/src/hooks/use-job-polling.ts`, `web/src/lib/api.ts`

**Interfaces:**
- The app renders only source selector, seven-day range controls, collection-state summary, result table, CSV download, and the GitHub Actions collection link.
- `?since=YYYY-MM-DD` selects a range; `이전 주`, `다음 주`, and `이번 주` update it without page reload.
- Missing snapshots render an explicit “수집 데이터 없음” state; they do not show a fake success, worker error, or raw HTML.

- [ ] **Step 1: Add the weekly control behavior**

  Initialize from `?since`, clamp to the current week, load the selected snapshot, update the URL with `history.replaceState`, and make the next-week control disabled at the current week.

- [ ] **Step 2: Replace the page structure**

  Remove hero/field-note/status prose and worker controls. Keep one header, one control bar, one summary strip, one results panel, and one small collection link.

- [ ] **Step 3: Apply the attached visual system**

  Use a white background, `#111827` text, `#3B82F6` primary, `#10B981` success, `#F59E0B` accent, `#F3F4F6` muted fill, `#E5E7EB` borders, Outfit typography, 6–8px radii, 2px input borders, no shadows/gradients/blur, and responsive table behavior.

- [ ] **Step 4: Add accessible states**

  Every control has a label or accessible name; loading, empty, error, and row-count states are visible without relying on color alone; external collection link opens the repository workflow in a new tab with `rel="noreferrer"`.

- [ ] **Step 5: Run lint, typecheck, and build**

  Run `pnpm --dir web lint`, `pnpm --dir web typecheck`, and `pnpm --dir web build`; resolve all errors before continuing.

### Task 4: Make weekly collection a one-shot GitHub Actions job

**Files:**
- Create: `scripts/export_week_snapshot.py`
- Create: `.github/workflows/collect-week.yml`
- Modify: `README.md`

**Interfaces:**
- `scripts/export_week_snapshot.py --since YYYY-MM-DD --until YYYY-MM-DD --gallery-id tcg` runs the existing service in-process, filters rows to the requested inclusive range, and writes `web/public/data/weeks/<since>.json` and `<since>.csv`.
- The workflow supports `workflow_dispatch` inputs `since`, `until`, `gallery_id` and a weekly schedule; it installs Python/Playwright dependencies, runs the script, and commits only the generated snapshot files.

- [ ] **Step 1: Write exporter tests**

  Test date validation, deterministic snapshot paths, CSV headers, row counts, and the empty-result shape using a temporary SQLite repository or fixture data.

- [ ] **Step 2: Implement exporter**

  Reuse `JobRequest`, `JobService`, and `Repository`; do not launch `--serve` and do not add another HTTP server. Serialize only public rows and summary metadata.

- [ ] **Step 3: Add the workflow**

  Configure `permissions: contents: write`, install the repository requirements, run the bounded exporter, and commit with a bot identity only when generated files change.

- [ ] **Step 4: Document the workflow**

  Explain that the web page reads committed weekly snapshots and that “주간 수집 실행” opens the manual workflow; document the exact inclusive date convention and generated file paths.

- [ ] **Step 5: Run exporter tests and a bounded live export**

  Execute the test suite and one current seven-day export, then inspect the JSON/CSV row counts and URLs for non-empty valid output. Preserve prior artifacts.

### Task 5: Browser verification and deployment checks

**Files:**
- Modify: `scripts/run_web_smoke.py`
- Create: `artifacts/weekly-console-verification.json`

**Interfaces:**
- Smoke test covers the default page, previous/next/current week controls, missing snapshot state, CSV download, and absence of worker copy/polling.

- [ ] **Step 1: Update the Playwright smoke flow**

  Assert the exact weekly range changes by seven days, `다음 주` disables at the current week, and the result table/empty state changes with the selected snapshot.

- [ ] **Step 2: Run the local browser test**

  Start Vite, run `python scripts/run_web_smoke.py --no-crawl`, inspect the screenshot, and save the observed control labels/counts to the verification artifact.

- [ ] **Step 3: Run the production build preview**

  Serve `web/dist`, repeat the browser flow, and verify `BASE_URL` snapshot paths resolve under `/tcg-trade-radar/`.

- [ ] **Step 4: Check the public Pages URL**

  Open `https://hol-ick.github.io/tcg-trade-radar/`, confirm the light functional UI loads, and verify it no longer requests `/api` or displays worker status.

- [ ] **Step 5: Run final verification**

  Run the full relevant commands: Python tests, `pnpm --dir web lint`, `pnpm --dir web typecheck`, `pnpm --dir web build`, and the browser smoke test. Report exact pass/fail evidence and any external GitHub Actions limitation separately.
