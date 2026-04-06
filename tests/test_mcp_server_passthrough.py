import unittest
from unittest.mock import patch
import sys
import types


class _FakeFastMCP:
    def __init__(self, *_args, **_kwargs):
        pass

    def tool(self):
        def _decorator(func):
            return func

        return _decorator

    def run(self, *_args, **_kwargs):
        return None


fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
fake_fastmcp_module.FastMCP = _FakeFastMCP
sys.modules.setdefault("mcp", types.ModuleType("mcp"))
sys.modules.setdefault("mcp.server", types.ModuleType("mcp.server"))
sys.modules["mcp.server.fastmcp"] = fake_fastmcp_module

from mcp_server import server


class McpPassthroughTests(unittest.TestCase):
    def test_house_series_passes_limit_and_cursor(self):
        with patch("mcp_server.server._request_json", return_value={"ok": True}) as req:
            server.house_series(from_epoch=10, to_epoch=20, interval="5m", limit=123, cursor="abc123")
            req.assert_called_once_with(
                "/house_series",
                params={"interval": "5m", "from": 10, "to": 20, "limit": 123, "cursor": "abc123"},
            )

    def test_panel_series_passes_limit_and_cursor(self):
        with patch("mcp_server.server._request_json", return_value={"ok": True}) as req:
            server.panel_series(
                panel_id="panel-A",
                from_epoch=10,
                to_epoch=20,
                interval="1h",
                limit=321,
                cursor="cursor-token",
            )
            req.assert_called_once_with(
                "/series",
                params={
                    "panel_id": "panel-A",
                    "interval": "1h",
                    "from": 10,
                    "to": 20,
                    "limit": 321,
                    "cursor": "cursor-token",
                },
            )


if __name__ == "__main__":
    unittest.main()
