# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

import importlib
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text


class HealthAndObservabilityTests(unittest.TestCase):
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
        os.environ["INGEST_FRESHNESS_MAX_AGE_SECONDS"] = "30"

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
        cls.backend_main.db.engine.dispose()

    def setUp(self):
        with self.backend_main.db.engine.begin() as conn:
            conn.execute(text("DELETE FROM samples_raw"))
            conn.execute(text("DELETE FROM house_raw"))
            conn.execute(text("DELETE FROM panel_power_samples"))
            conn.execute(text("DELETE FROM site_power_samples"))

    def test_health_live_returns_ok(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_ready_fails_when_db_unavailable(self):
        with patch("backend.main.db.get_connection", side_effect=RuntimeError("db unavailable")):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertFalse(payload["checks"]["database"])

    def test_health_ready_fails_when_ingest_is_stale(self):
        stale_ts = int(time.time()) - 1_000
        with self.backend_main.db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO house_raw
                    (ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                    VALUES
                    (:ts, 1.0, 0.5, 0.5, 240.0, 120.0, 120.0, '1.0', '127.0.0.1')
                    """
                ),
                {"ts": stale_ts},
            )

        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertTrue(payload["checks"]["database"])
        self.assertTrue(payload["checks"]["migrations"])
        self.assertFalse(payload["checks"]["ingest_fresh"])

    def test_metrics_exposes_api_db_poll_and_worker_metric_families(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("solar_api_request_duration_seconds", body)
        self.assertIn("solar_api_request_status_total", body)
        self.assertIn("solar_db_query_duration_seconds", body)
        self.assertIn("solar_poll_ingest_success_total", body)
        self.assertIn("solar_worker_job_duration_seconds", body)


if __name__ == "__main__":
    unittest.main()
