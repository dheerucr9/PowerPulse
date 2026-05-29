# PowerPulse - Real-Time Home Energy Monitoring

**Repo:** https://github.com/dheerucr9/PowerPulse
**Stack:** FastAPI backend, APScheduler worker poller, React frontend with Vite, ECharts for visualizations, PostgreSQL + TimescaleDB.

**Last Updated:** 2026-04-06

---

## Overview

PowerPulse is a self-contained Docker stack for monitoring home energy systems. It polls solar gateways and EV chargers in real-time, stores telemetry in TimescaleDB, and exposes a modern dashboard + REST API.

---

## Features

- **Solar Monitoring** - Per-panel power output, voltage, current, temperature
- **Consumption Tracking** - Household energy usage in real-time
- **Grid Flow** - Net energy flow (import/export) visualization
- **EV Charging** - Tesla Wall Connector integration
- **Alerts** - Configurable anomaly detection
- **Dark/Light Mode** - Dashboard theme toggle
- **Historical Charts** - Interactive ECharts with line & bar views

---

## Frontend (`frontend/`)

### Tech Stack
- React 18 + TypeScript
- Vite for bundling
- TanStack Query for data fetching
- ECharts for visualizations
- Custom CSS with design tokens

### Key Components
- `App.tsx` - Main dashboard layout
- `LiveFlow.tsx` - Real-time energy flow visualization (Solar → Home → Grid → Tesla)
- `StatCard.tsx` / `ChargerStatCard.tsx` - Metric cards
- `PowerHistoryChart.tsx` - Line and bar chart with ECharts
- `HistoryFilters.tsx` - Time range presets (relative + absolute)
- `AlertsPanel.tsx` - Alert management sidebar
- `DashboardHeader.tsx` - Header with theme toggle

### Features
- Dark/light mode with system preference detection
- Responsive design
- Live polling every 20s (TanStack Query)
- Staggered entrance animations

---

## Backend (`backend/`)

### Tech Stack
- FastAPI with Pydantic schemas
- PostgreSQL + TimescaleDB (hypertable for time-series)
- APScheduler for polling jobs
- Alembic for migrations

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/latest` | GET | Latest solar snapshot |
| `/series` | GET | Time series data (paginated, cursor-based) |
| `/house_series` | GET | House-level time series |
| `/charger/latest` | GET | Tesla Wall Connector latest status |
| `/charger/history` | GET | Tesla Wall Connector history |
| `/api/alerts` | GET/POST | Alert management |
| `/api/intelligence/summary` | GET | Intelligence insights |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

### Database Tables

| Table | Description |
|-------|-------------|
| `site_power_samples` | Site-level telemetry (production, consumption, net) |
| `panel_power_samples` | Per-panel telemetry |
| `charger_samples` | Tesla Wall Connector samples |
| `alerts` | Alert records |
| `alert_acknowledgements` | Acknowledgment tracking |
| `anomalies` | Detected anomalies |
| `site_panels` | Panel registry |

### Poller (`poller.py` / `worker_entry.py`)

- Solar polling: Every `POLL_SECONDS` (default 60s)
- Charger polling: Every `WALL_CONNECTOR_POLL_SECONDS` (default 60s)
- Intelligence runs every `INTELLIGENCE_SECONDS` (default 300s)

---

## Environment Variables

### Gateway (Required)
- `GATEWAY_IP` - Solar gateway IP
- `GATEWAY_USER` - SunPower/SunStrong local PVS gateway auth username
- `GATEWAY_PASS` - SunPower/SunStrong local PVS gateway auth password
- `GATEWAY_TIMEOUT` - Request timeout (default 20s)

Gateway auth flow: `GET https://<GATEWAY_IP>/auth?login` with HTTP Basic Auth, then reuse the returned session/cookie for `https://<GATEWAY_IP>/cgi-bin/dl_cgi/devices/list`. Keep actual gateway credentials in `.env` only; do not commit them.

### Location (Required)
- `LATITUDE` / `LONGITUDE` - For day/night rendering
- `TZ` - Timezone (e.g., `America/Los_Angeles`)

### Tesla Wall Connector (Optional)
- `WALL_CONNECTOR_IP` - Wall Connector IP
- `WALL_CONNECTOR_POLL_SECONDS` - Poll interval

### Database
- `DATABASE_DSN` - PostgreSQL connection string
- `POSTGRES_DB/USER/PASSWORD/HOST/PORT`

### Network
- `HOST_BIND_IP` - Bind IP (default 127.0.0.1)
- `FRONTEND_API_ORIGIN` - For CORS

---

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI + dashboard |
| `worker` | 9101 | Poller + intelligence jobs |
| `db` | 5432 | PostgreSQL + TimescaleDB |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3001 | Dashboards (optional) |

---

## Running

```bash
# Setup
cp .env.example .env
# Edit .env with your settings

# Build and run
docker compose up --build -d

# Apply migrations
docker compose exec api alembic upgrade head

# View logs
docker compose logs -f
```

---

## Development

```bash
# Frontend
cd frontend
npm install
npm run dev  # Vite dev server

# Backend
cd backend
# Run tests
pytest

# Apply migrations
alembic upgrade head
```

---

## File Structure

```
s_power/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── poller.py            # Gateway polling
│   ├── worker_entry.py      # APScheduler jobs
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── settings.py         # Environment config
│   ├── db.py                # Database connection
│   ├── repositories/        # Data access layer
│   │   ├── charger.py
│   │   ├── telemetry.py
│   │   └── alerts.py
│   ├── services/            # Business logic
│   ├── jobs/                # Intelligence jobs
│   └── observability/       # Health, metrics, logging
├── frontend/
│   ├── src/
│   │   ├── app/            # App.tsx, providers
│   │   ├── components/     # React components
│   │   │   ├── dashboard/ # LiveFlow, StatCard, etc.
│   │   │   ├── charts/     # ECharts
│   │   │   └── alerts/      # Alert components
│   │   ├── features/       # TanStack Query hooks
│   │   │   ├── live/
│   │   │   ├── history/
│   │   │   ├── charger/
│   │   │   └── alerts/
│   │   ├── styles/         # CSS tokens + base
│   │   └── hooks/          # useTheme
│   └── index.html
├── docker-compose.yml
├── Dockerfile
├── alembic/                 # Database migrations
├── ops/                     # Backup/restore scripts
└── README.md
```

---

## Key Patterns

### Data Fetching
- TanStack Query with 20s polling for live data
- 30s polling for charger data
- Manual refresh available

### Theme
- Uses `data-theme="dark"` on `<html>`
- CSS custom properties for colors
- Persisted to localStorage
- System preference detection

### Charts
- ECharts with custom styling
- Line chart: Power (kW) over time
- Bar chart: Energy (kWh) by day/week/month
- Net shown as dashed line overlay

---

## Extensibility

Future additions planned:
- Battery storage monitoring
- Smart home device integration
- Weather correlation
- Cost tracking
- Multiple home support
- Home Assistant integration
