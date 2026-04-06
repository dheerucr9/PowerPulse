# Solar Real-Time Dashboard Context (2026-03-30)

**Repo:** /Users/dheeraj/Documents/snaird_v2/by-the-power-of-ai/s_power  
**Stack:** FastAPI backend, worker poller, React frontend bundled with esbuild (frontend/src/main.jsx -> static/dist/bundle.js served by FastAPI).

## Frontend
- Live tab: animated sun -> house vertical line; house <-> grid horizontal band with directional arrow; house illustration removed. Bottom strip shows up to 13 panel chips with hover tooltip and low/fault warning badge.
- History tab: Chart.js via unified `/series`; axes labeled "Time" (x) and "Power (kW)" (y).
- Frontend is served from bundled `static/dist/index.html` (root-level `solar_dashboard.html` removed as legacy).

## Backend API (`backend/main.py`)
- Serves built assets from `/static` (dist).
- Endpoints: `/devices` (gateway proxy), `/series` (house + panel; optional `panel_id`; intervals raw/5m/1h), `/house_series` (shim calling `/series`), `/latest`.
- Env vars: `GATEWAY_IP/USER/PASS`, `DB_PATH`, `TZ`, `GATEWAY_TIMEOUT`, etc.

## Poller (`backend/poller.py`)
- Polls gateway during solar window (lat/long, TZ, buffer) every `POLL_SECONDS` (default 60).
- Stores `samples_raw` (panel-level) and `house_raw` (site).
- Consumption derived: if gateway consumption is negative (export), add to production and clamp to >= 0.
- Net fix: `net_kw = production_kw - derived_consumption`.
- Retries using requests + urllib3 Retry; TLS verify disabled.

## Docker
- `Dockerfile` builds frontend (node 18, `npm ci`, esbuild) then backend API + embedded poller (python:3.11-slim).
- `docker-compose.yml` mounts `./data` to `/data`, exposes port 8000, env via `.env` (git-ignored).
- `.dockerignore` excludes `frontend/node_modules`, `dist`, `.env`, `data`.

## Data
- SQLite at `data/solar.db`; tables `samples_raw`, `house_raw`.
- Net backfill (if needed):  
  `UPDATE house_raw SET net_kw = production_kw - consumption_kw WHERE production_kw IS NOT NULL AND consumption_kw IS NOT NULL;`

## Usage
- From repo root: `docker compose up --build` (or `build --no-cache`, `up --force-recreate`).
- Frontend build served via API image; `static/` intentionally empty.
