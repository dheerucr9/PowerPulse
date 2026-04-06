# Solar MCP Server

MCP wrapper for the running Solar backend API in this repo.

## What it exposes
- `health`
- `latest_snapshot`
- `house_series`
- `panel_series`
- `list_devices`

`house_series` and `panel_series` support pagination passthrough:
- `limit` (optional)
- `cursor` (optional)

Returned payload includes API `page_info`, so MCP clients can iterate until `has_more=false`.

## Run locally
```bash
cd /Users/dheeraj/Documents/snaird_v2/by-the-power-of-ai/s_power
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
Use this in your MCP host config (adjust python path if needed):

```json
{
  "mcpServers": {
    "solar-service": {
      "command": "/Users/dheeraj/Documents/snaird_v2/by-the-power-of-ai/s_power/.venv-mcp/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "SOLAR_API_BASE_URL": "http://127.0.0.1:8000",
        "SOLAR_API_TIMEOUT": "15"
      }
    }
  }
}
```
