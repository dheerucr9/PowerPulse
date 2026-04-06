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


class AlertLifecycleTests(unittest.TestCase):
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

        cls.engine = create_engine(os.environ["DATABASE_DSN"], future=True, connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
        cls.alert_repo_module = importlib.reload(importlib.import_module("backend.repositories.alerts"))
        cls.alert_service_module = importlib.reload(importlib.import_module("backend.services.alerts"))

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

    def _insert_anomaly(self, session, sample_ts: int, severity: str = "warning") -> int:
        row = session.execute(
            text(
                """
                INSERT INTO anomalies
                (
                    site_id,
                    panel_id,
                    metric,
                    source,
                    direction,
                    severity,
                    state,
                    detected_at_ts,
                    sample_ts,
                    explanation,
                    evidence
                )
                VALUES
                (
                    'default',
                    NULL,
                    'consumption_kw',
                    'site',
                    'above',
                    :severity,
                    'open',
                    :sample_ts,
                    :sample_ts,
                    'high consumption detected',
                    :evidence
                )
                RETURNING anomaly_id
                """
            ),
            {
                "sample_ts": sample_ts,
                "severity": severity,
                "evidence": json.dumps({"window": sample_ts}),
            },
        ).mappings().one()
        return int(row["anomaly_id"])

    def _service(self, session):
        repo = self.alert_repo_module.AlertsRepository(session)
        return self.alert_service_module.AlertLifecycleService(repo)

    def test_duplicate_detections_coalesce_into_single_active_alert(self):
        with self.SessionLocal() as session:
            service = self._service(session)
            anomaly_1 = self._insert_anomaly(session, sample_ts=1_000, severity="warning")
            service.record_anomaly_detection(
                anomaly_id=anomaly_1,
                site_id="default",
                panel_id=None,
                source="site",
                metric="consumption_kw",
                direction="above",
                severity="warning",
                sample_ts=1_000,
                title="Consumption spike",
                message="Expected 1.0kW, observed 3.0kW",
                baseline_kw=1.0,
                observed_kw=3.0,
                deviation_kw=2.0,
                deviation_pct=200.0,
                confidence_score=0.9,
                affected_panel_count=None,
                explanation="Expected 1.0kW, observed 3.0kW",
                evidence={"pattern": "spike"},
            )

            anomaly_2 = self._insert_anomaly(session, sample_ts=1_300, severity="info")
            service.record_anomaly_detection(
                anomaly_id=anomaly_2,
                site_id="default",
                panel_id=None,
                source="site",
                metric="consumption_kw",
                direction="above",
                severity="info",
                sample_ts=1_300,
                title="Consumption spike",
                message="Expected 1.0kW, observed 2.4kW",
                baseline_kw=1.0,
                observed_kw=2.4,
                deviation_kw=1.4,
                deviation_pct=140.0,
                confidence_score=0.8,
                affected_panel_count=None,
                explanation="Expected 1.0kW, observed 2.4kW",
                evidence={"pattern": "spike"},
            )
            session.commit()

        with self.engine.begin() as conn:
            alerts = conn.execute(text("SELECT * FROM alerts ORDER BY alert_id ASC")).mappings().all()

        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(int(alert["first_seen_ts"]), 1_000)
        self.assertEqual(int(alert["last_seen_ts"]), 1_300)
        self.assertEqual(str(alert["status"]), "open")
        self.assertEqual(int(alert["anomaly_id"]), anomaly_2)
        self.assertEqual(str(alert["severity"]), "warning")

        payload = alert["explanation_payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        self.assertEqual(payload["kind"], "consumption")
        self.assertEqual(int(payload["sample_ts"]), 1_300)
        self.assertEqual(payload["evidence"]["pattern"], "spike")

    def test_open_to_acknowledged_records_default_operator_audit_row(self):
        with self.SessionLocal() as session:
            service = self._service(session)
            anomaly_id = self._insert_anomaly(session, sample_ts=2_000)
            alert_id = service.record_anomaly_detection(
                anomaly_id=anomaly_id,
                site_id="default",
                panel_id=None,
                source="site",
                metric="consumption_kw",
                direction="above",
                severity="warning",
                sample_ts=2_000,
                title="Consumption spike",
                message="Expected 1.0kW, observed 2.8kW",
                baseline_kw=1.0,
                observed_kw=2.8,
                deviation_kw=1.8,
                deviation_pct=180.0,
                confidence_score=0.8,
                affected_panel_count=None,
                explanation="Expected 1.0kW, observed 2.8kW",
                evidence={"pattern": "spike"},
            )

            service.acknowledge_alert(
                alert_id=alert_id,
                new_status="acknowledged",
                acknowledged_by=None,
                note="Investigating",
                acknowledged_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            )
            session.commit()

        with self.engine.begin() as conn:
            alert = conn.execute(text("SELECT * FROM alerts ORDER BY alert_id DESC LIMIT 1")).mappings().one()
            ack = conn.execute(text("SELECT * FROM alert_acknowledgements ORDER BY ack_id DESC LIMIT 1")).mappings().one()

        self.assertEqual(str(alert["status"]), "acknowledged")
        self.assertEqual(str(alert["acknowledged_by"]), "local-operator")
        self.assertEqual(str(alert["acknowledged_note"]), "Investigating")
        self.assertEqual(str(ack["previous_status"]), "open")
        self.assertEqual(str(ack["new_status"]), "acknowledged")
        self.assertEqual(str(ack["acknowledged_by"]), "local-operator")

    def test_open_to_resolved_records_resolution_without_losing_evidence(self):
        with self.SessionLocal() as session:
            service = self._service(session)
            anomaly_id = self._insert_anomaly(session, sample_ts=3_000, severity="critical")
            alert_id = service.record_anomaly_detection(
                anomaly_id=anomaly_id,
                site_id="default",
                panel_id=None,
                source="site",
                metric="consumption_kw",
                direction="above",
                severity="critical",
                sample_ts=3_000,
                title="Consumption sustained anomaly",
                message="Expected 1.2kW, observed 3.6kW",
                baseline_kw=1.2,
                observed_kw=3.6,
                deviation_kw=2.4,
                deviation_pct=200.0,
                confidence_score=0.95,
                affected_panel_count=None,
                explanation="Expected 1.2kW, observed 3.6kW",
                evidence={"pattern": "sustained", "duration_seconds": 1200},
            )

            service.acknowledge_alert(
                alert_id=alert_id,
                new_status="resolved",
                acknowledged_by="ops-a",
                note="Load normalized",
                acknowledged_at=datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
            )
            session.commit()

        with self.engine.begin() as conn:
            alert = conn.execute(text("SELECT * FROM alerts ORDER BY alert_id DESC LIMIT 1")).mappings().one()
            ack = conn.execute(text("SELECT * FROM alert_acknowledgements ORDER BY ack_id DESC LIMIT 1")).mappings().one()

        payload = alert["explanation_payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        self.assertEqual(str(alert["status"]), "resolved")
        self.assertEqual(str(alert["resolved_by"]), "ops-a")
        self.assertEqual(str(alert["resolution_note"]), "Load normalized")
        self.assertEqual(payload["evidence"]["pattern"], "sustained")
        self.assertEqual(str(ack["new_status"]), "resolved")

    def test_suppression_closes_active_alert_and_next_detection_opens_new_row(self):
        with self.SessionLocal() as session:
            service = self._service(session)
            anomaly_1 = self._insert_anomaly(session, sample_ts=4_000, severity="warning")
            alert_id = service.record_anomaly_detection(
                anomaly_id=anomaly_1,
                site_id="default",
                panel_id=None,
                source="site",
                metric="consumption_kw",
                direction="above",
                severity="warning",
                sample_ts=4_000,
                title="Consumption spike",
                message="Expected 1.0kW, observed 2.5kW",
                baseline_kw=1.0,
                observed_kw=2.5,
                deviation_kw=1.5,
                deviation_pct=150.0,
                confidence_score=0.7,
                affected_panel_count=None,
                explanation="Expected 1.0kW, observed 2.5kW",
                evidence={"pattern": "spike"},
            )
            service.acknowledge_alert(
                alert_id=alert_id,
                new_status="suppressed",
                acknowledged_by="ops-b",
                note="Known maintenance window",
                acknowledged_at=datetime(2024, 1, 1, 14, 0, tzinfo=timezone.utc),
            )

            anomaly_2 = self._insert_anomaly(session, sample_ts=4_300, severity="warning")
            service.record_anomaly_detection(
                anomaly_id=anomaly_2,
                site_id="default",
                panel_id=None,
                source="site",
                metric="consumption_kw",
                direction="above",
                severity="warning",
                sample_ts=4_300,
                title="Consumption spike",
                message="Expected 1.0kW, observed 2.6kW",
                baseline_kw=1.0,
                observed_kw=2.6,
                deviation_kw=1.6,
                deviation_pct=160.0,
                confidence_score=0.75,
                affected_panel_count=None,
                explanation="Expected 1.0kW, observed 2.6kW",
                evidence={"pattern": "spike"},
            )
            session.commit()

        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT alert_id, status, first_seen_ts, last_seen_ts FROM alerts ORDER BY alert_id ASC")).mappings().all()

        self.assertEqual(len(rows), 2)
        self.assertEqual(str(rows[0]["status"]), "suppressed")
        self.assertEqual(int(rows[0]["first_seen_ts"]), 4_000)
        self.assertEqual(int(rows[0]["last_seen_ts"]), 4_000)
        self.assertEqual(str(rows[1]["status"]), "open")
        self.assertEqual(int(rows[1]["first_seen_ts"]), 4_300)
        self.assertEqual(int(rows[1]["last_seen_ts"]), 4_300)


if __name__ == "__main__":
    unittest.main()
