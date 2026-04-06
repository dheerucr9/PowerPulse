import importlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text


class ApiPaginationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(delete=False)
        cls.db_path = cls.tmp.name
        cls.tmp.close()

        os.environ["DATABASE_DSN"] = f"sqlite+pysqlite:///{cls.db_path}"
        os.environ["DB_PATH"] = cls.db_path
        os.environ["GATEWAY_IP"] = "127.0.0.1"
        os.environ["GATEWAY_USER"] = "u"
        os.environ["GATEWAY_PASS"] = "p"
        os.environ["TZ"] = "UTC"

        subprocess.run(
            [
                str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "alembic"),
                "-c",
                str(Path(__file__).resolve().parents[1] / "alembic.ini"),
                "upgrade",
                "head",
            ],
            check=True,
            env=os.environ.copy(),
        )

        import backend.main as backend_main  # noqa: WPS433

        cls.backend_main = importlib.reload(backend_main)
        cls.client = TestClient(cls.backend_main.app)

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.db_path)
        except OSError:
            pass

    def setUp(self):
        house_rows = []
        panel_rows = []

        for i in range(12):
            ts = 1_700_000_000 + i
            house_rows.append(
                {
                    "ts": ts,
                    "production_kw": 1.0 + i,
                    "consumption_kw": 0.5 + i,
                    "net_kw": 0.5,
                    "v_sys": 240.0,
                    "v_l1": 120.0,
                    "v_l2": 120.0,
                    "gateway_swver": "1.0",
                    "gateway_ip": "127.0.0.1",
                }
            )
            panel_rows.append(
                {
                    "ts": ts,
                    "panel_id": "panel-A",
                    "p_kw": 0.4 + i,
                    "v_ac": 120.0,
                    "v_dc": 45.0,
                    "i_dc": 1.2,
                    "temp_c": 35.0,
                    "state": "OK",
                    "serial": "panel-A",
                    "gateway_swver": "1.0",
                    "gateway_ip": "127.0.0.1",
                }
            )

        bucket_offsets = [300, 600, 900, 3600, 7200, 10800]
        for idx, offset in enumerate(bucket_offsets, start=1):
            ts = 1_700_000_000 + offset
            house_rows.append(
                {
                    "ts": ts,
                    "production_kw": 5.0 + idx,
                    "consumption_kw": 2.0 + idx,
                    "net_kw": 3.0,
                    "v_sys": 241.0,
                    "v_l1": 120.5,
                    "v_l2": 120.5,
                    "gateway_swver": "1.0",
                    "gateway_ip": "127.0.0.1",
                }
            )
            panel_rows.append(
                {
                    "ts": ts,
                    "panel_id": "panel-A",
                    "p_kw": 2.4 + idx,
                    "v_ac": 121.0,
                    "v_dc": 46.0,
                    "i_dc": 1.3,
                    "temp_c": 36.0,
                    "state": "OK",
                    "serial": "panel-A",
                    "gateway_swver": "1.0",
                    "gateway_ip": "127.0.0.1",
                }
            )

        with self.backend_main.db.engine.begin() as conn:
            conn.execute(text("DELETE FROM samples_raw"))
            conn.execute(text("DELETE FROM house_raw"))
            conn.execute(
                text(
                    """
                    INSERT INTO house_raw
                    (ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                    VALUES
                    (:ts, :production_kw, :consumption_kw, :net_kw, :v_sys, :v_l1, :v_l2, :gateway_swver, :gateway_ip)
                    """
                ),
                house_rows,
            )
            conn.execute(
                text(
                    """
                    INSERT INTO samples_raw
                    (ts, panel_id, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial, gateway_swver, gateway_ip)
                    VALUES
                    (:ts, :panel_id, :p_kw, :v_ac, :v_dc, :i_dc, :temp_c, :state, :serial, :gateway_swver, :gateway_ip)
                    """
                ),
                panel_rows,
            )

    def test_house_series_first_page_returns_page_info(self):
        resp = self.client.get(
            "/house_series",
            params={"from": 1_700_000_000, "to": 1_700_000_100, "interval": "raw", "limit": 5},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["samples"]), 5)
        self.assertTrue(data["page_info"]["has_more"])
        self.assertIsNotNone(data["page_info"]["next_cursor"])
        self.assertEqual(data["page_info"]["returned"], 5)
        self.assertEqual(data["page_info"]["limit"], 5)

    def test_house_series_page_walk_has_no_gaps_or_dupes(self):
        cursor = None
        all_ts = []
        while True:
            params = {"from": 1_700_000_000, "to": 1_700_000_100, "interval": "raw", "limit": 4}
            if cursor:
                params["cursor"] = cursor
            resp = self.client.get("/house_series", params=params)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            all_ts.extend([row["ts"] for row in data["samples"]])
            if not data["page_info"]["has_more"]:
                break
            cursor = data["page_info"]["next_cursor"]
            self.assertIsNotNone(cursor)

        self.assertEqual(all_ts, [1_700_000_000 + i for i in range(12)])

    def test_panel_series_page_walk_has_no_gaps_or_dupes(self):
        cursor = None
        all_ts = []
        while True:
            params = {
                "from": 1_700_000_000,
                "to": 1_700_000_100,
                "interval": "raw",
                "panel_id": "panel-A",
                "limit": 3,
            }
            if cursor:
                params["cursor"] = cursor
            resp = self.client.get("/series", params=params)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            all_ts.extend([row["ts"] for row in data["samples"]])
            if not data["page_info"]["has_more"]:
                break
            cursor = data["page_info"]["next_cursor"]
            self.assertIsNotNone(cursor)

        self.assertEqual(all_ts, [1_700_000_000 + i for i in range(12)])

    def test_invalid_cursor_returns_400(self):
        resp = self.client.get(
            "/house_series",
            params={
                "from": 1_700_000_000,
                "to": 1_700_000_100,
                "interval": "raw",
                "limit": 5,
                "cursor": "not-a-valid-cursor",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Invalid cursor")

    def test_limit_bounds_enforced(self):
        high = self.client.get(
            "/house_series",
            params={"from": 1_700_000_000, "to": 1_700_000_100, "interval": "raw", "limit": 999999},
        )
        self.assertEqual(high.status_code, 200)
        self.assertEqual(high.json()["page_info"]["limit"], 5000)

        low = self.client.get(
            "/house_series",
            params={"from": 1_700_000_000, "to": 1_700_000_100, "interval": "raw", "limit": 0},
        )
        self.assertEqual(low.status_code, 400)

    def test_house_series_5m_interval_page_walk(self):
        cursor = None
        all_ts = []
        while True:
            params = {"from": 1_700_000_000, "to": 1_700_004_000, "interval": "5m", "limit": 2}
            if cursor:
                params["cursor"] = cursor
            resp = self.client.get("/house_series", params=params)
            self.assertEqual(resp.status_code, 200)
            payload = resp.json()
            all_ts.extend(row["ts"] for row in payload["samples"])
            if not payload["page_info"]["has_more"]:
                break
            cursor = payload["page_info"]["next_cursor"]
            self.assertIsNotNone(cursor)

        self.assertEqual(all_ts, sorted(all_ts))
        self.assertGreaterEqual(len(all_ts), 3)
        self.assertEqual(len(all_ts), len(set(all_ts)))

    def test_panel_series_1h_interval_page_walk(self):
        cursor = None
        all_ts = []
        while True:
            params = {
                "from": 1_700_000_000,
                "to": 1_700_020_000,
                "interval": "1h",
                "panel_id": "panel-A",
                "limit": 2,
            }
            if cursor:
                params["cursor"] = cursor
            resp = self.client.get("/series", params=params)
            self.assertEqual(resp.status_code, 200)
            payload = resp.json()
            all_ts.extend(row["ts"] for row in payload["samples"])
            if not payload["page_info"]["has_more"]:
                break
            cursor = payload["page_info"]["next_cursor"]
            self.assertIsNotNone(cursor)

        self.assertEqual(all_ts, sorted(all_ts))
        self.assertGreaterEqual(len(all_ts), 2)
        self.assertEqual(len(all_ts), len(set(all_ts)))


if __name__ == "__main__":
    unittest.main()
