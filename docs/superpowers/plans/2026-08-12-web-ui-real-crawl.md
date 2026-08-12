# TCG Trade Radar Web UI and Real Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task with verification checkpoints.

**Goal:** Add a local React web UI that starts and monitors the existing collector jobs, displays diagnostics and results, and verifies whether the current DCInside collection path works in the live environment.

**Architecture:** Keep the Python collector API and SQLite worker as the source of truth. Add an isolated `web/` Vite + React + TypeScript app using locally owned shadcn/ui components, with a development proxy to `http://127.0.0.1:8787`. The UI submits bounded public-read jobs, polls job state/logs/results, and keeps live-source failures visible instead of translating them into “no posts.”

**Tech Stack:** Python worker API, Vite, React, TypeScript, shadcn/ui components, CSS variables, Playwright.

## Global Constraints

- Use `ui.shadcn.com` official installation and component patterns; do not runtime-embed or CDN-load UI markup.
- Preserve the existing Python/SQLite API contract and public-read-only collection boundaries.
- Do not add login, CAPTCHA bypass, posting, commenting, DM, or automated trading behavior.
- Keep API tokens in memory-only UI state; never commit `.env` or credential values.
- Show `empty`, `blocked`, `structure_changed`, and transport fallback diagnostics distinctly from confirmed “no posts.”
- Use the existing bounded limits: `max_posts` 1–200, `max_pages` 1–20, delay >= 0, and the current collector’s retry limits.

---

### Task 1: Scaffold the isolated web application

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/index.css`
- Create: `web/components.json`

**Interfaces:**
- Consumes: existing worker API at `/health`, `/jobs`, `/jobs/:id`, `/jobs/:id/logs`, `/jobs/:id/results`.
- Produces: `npm run dev` on port 5173 and `npm run build` output for the web surface.

- [ ] Confirm Node/npm/pnpm versions and run the official shadcn CLI help before initialization.
- [ ] Initialize the Vite React TypeScript app without overwriting Python collector files.
- [ ] Configure a development proxy for `/api` or a single worker base URL so local UI requests do not require hard-coded production URLs.
- [ ] Add the minimum shadcn/ui primitives required by the page: Button, Card, Badge, Input, Select, Tabs, Progress, ScrollArea, and Table or equivalent local components.
- [ ] Run `pnpm build` or the repository-selected package-manager build and record the output.

### Task 2: Build the collector control surface

**Files:**
- Create: `web/src/lib/api.ts`
- Create: `web/src/lib/types.ts`
- Create: `web/src/components/collector-form.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**
- `createJob(payload: JobRequest): Promise<{ job_id: string; id: string }>`
- `getHealth(): Promise<{ version: string }>`
- `getJob(jobId: string): Promise<JobStatus>`
- `getLogs(jobId: string): Promise<{ logs: JobLog[] }>`
- `getResults(jobId: string): Promise<{ rows: ExtractedRow[] }>`

- [ ] Add five gallery presets with explicit gallery IDs and readable labels.
- [ ] Add bounded controls for gallery, subject, post limit, page limit, delay, buy-rate, and optional token.
- [ ] Disable duplicate submissions while a job is active and show the worker connection state.
- [ ] Use a stable API client that handles non-JSON errors, 401, 404, timeout, and connection failures with actionable text.
- [ ] Keep the user’s token out of URLs, logs, and local storage.

### Task 3: Build diagnostics, live job progress, and result review

**Files:**
- Create: `web/src/components/job-status.tsx`
- Create: `web/src/components/job-logs.tsx`
- Create: `web/src/components/result-table.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**
- `useJobPolling(jobId: string | null): { job: JobStatus | null; logs: JobLog[]; rows: ExtractedRow[]; error: string | null }`

- [ ] Poll job state at a bounded interval and stop on `completed` or `failed`.
- [ ] Show source, row, review, and error counts using badges and progress rather than decorative percentages.
- [ ] Render structured log details such as URL, status, content length, transport, fallback, and structure state.
- [ ] Render results with listing type, card name, price, quantity, review state, and original post link.
- [ ] Preserve `needs_review` and source diagnostics as visible states; never collapse them into a generic empty state.
- [ ] Add a responsive layout with visible keyboard focus and reduced-motion behavior.

### Task 4: Verify the live crawl path

**Files:**
- Create: `web/tests/collector-web.spec.ts`
- Create: `scripts/run_web_smoke.py`
- Modify: `README.md`

- [ ] Run the worker in a temporary audit database and launch the Vite dev server.
- [ ] Use Playwright to verify health, select a gallery, submit a bounded job, observe polling, and inspect final logs/results.
- [ ] Run a real public-read `tcggame` sample with a small limit and capture the exact final state: completed rows, or a structured transport/block/empty result.
- [ ] Run the existing 49 Python tests and the web production build after UI changes.
- [ ] Update README with exact local startup commands and the evidence boundary for live crawling.
- [ ] Record the result in AI_HUB with changed paths, commit, verification commands, and unresolved source limitations.

### Task 5: Review and deliver

- [ ] Run `git diff --check` and inspect only session-owned paths.
- [ ] Capture a local screenshot or Playwright DOM evidence for the main flow.
- [ ] Commit and push verified project files to `origin/main` under the standing repository policy.
- [ ] Render and index the AI_HUB journal, then report the live crawl result separately from UI/build verification.
