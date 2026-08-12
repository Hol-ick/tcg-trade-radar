# TCG Trade Radar Web UI

The web surface is a local React/Vite app built with shadcn/ui components. It talks to the existing Python worker; it does not replace the collector or its SQLite audit trail.

## Run locally

From the repository root, start the worker:

```powershell
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3 --data-root data
```

In another terminal, start the UI:

```powershell
pnpm --dir web install
pnpm --dir web dev --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. Vite proxies `/api/*` to the local worker at `127.0.0.1:8787`.

The development probe is available at `http://127.0.0.1:5173/dev` and is also published as a static GitHub Pages preview when the `Deploy web preview` workflow completes. The hosted preview is UI-only; live collection requires a worker endpoint configured with `VITE_WORKER_URL` and must not expose a local SQLite worker directly to the public internet.

## What the UI verifies

- The worker health endpoint and version.
- A bounded public-read collection job for one of the five gallery presets.
- Live job state, counts, structured logs, response-shape diagnostics, and extracted rows.
- Empty results and `structure_changed`/blocked responses as visible evidence instead of silently treating them as success.

The UI stores no API token. If the worker is started with `--api-token`, enter the token for the current browser session.

## Checks

```powershell
pnpm --dir web build
pnpm --dir web lint
python D:\CodexHome\skills\webapp-testing\scripts\with_server.py --server "python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\web-ui-smoke.sqlite3 --data-root data" --port 8787 --server "pnpm --dir web dev --host 127.0.0.1 --port 5173" --port 5173 -- python scripts\run_web_smoke.py
```
