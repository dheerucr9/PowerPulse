# PowerPulse MCP Server

MCP wrapper for the PowerPulse backend API.

## What it exposes

### Health
- `health` - Basic health check
- `health_live` - Process liveness
- `health_ready` - Readiness (DB, migrations, ingest freshness)

### Live Data
- `latest` - Latest per-panel snapshot and totals
- `live` - Current live state (production, consumption)

### Tesla Wall Connector
- `charger_latest` - Latest charging status
- `charger_history` - Charging history (paginated)

### Time Series
- `series` - Panel-level time series (paginated)
- `house_series` - House-level time series (production, consumption, net)

### Devices
- `devices` - Gateway devices list

### Alerts
- `alerts` - List alerts with filtering (status, severity, kind)
- `alert_detail` - Alert details
- `acknowledge_alert` - Acknowledge an alert

### Intelligence
- `intelligence_summary` - Overall insights
- `production_intelligence` - Production insights
- `consumption_intelligence` - Consumption insights

### Config
- `config` - Current configuration

## Run locally

```bash
cd /path/to/PowerPulse
python3 -m venv .venv-mcp
source .venv-mcp/bin/activate
pip install -r mcp_server/requirements.txt
```

Set API location if needed (default is `http://127.0.0.1:8000`):
```bash
export SOLAR_API_BASE_URL="http://127.0.0.1:8000"
export SOLAR_API_TIMEOUT="15"
```

Start server (stdio transport):
```bash
python -m mcp_server.server
```

## Example MCP client config

Use this in your MCP host config (adjust paths if needed):

```json
{
  "mcpServers": {
    "powerpulse": {
      "command": "/path/to/PowerPulse/.venv-mcp/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "SOLAR_API_BASE_URL": "http://127.0.0.1:8000",
        "SOLAR_API_TIMEOUT": "15"
      }
    }
  }
}
```

## API Endpoints Available

| MCP Tool | Backend Endpoint |
|----------|-----------------|
| `health` | `GET /health` |
| `health_live` | `GET /health/live` |
| `health_ready` | `GET /health/ready` |
| `latest` | `GET /latest` |
| `live` | `GET /live` |
| `charger_latest` | `GET /charger/latest` |
| `charger_history` | `GET /charger/history` |
| `series` | `GET /series` |
| `house_series` | `GET /house_series` |
| `devices` | `GET /devices` |
| `alerts` | `GET /api/alerts` |
| `alert_detail` | `GET /api/alerts/{id}` |
| `acknowledge_alert` | `POST /api/alerts/{id}/acknowledge` |
| `intelligence_summary` | `GET /api/intelligence/summary` |
| `production_intelligence` | `GET /api/intelligence/production` |
| `consumption_intelligence` | `GET /api/intelligence/consumption` |
| `config` | `GET /config` |
