import os
from typing import Any, Dict, Optional

import requests
from mcp.server.fastmcp import FastMCP


API_BASE_URL = os.environ.get("SOLAR_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT_SECONDS = float(os.environ.get("SOLAR_API_TIMEOUT", "15"))

mcp = FastMCP("solar-service")


def _request_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    response = requests.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


@mcp.tool()
def health() -> Dict[str, Any]:
    """Check if the solar backend API is reachable."""
    return _request_json("/health")


@mcp.tool()
def latest_snapshot() -> Dict[str, Any]:
    """Return latest per-panel snapshot and total production."""
    return _request_json("/latest")


@mcp.tool()
def house_series(
    from_epoch: Optional[int] = None,
    to_epoch: Optional[int] = None,
    interval: str = "raw",
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return house-level history.

    interval must be one of: raw, 5m, 1h.
    """
    params: Dict[str, Any] = {"interval": interval}
    if from_epoch is not None:
        params["from"] = from_epoch
    if to_epoch is not None:
        params["to"] = to_epoch
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return _request_json("/house_series", params=params)


@mcp.tool()
def panel_series(
    panel_id: str,
    from_epoch: Optional[int] = None,
    to_epoch: Optional[int] = None,
    interval: str = "raw",
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return panel-level history for one panel_id.

    interval must be one of: raw, 5m, 1h.
    """
    params: Dict[str, Any] = {"panel_id": panel_id, "interval": interval}
    if from_epoch is not None:
        params["from"] = from_epoch
    if to_epoch is not None:
        params["to"] = to_epoch
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return _request_json("/series", params=params)


@mcp.tool()
def list_devices(
    ip: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return gateway devices list.

    If ip/user/password are omitted, backend defaults are used.
    """
    params: Dict[str, Any] = {}
    if ip:
        params["ip"] = ip
    if user:
        params["user"] = user
    if password:
        params["pass"] = password
    return _request_json("/devices", params=params if params else None)


if __name__ == "__main__":
    mcp.run(transport="stdio")
