import importlib
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from datetime import timezone
from pathlib import Path

from sqlalchemy import create_engine  # pyright: ignore[reportMissingImports]
from sqlalchemy import text  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import sessionmaker  # pyright: ignore[reportMissingImports]


class ConsumptionIntelligenceTests(unittest.TestCase):
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

        cls.dsn = os.environ["DATABASE_DSN"]
        cls.engine = create_engine(cls.dsn, future=True, connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
        cls.consumption_job = importlib.reload(importlib.import_module("backend.jobs.consumption_intelligence"))
        cls.consumption_repo_module = importlib.reload(importlib.import_module("backend.repositories.consumption_intelligence"))

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
    def _insert_house_row(conn, ts: int, consumption_kw: float, production_kw: float = 1.5) -> None:
        conn.execute(
            text(
                """
                INSERT INTO house_raw
                (ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                VALUES
                (:ts, :production_kw, :consumption_kw, :net_kw, 240.0, 120.0, 120.0, '1.0', '127.0.0.1')
                """
            ),
            {
                "ts": ts,
                "production_kw": production_kw,
                "consumption_kw": consumption_kw,
                "net_kw": production_kw - consumption_kw,
            },
        )

    @classmethod
    def _seed_weekly_history(
        cls,
        conn,
        *,
        latest_ts: int,
        bucket_offsets: list[int],
        baseline_consumption_kw: float,
        weeks: int,
    ) -> None:
        for weeks_back in range(weeks, 0, -1):
            for offset in bucket_offsets:
                ts = latest_ts - (weeks_back * 7 * 86400) + offset
                cls._insert_house_row(conn, ts=ts, consumption_kw=baseline_consumption_kw, production_kw=1.8)

    def _run_cycle(self, latest_ts: int) -> dict[str, int | bool]:
        with self.SessionLocal() as session:
            try:
                repo = self.consumption_repo_module.ConsumptionIntelligenceRepository(session)
                summary = self.consumption_job.run_consumption_intelligence_cycle(repository=repo, now_ts=latest_ts)
                session.commit()
                return summary
            except Exception:
                session.rollback()
                raise

    def test_normal_load_persists_baseline_without_anomaly(self):
        latest_ts = int(datetime(2023, 11, 20, 14, 0, tzinfo=timezone.utc).timestamp())
        with self.engine.begin() as conn:
            self._seed_weekly_history(
                conn,
                latest_ts=latest_ts,
                bucket_offsets=[0],
                baseline_consumption_kw=1.0,
                weeks=6,
            )
            self._insert_house_row(conn, ts=latest_ts, consumption_kw=1.1, production_kw=1.6)

        summary = self._run_cycle(latest_ts=latest_ts)
        self.assertGreaterEqual(summary["baseline_windows"], 1)
        self.assertFalse(summary["anomaly_created"])

        with self.engine.begin() as conn:
            baseline_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM site_power_baselines
                    WHERE metric = 'consumption_kw'
                      AND bucket_start_ts = :bucket_ts
                    """
                ),
                {"bucket_ts": latest_ts},
            ).scalar_one()
            anomaly_count = conn.execute(text("SELECT COUNT(*) FROM anomalies")).scalar_one()

        self.assertEqual(baseline_count, 1)
        self.assertEqual(anomaly_count, 0)

    def test_short_transient_spike_creates_spike_anomaly(self):
        latest_ts = int(datetime(2023, 11, 20, 14, 0, tzinfo=timezone.utc).timestamp())
        offsets = [-900, -600, -300, 0]
        with self.engine.begin() as conn:
            self._seed_weekly_history(
                conn,
                latest_ts=latest_ts,
                bucket_offsets=offsets,
                baseline_consumption_kw=1.0,
                weeks=6,
            )
            self._insert_house_row(conn, ts=latest_ts - 900, consumption_kw=1.0, production_kw=1.5)
            self._insert_house_row(conn, ts=latest_ts - 600, consumption_kw=1.1, production_kw=1.5)
            self._insert_house_row(conn, ts=latest_ts - 300, consumption_kw=1.0, production_kw=1.5)
            self._insert_house_row(conn, ts=latest_ts, consumption_kw=3.2, production_kw=1.2)

        summary = self._run_cycle(latest_ts=latest_ts)
        self.assertTrue(summary["anomaly_created"])

        with self.engine.begin() as conn:
            anomaly = conn.execute(
                text(
                    """
                    SELECT anomaly_id, explanation, evidence
                    FROM anomalies
                    WHERE metric = 'consumption_kw' AND sample_ts = :sample_ts
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
        self.assertEqual(evidence["pattern_type"], "spike")
        self.assertTrue(evidence["is_spike_like"])
        self.assertEqual(int(evidence["duration_seconds"]), 300)
        self.assertTrue(evidence["solar_context"]["demand_exceeds_solar"])
        self.assertIn("expected", str(anomaly["explanation"]).lower())
        self.assertIn("observed", str(anomaly["explanation"]).lower())

        count_by_type = {row["evidence_type"]: int(row["c"]) for row in evidence_counts}
        self.assertEqual(count_by_type.get("consumption_baseline_comparison", 0), 1)
        self.assertEqual(count_by_type.get("consumption_spike_window", 0), 1)
        self.assertEqual(count_by_type.get("consumption_solar_context", 0), 1)

    def test_sustained_high_demand_creates_sustained_anomaly(self):
        latest_ts = int(datetime(2023, 11, 20, 15, 0, tzinfo=timezone.utc).timestamp())
        offsets = [-1200, -900, -600, -300, 0]
        with self.engine.begin() as conn:
            self._seed_weekly_history(
                conn,
                latest_ts=latest_ts,
                bucket_offsets=offsets,
                baseline_consumption_kw=1.0,
                weeks=6,
            )
            self._insert_house_row(conn, ts=latest_ts - 1200, consumption_kw=2.6, production_kw=1.3)
            self._insert_house_row(conn, ts=latest_ts - 900, consumption_kw=2.8, production_kw=1.3)
            self._insert_house_row(conn, ts=latest_ts - 600, consumption_kw=2.7, production_kw=1.3)
            self._insert_house_row(conn, ts=latest_ts - 300, consumption_kw=2.9, production_kw=1.3)
            self._insert_house_row(conn, ts=latest_ts, consumption_kw=2.8, production_kw=1.3)

        summary = self._run_cycle(latest_ts=latest_ts)
        self.assertTrue(summary["anomaly_created"])

        with self.engine.begin() as conn:
            anomaly = conn.execute(
                text(
                    """
                    SELECT anomaly_id, evidence
                    FROM anomalies
                    WHERE metric = 'consumption_kw' AND sample_ts = :sample_ts
                    """
                ),
                {"sample_ts": latest_ts},
            ).mappings().one()
            sustained_rows = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM anomaly_evidence
                    WHERE anomaly_id = :anomaly_id
                      AND evidence_type = 'consumption_sustained_window'
                    """
                ),
                {"anomaly_id": int(anomaly["anomaly_id"])},
            ).scalar_one()

        evidence = anomaly["evidence"]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        self.assertEqual(evidence["pattern_type"], "sustained")
        self.assertGreaterEqual(int(evidence["duration_seconds"]), 1200)
        self.assertGreaterEqual(int(evidence["sustained_window"]["bucket_count"]), 4)
        self.assertEqual(int(sustained_rows), 1)

    def test_insufficient_history_suppresses_anomaly(self):
        latest_ts = int(datetime(2023, 11, 20, 14, 0, tzinfo=timezone.utc).timestamp())
        with self.engine.begin() as conn:
            self._seed_weekly_history(
                conn,
                latest_ts=latest_ts,
                bucket_offsets=[0],
                baseline_consumption_kw=1.0,
                weeks=2,
            )
            self._insert_house_row(conn, ts=latest_ts, consumption_kw=3.5, production_kw=1.0)

        summary = self._run_cycle(latest_ts=latest_ts)
        self.assertFalse(summary["anomaly_created"])

        with self.engine.begin() as conn:
            baseline_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM site_power_baselines
                    WHERE metric = 'consumption_kw'
                      AND bucket_start_ts = :bucket_ts
                    """
                ),
                {"bucket_ts": latest_ts},
            ).scalar_one()
            anomaly_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM anomalies
                    WHERE metric = 'consumption_kw'
                    """
                )
            ).scalar_one()

        self.assertEqual(int(baseline_count), 0)
        self.assertEqual(int(anomaly_count), 0)


if __name__ == "__main__":
    unittest.main()
