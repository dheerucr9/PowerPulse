import importlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import text  # pyright: ignore[reportMissingImports]
from sqlalchemy import create_engine  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import sessionmaker  # pyright: ignore[reportMissingImports]


class ProductionIntelligenceTests(unittest.TestCase):
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
        os.environ["LATITUDE"] = "0"
        os.environ["LONGITUDE"] = "0"

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

        cls.dsn = os.environ["DATABASE_DSN"]
        cls.engine = create_engine(cls.dsn, future=True, connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
        cls.production_job = importlib.reload(importlib.import_module("backend.jobs.production_intelligence"))
        cls.production_repo_module = importlib.reload(importlib.import_module("backend.repositories.production_intelligence"))

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.db_path)
        except OSError:
            pass

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM alert_acknowledgements"))
            conn.execute(text("DELETE FROM alerts"))
            conn.execute(text("DELETE FROM anomaly_evidence"))
            conn.execute(text("DELETE FROM anomalies"))
            conn.execute(text("DELETE FROM panel_power_baselines"))
            conn.execute(text("DELETE FROM site_power_baselines"))
            conn.execute(text("DELETE FROM samples_raw"))
            conn.execute(text("DELETE FROM house_raw"))

    @staticmethod
    def _seed_history(conn, latest_ts: int, latest_production: float) -> None:
        history_rows = []
        panel_rows = []
        for days_back in range(8, 1, -1):
            ts = latest_ts - (days_back * 86400)
            history_rows.append(
                {
                    "ts": ts,
                    "production_kw": 4.0,
                    "consumption_kw": 1.2,
                    "net_kw": 2.8,
                    "v_sys": 240.0,
                    "v_l1": 120.0,
                    "v_l2": 120.0,
                    "gateway_swver": "1.0",
                    "gateway_ip": "127.0.0.1",
                }
            )
            panel_rows.extend(
                [
                    {
                        "ts": ts,
                        "panel_id": "panel-1",
                        "p_kw": 1.3,
                        "v_ac": 120.0,
                        "v_dc": 40.0,
                        "i_dc": 1.0,
                        "temp_c": 30.0,
                        "state": "OK",
                        "serial": "panel-1",
                        "gateway_swver": "1.0",
                        "gateway_ip": "127.0.0.1",
                    },
                    {
                        "ts": ts,
                        "panel_id": "panel-2",
                        "p_kw": 1.4,
                        "v_ac": 120.0,
                        "v_dc": 40.0,
                        "i_dc": 1.0,
                        "temp_c": 30.0,
                        "state": "OK",
                        "serial": "panel-2",
                        "gateway_swver": "1.0",
                        "gateway_ip": "127.0.0.1",
                    },
                    {
                        "ts": ts,
                        "panel_id": "panel-3",
                        "p_kw": 1.3,
                        "v_ac": 120.0,
                        "v_dc": 40.0,
                        "i_dc": 1.0,
                        "temp_c": 30.0,
                        "state": "OK",
                        "serial": "panel-3",
                        "gateway_swver": "1.0",
                        "gateway_ip": "127.0.0.1",
                    },
                ]
            )

        history_rows.append(
            {
                "ts": latest_ts,
                "production_kw": latest_production,
                "consumption_kw": 1.2,
                "net_kw": latest_production - 1.2,
                "v_sys": 240.0,
                "v_l1": 120.0,
                "v_l2": 120.0,
                "gateway_swver": "1.0",
                "gateway_ip": "127.0.0.1",
            }
        )

        conn.execute(
            text(
                """
                INSERT INTO house_raw
                (ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                VALUES
                (:ts, :production_kw, :consumption_kw, :net_kw, :v_sys, :v_l1, :v_l2, :gateway_swver, :gateway_ip)
                """
            ),
            history_rows,
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

    def test_daylight_baseline_persisted_without_anomaly_when_within_expected(self):
        latest_ts = 1_700_323_200
        night_ts = latest_ts - 12 * 3600

        with self.engine.begin() as conn:
            self._seed_history(conn, latest_ts=latest_ts, latest_production=3.9)
            conn.execute(
                text(
                    """
                    INSERT INTO house_raw
                    (ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                    VALUES
                    (:ts, 0, 0.8, -0.8, 240, 120, 120, '1.0', '127.0.0.1')
                    """
                ),
                {"ts": night_ts},
            )

        with self.SessionLocal() as session:
            try:
                repo = self.production_repo_module.ProductionIntelligenceRepository(session)
                summary = self.production_job.run_production_intelligence_cycle(repository=repo, now_ts=latest_ts)
                session.commit()
            except Exception:
                session.rollback()
                raise
        self.assertGreaterEqual(summary["baseline_windows"], 1)
        self.assertFalse(summary["anomaly_created"])

        with self.engine.begin() as conn:
            day_baseline_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS c
                    FROM site_power_baselines
                    WHERE metric = 'production_kw'
                      AND bucket_start_ts = :bucket_ts
                    """
                ),
                {"bucket_ts": latest_ts},
            ).scalar_one()
            night_baseline_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS c
                    FROM site_power_baselines
                    WHERE metric = 'production_kw'
                      AND bucket_start_ts = :bucket_ts
                    """
                ),
                {"bucket_ts": night_ts // 300 * 300},
            ).scalar_one()
            anomaly_count = conn.execute(text("SELECT COUNT(*) FROM anomalies")).scalar_one()

        self.assertEqual(day_baseline_count, 1)
        self.assertEqual(night_baseline_count, 0)
        self.assertEqual(anomaly_count, 0)

    def test_daylight_underproduction_persists_site_and_peer_evidence(self):
        latest_ts = 1_700_323_200
        with self.engine.begin() as conn:
            self._seed_history(conn, latest_ts=latest_ts, latest_production=1.0)
            conn.execute(text("DELETE FROM samples_raw WHERE ts = :ts"), {"ts": latest_ts})
            conn.execute(
                text(
                    """
                    INSERT INTO samples_raw
                    (ts, panel_id, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial, gateway_swver, gateway_ip)
                    VALUES
                    (:ts, 'panel-1', 1.2, 120, 40, 1.0, 30, 'OK', 'panel-1', '1.0', '127.0.0.1'),
                    (:ts, 'panel-2', 1.1, 120, 40, 1.0, 30, 'OK', 'panel-2', '1.0', '127.0.0.1'),
                    (:ts, 'panel-3', 0.2, 120, 40, 1.0, 30, 'FAULT: offline', 'panel-3', '1.0', '127.0.0.1')
                    """
                ),
                {"ts": latest_ts},
            )

        with self.SessionLocal() as session:
            try:
                repo = self.production_repo_module.ProductionIntelligenceRepository(session)
                summary = self.production_job.run_production_intelligence_cycle(repository=repo, now_ts=latest_ts)
                session.commit()
            except Exception:
                session.rollback()
                raise
        self.assertTrue(summary["anomaly_created"])

        with self.engine.begin() as conn:
            anomaly = conn.execute(
                text(
                    """
                    SELECT anomaly_id, baseline_kw, observed_kw, deviation_pct, panel_state, evidence
                    FROM anomalies
                    WHERE sample_ts = :sample_ts
                    """
                ),
                {"sample_ts": latest_ts},
            ).mappings().one()
            evidence_counts = conn.execute(
                text(
                    """
                    SELECT evidence_type, COUNT(*) AS c
                    FROM anomaly_evidence
                    WHERE anomaly_id = :anomaly_id
                    GROUP BY evidence_type
                    """
                ),
                {"anomaly_id": int(anomaly["anomaly_id"])},
            ).mappings().all()

        evidence = anomaly["evidence"]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        self.assertAlmostEqual(float(anomaly["observed_kw"]), 1.0, places=3)
        self.assertLess(float(anomaly["deviation_pct"]), -30.0)
        self.assertEqual(evidence["daylight"]["is_daylight"], True)
        self.assertGreaterEqual(evidence["affected_panel_count"], 1)
        self.assertGreaterEqual(len(evidence["panel_state_issues"]), 1)
        self.assertGreaterEqual(len(evidence["peer_underperforming_panels"]), 1)
        self.assertIn("fault", str(anomaly["panel_state"]).lower())

        count_by_type = {row["evidence_type"]: int(row["c"]) for row in evidence_counts}
        self.assertGreaterEqual(count_by_type.get("peer_underperforming_panel", 0), 1)
        self.assertGreaterEqual(count_by_type.get("panel_state_issue", 0), 1)

    def test_nighttime_zero_production_does_not_create_anomaly(self):
        latest_ts = 1_700_280_000
        with self.engine.begin() as conn:
            self._seed_history(conn, latest_ts=latest_ts, latest_production=0.0)
            conn.execute(text("DELETE FROM samples_raw WHERE ts = :ts"), {"ts": latest_ts})
            conn.execute(
                text(
                    """
                    INSERT INTO samples_raw
                    (ts, panel_id, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial, gateway_swver, gateway_ip)
                    VALUES
                    (:ts, 'panel-1', 0.0, 120, 40, 1.0, 30, 'OK', 'panel-1', '1.0', '127.0.0.1'),
                    (:ts, 'panel-2', 0.0, 120, 40, 1.0, 30, 'OK', 'panel-2', '1.0', '127.0.0.1')
                    """
                ),
                {"ts": latest_ts},
            )

        with self.SessionLocal() as session:
            try:
                repo = self.production_repo_module.ProductionIntelligenceRepository(session)
                summary = self.production_job.run_production_intelligence_cycle(repository=repo, now_ts=latest_ts)
                session.commit()
            except Exception:
                session.rollback()
                raise
        self.assertFalse(summary["anomaly_created"])

        with self.engine.begin() as conn:
            anomaly_count = conn.execute(text("SELECT COUNT(*) FROM anomalies")).scalar_one()

        self.assertEqual(anomaly_count, 0)


if __name__ == "__main__":
    unittest.main()
