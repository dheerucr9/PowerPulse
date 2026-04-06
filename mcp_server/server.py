import os
from typing import Any, Dict, List, Optional

import requests
from mcp.server.fastmcp import FastMCP


API_BASE_URL = os.environ.get("SOLAR_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT_SECONDS = float(os.environ.get("SOLAR_API_TIMEOUT", "15"))

mcp = FastMCP("powerpulse")


def _request_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    response = requests.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


# Health endpoints

@mcp.tool()
def health() -> Dict[str, Any]:
    """Check if the API is running."""
    return _request_json("/health")


@mcp.tool()
def health_live() -> Dict[str, Any]:
    """Check if the API process is alive."""
    return _request_json("/health/live")


@mcp.tool()
def health_ready() -> Dict[str, Any]:
    """Check if the API is ready (DB connected, migrations applied, ingest fresh)."""
    return _request_json("/health/ready")


# Live data

@mcp.tool()
def latest() -> Dict[str, Any]:
    """Return latest solar snapshot with per-panel data and totals."""
    return _request_json("/latest")


@mcp.tool()
def live() -> Dict[str, Any]:
    """Return current live state with solar production and house consumption."""
    return _request_json("/live")


# Charger (Tesla Wall Connector)

@mcp.tool()
def charger_latest() -> Dict[str, Any]:
    """Return latest Tesla Wall Connector status."""
    return _request_json("/charger/latest")


@mcp.tool()
def charger_history(
    from_epoch: Optional[int] = None,
    to_epoch: Optional[int] = None,
    interval: str = "raw",
    limit: int = 500,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return charger history (paginated).
    
    Args:
        from_epoch: Start timestamp
        to_epoch: End timestamp
        interval: raw, 5m, or 1h
        limit: Max results per page (default 500)
        cursor: Pagination cursor from previous response
    """
    params: Dict[str, Any] = {"interval": interval, "limit": limit}
    if from_epoch is not None:
        params["from"] = from_epoch
    if to_epoch is not None:
        params["to"] = to_epoch
    if cursor is not None:
        params["cursor"] = cursor
    return _request_json("/charger/history", params=params)


# Time series data

@mcp.tool()
def series(
    from_epoch: Optional[int] = None,
    to_epoch: Optional[int] = None,
    interval: str = "raw",
    panel_id: Optional[str] = None,
    limit: int = 500,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return solar panel time series data (paginated).
    
    Args:
        from_epoch: Start timestamp
        to_epoch: End timestamp
        interval: raw, 5m, or 1h
        panel_id: Filter by specific panel (optional)
        limit: Max results per page (default 500)
        cursor: Pagination cursor
    """
    params: Dict[str, Any] = {"interval": interval, "limit": limit}
    if from_epoch is not None:
        params["from"] = from_epoch
    if to_epoch is not None:
        params["to"] = to_epoch
    if panel_id is not None:
        params["panel_id"] = panel_id
    if cursor is not None:
        params["cursor"] = cursor
    return _request_json("/series", params=params)


@mcp.tool()
def house_series(
    from_epoch: Optional[int] = None,
    to_epoch: Optional[int] = None,
    interval: str = "raw",
    limit: int = 500,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return house-level time series (production, consumption, net).
    
    Args:
        from_epoch: Start timestamp
        to_epoch: End timestamp
        interval: raw, 5m, or 1h
        limit: Max results per page (default 500)
        cursor: Pagination cursor
    """
    params: Dict[str, Any] = {"interval": interval, "limit": limit}
    if from_epoch is not None:
        params["from"] = from_epoch
    if to_epoch is not None:
        params["to"] = to_epoch
    if cursor is not None:
        params["cursor"] = cursor
    return _request_json("/house_series", params=params)


# Devices

@mcp.tool()
def devices() -> Dict[str, Any]:
    """Return list of gateway devices."""
    return _request_json("/devices")


# Alerts

@mcp.tool()
def alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Return alerts with optional filtering.
    
    Args:
        status: Filter by status (open, acknowledged, resolved, suppressed)
        severity: Filter by severity (info, warning, critical)
        kind: Filter by kind (production, consumption, charger)
        limit: Max results (default 50)
    """
    params: Dict[str, Any] = {"limit": limit}
    if status is not None:
        params["status"] = status
    if severity is not None:
        params["severity"] = severity
    if kind is not None:
        params["kind"] = kind
    return _request_json("/api/alerts", params=params)


@mcp.tool()
def alert_detail(alert_id: str) -> Dict[str, Any]:
    """Return detailed information for a specific alert."""
    return _request_json(f"/api/alerts/{alert_id}")


@mcp.tool()
def acknowledge_alert(alert_id: str, note: Optional[str] = None) -> Dict[str, Any]:
    """
    Acknowledge an alert.
    
    Args:
        alert_id: The alert ID to acknowledge
        note: Optional note for acknowledgment
    """
    url = f"{API_BASE_URL}/api/alerts/{alert_id}/acknowledge"
    payload: Dict[str, Any] = {}
    if note is not None:
        payload["note"] = note
    response = requests.post(url, json=payload, timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


# Intelligence

@mcp.tool()
def intelligence_summary() -> Dict[str, Any]:
    """Return intelligence insights summary."""
    return _request_json("/api/intelligence/summary")


@mcp.tool()
def production_intelligence() -> Dict[str, Any]:
    """Return production intelligence insights."""
    return _request_json("/api/intelligence/production")


@mcp.tool()
def consumption_intelligence() -> Dict[str, Any]:
    """Return consumption intelligence insights."""
    return _request_json("/api/intelligence/consumption")


# Config

@mcp.tool()
def config() -> Dict[str, Any]:
    """Return current configuration."""
    return _request_json("/config")


if __name__ == "__main__":
    mcp.run(transport="stdio")
