# PowerPulse

Real-time home energy monitoring

A self-contained Docker stack for monitoring home energy systems including solar panels, home consumption, grid flow, EV charging, and more.

## Overview

PowerPulse polls your solar gateway and EV charger in real-time, stores telemetry in TimescaleDB, and exposes a modern dashboard + REST API. Perfect for homeowners who want visibility into their energy production, consumption, and EV charging patterns.

## Features

- **Solar Monitoring** — Track per-panel power output, voltage, current, and temperature
- **Consumption Tracking** — Monitor household energy usage in real-time
- **Grid Flow** — See net energy flow (import/export) at a glance
- **EV Charging** — Tesla Wall Connector integration for charging session monitoring
- **Alerts** — Configurable alerts for anomalies (panel offline, charging anomalies, etc.)
- **Dark Mode** — Dashboard supports dark/light themes
- **Historical Charts** — Interactive ECharts visualizations with time-series data
- **Extensible** — Ready for battery storage, smart home integrations, and more

## Prerequisites

- Docker + Docker Compose
- Solar gateway reachable on your LAN
- (Optional) Tesla Wall Connector on your network

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your settings (see Configuration below)

# 3. Build and start the stack
docker compose up --build -d

# 4. Confirm all services are healthy
docker compose ps

# 5. Apply database migrations (required before API operations)
docker compose exec api alembic upgrade head
```

## Configuration

Copy `.env.example` to `.env` and configure these variables:

### Gateway (Required)
| Variable | Description | Example |
|----------|-------------|---------|
| `GATEWAY_IP` | IP address of your solar gateway | `192.168.1.100` |
| `GATEWAY_USER` | SunPower/SunStrong gateway auth username | `<gateway-user>` |
| `GATEWAY_PASS` | SunPower/SunStrong gateway auth password | `<gateway-password>` |
| `GATEWAY_TIMEOUT` | Request timeout in seconds (default: 20) | `20` |
| `POLL_SECONDS` | Polling interval (default: 60) | `60` |

PowerPulse authenticates to the gateway with `GET https://<GATEWAY_IP>/auth?login`, then reads telemetry from `https://<GATEWAY_IP>/cgi-bin/dl_cgi/devices/list`. Use the credentials assigned to the local PVS gateway itself, not the PowerPulse dashboard, database, Grafana, or router credentials. Keep the real values only in `.env`; `.env` is gitignored.

To verify credentials manually:

```bash
curl -k -c /tmp/pvs.cookies --basic -u "<gateway-user>:<gateway-password>" "https://<GATEWAY_IP>/auth?login"
curl -k -b /tmp/pvs.cookies "https://<GATEWAY_IP>/cgi-bin/dl_cgi/devices/list"
```

### Location (Required)
| Variable | Description | Example |
|----------|-------------|---------|
| `LATITUDE` | Your latitude | `37.7749` |
| `LONGITUDE` | Your longitude | `-122.4194` |
| `TZ` | Timezone | `America/Los_Angeles` |
| `SUN_BUFFER_MINUTES` | Minutes before/after sunset for dark mode (default: 25) | `25` |

### Tesla Wall Connector (Optional)
| Variable | Description | Example |
|----------|-------------|---------|
| `WALL_CONNECTOR_IP` | IP address of Tesla Wall Connector | `CHANGE_ME_IP` |
| `WALL_CONNECTOR_POLL_SECONDS` | Charging data poll interval (default: 60) | `60` |

### Network
| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_BIND_IP` | `127.0.0.1` | IP to bind services. Set to LAN IP for network access |

### Database
| Variable | Default |
|----------|---------|
| `POSTGRES_DB` | `solar` |
| `POSTGRES_USER` | `solar` |
| `POSTGRES_PASSWORD` | `solar` |
| `POSTGRES_HOST` | `db` |
| `POSTGRES_PORT` | `5432` |

### Backup Settings
| Variable | Default |
|----------|---------|
| `BACKUP_DIR` | `/backups` |
| `BACKUP_RETENTION_DAYS` | `7` |

## Access

After startup, the dashboard is available at:

```
http://<HOST_BIND_IP>:8000
```

- Default binding: `127.0.0.1` (local only)
- For LAN access: set `HOST_BIND_IP` to your machine's LAN IP in `.env`

**Security Note:** Do not expose ports directly to the internet. Use VPN for remote access.

### Service Ports
| Service | Port | Path |
|---------|------|------|
| API + Dashboard | 8000 | `/` |
| Prometheus | 9090 | `/` |
| Grafana | 3001 | `/` |

## API

The REST API provides programmatic access to all telemetry data.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/latest` | Latest per-panel snapshot + total production |
| GET | `/charger/latest` | Latest EV charging session data |
| GET | `/charger/history` | Historical charging sessions |
| GET | `/series` | Panel time series (paginated) |
| GET | `/house_series` | House consumption/production series |
| GET | `/devices` | Available devices (panels, charger) |
| GET | `/config` | Current configuration |
| GET | `/api/alerts` | List alerts (supports `status` filter) |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge an alert |
| GET | `/api/intelligence/summary` | AI-generated energy insights |
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness check (includes DB + ingest freshness) |
| GET | `/metrics` | Prometheus metrics |

### API Examples

```bash
# Get latest solar data
curl http://127.0.0.1:8000/latest

# Get latest charger data
curl http://127.0.0.1:8000/charger/latest

# Get charger history
curl "http://127.0.0.1:8000/charger/history?from=1711862400&to=1711948800"

# Get house consumption series
curl "http://127.0.0.1:8000/house_series?from=1711862400&to=1711948800&interval=raw"

# Get open alerts
curl "http://127.0.0.1:8000/api/alerts?status=open"

# Check system readiness
curl http://127.0.0.1:8000/health/ready
```

### Pagination

Series endpoints (`/series`, `/house_series`, `/charger/history`) support cursor-based pagination:

```bash
# Page 1
curl "http://127.0.0.1:8000/house_series?from=1711862400&to=1711948800&interval=raw&limit=500"

# Page 2 (use next_cursor from page 1)
curl "http://127.0.0.1:8000/house_series?from=1711862400&to=1711948800&interval=raw&limit=500&cursor=<next_cursor>"
```

Response includes `page_info` with `has_more`, `next_cursor`, `returned`, and `limit`.

## Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** React + ECharts
- **Database:** PostgreSQL + TimescaleDB
- **Monitoring:** Prometheus + Grafana

## Extensibility

PowerPulse is designed to grow with your energy setup:

- **Battery Storage** — Add battery monitoring (Tesla Powerwall, Franklin WH, etc.)
- **Smart Home** — Integrate with Home Assistant, SmartThings
- **Additional Chargers** — Support for multiple EV chargers
- **Predictive Analytics** — ML-based consumption forecasting

## Backup & Restore

```bash
# Create a backup
./ops/backup.sh

# List backups
ls -lh ./backups/

# Restore latest backup
./ops/restore.sh latest

# Restore specific backup
./ops/restore.sh ./backups/powerpulse_20260406_120000.dump
```

## Upgrade

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose up --build -d

# Apply migrations
docker compose exec api alembic upgrade head

# Verify health
docker compose ps
curl -sf http://127.0.0.1:8000/health/ready
```

## License

MIT
