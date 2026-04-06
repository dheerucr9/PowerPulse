# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

import importlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text


class AlertsAndIntelligenceApiTests(unittest.TestCase):
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
        cls.backend_main.db.engine.dispose()

    def setUp(self):
        with self.backend_main.db.engine.begin() as conn:
            conn.execute(text("DELETE FROM alert_acknowledgements"))
            conn.execute(text("DELETE FROM alerts"))
            conn.execute(text("DELETE FROM anomaly_evidence"))
            conn.execute(text("DELETE FROM anomalies"))

    def _insert_anomaly(self, *, metric: str, direction: str, severity: str, sample_ts: int) -> int:
        with self.backend_main.db.engine.begin() as conn:
            row = conn.execute(
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
                        baseline_kw,
                        observed_kw,
                        deviation_kw,
                        deviation_pct,
                        confidence_score,
                        explanation,
                        evidence
                    )
                    VALUES
                    (
                        'default',
                        NULL,
                        :metric,
                        'site',
                        :direction,
                        :severity,
                        'open',
                        :sample_ts,
                        :sample_ts,
                        1.0,
                        2.0,
                        1.0,
                        100.0,
                        0.9,
                        :explanation,
                        :evidence
                    )
                    RETURNING anomaly_id
                    """
                ),
                {
                    "metric": metric,
                    "direction": direction,
                    "severity": severity,
                    "sample_ts": sample_ts,
                    "explanation": f"{metric} {direction} anomaly",
                    "evidence": json.dumps({"metric": metric, "direction": direction, "sample_ts": sample_ts}),
                },
            ).mappings().one()
            return int(row["anomaly_id"])

    def _insert_alert(self, *, anomaly_id: int, kind: str, severity: str, status: str, ts: int, title: str) -> int:
        with self.backend_main.db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO alerts
                    (
                        anomaly_id,
                        site_id,
                        panel_id,
                        dedupe_key,
                        kind,
                        category,
                        severity,
                        status,
                        state,
                        title,
                        message,
                        first_seen_ts,
                        last_seen_ts,
                        detected_at_ts,
                        last_observed_ts,
                        baseline_kw,
                        observed_kw,
                        deviation_kw,
                        deviation_pct,
                        confidence_score,
                        affected_panel_count,
                        evidence_summary,
                        explanation_payload
                    )
                    VALUES
                    (
                        :anomaly_id,
                        'default',
                        NULL,
                        :dedupe_key,
                        :kind,
                        :category,
                        :severity,
                        :status,
                        NULL,
                        :title,
                        :message,
                        :ts,
                        :ts,
                        :ts,
                        :ts,
                        1.0,
                        2.0,
                        1.0,
                        100.0,
                        0.9,
                        1,
                        :evidence_summary,
                        :explanation_payload
                    )
                    RETURNING alert_id
                    """
                ),
                {
                    "anomaly_id": anomaly_id,
                    "dedupe_key": f"default|*|{kind}|site|{kind}_kw|above",
                    "kind": kind,
                    "category": kind,
                    "severity": severity,
                    "status": status,
                    "title": title,
                    "message": f"{title} message",
                    "ts": ts,
                    "evidence_summary": f"{title} summary",
                    "explanation_payload": json.dumps(
                        {
                            "kind": kind,
                            "source": "site",
                            "metric": "consumption_kw" if kind == "consumption" else "production_kw",
                            "direction": "above" if kind == "consumption" else "below",
                            "title": title,
                            "message": f"{title} message",
                            "explanation": f"{title} explanation",
                            "evidence": {"panel_ids": ["panel-1"]},
                            "sample_ts": ts,
                        }
                    ),
                },
            ).mappings().one()
            return int(row["alert_id"])

    def test_openapi_includes_new_alert_and_intelligence_paths(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("/api/alerts", paths)
        self.assertIn("/api/alerts/{alert_id}", paths)
        self.assertIn("/api/alerts/{alert_id}/acknowledge", paths)
        self.assertIn("/api/intelligence/summary", paths)

    def test_alert_list_supports_status_kind_severity_filters(self):
        anomaly_consumption = self._insert_anomaly(metric="consumption_kw", direction="above", severity="critical", sample_ts=1_700_001_000)
        anomaly_production = self._insert_anomaly(metric="production_kw", direction="below", severity="warning", sample_ts=1_700_001_100)

        self._insert_alert(
            anomaly_id=anomaly_consumption,
            kind="consumption",
            severity="critical",
            status="open",
            ts=1_700_001_000,
            title="Consumption spike",
        )
        self._insert_alert(
            anomaly_id=anomaly_production,
            kind="production",
            severity="warning",
            status="acknowledged",
            ts=1_700_001_100,
            title="Production dip",
        )

        response = self.client.get(
            "/api/alerts",
            params={"status": "open", "kind": "consumption", "severity": "critical", "limit": 20},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["kind"], "consumption")
        self.assertEqual(payload["items"][0]["severity"], "critical")
        self.assertEqual(payload["items"][0]["status"], "open")
        self.assertIn("evidence", payload["items"][0]["explanation_payload"])
        self.assertEqual(payload["meta"]["filtered_total"], 1)
        self.assertEqual(payload["meta"]["open_badge_count"], 1)

    def test_alert_list_rejects_invalid_filter_values(self):
        response = self.client.get("/api/alerts", params={"status": "bogus"})
        self.assertEqual(response.status_code, 422)

    def test_alert_detail_returns_typed_alert_anomaly_and_evidence(self):
        anomaly_id = self._insert_anomaly(metric="consumption_kw", direction="above", severity="warning", sample_ts=1_700_002_000)
        alert_id = self._insert_alert(
            anomaly_id=anomaly_id,
            kind="consumption",
            severity="warning",
            status="open",
            ts=1_700_002_000,
            title="Sustained load",
        )
        with self.backend_main.db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO anomaly_evidence
                    (
                        anomaly_id,
                        site_id,
                        panel_id,
                        evidence_type,
                        reference_ts,
                        metric,
                        details,
                        context
                    )
                    VALUES
                    (
                        :anomaly_id,
                        'default',
                        NULL,
                        'consumption_baseline_comparison',
                        :ts,
                        'consumption_kw',
                        'baseline comparison',
                        :context
                    )
                    """
                ),
                {
                    "anomaly_id": anomaly_id,
                    "ts": 1_700_002_000,
                    "context": json.dumps({"expected_range_kw": {"low": 0.8, "high": 1.2}}),
                },
            )

        response = self.client.get(f"/api/alerts/{alert_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["alert"]["alert_id"], alert_id)
        self.assertEqual(payload["anomaly"]["anomaly_id"], anomaly_id)
        self.assertEqual(len(payload["anomaly_evidence"]), 1)
        self.assertIn("context", payload["anomaly_evidence"][0])
        self.assertIn("evidence", payload["anomaly"])

    def test_alert_detail_returns_404_for_unknown_id(self):
        response = self.client.get("/api/alerts/999999")
        self.assertEqual(response.status_code, 404)

    def test_acknowledge_endpoint_updates_status_and_returns_alert(self):
        anomaly_id = self._insert_anomaly(metric="production_kw", direction="below", severity="warning", sample_ts=1_700_003_000)
        alert_id = self._insert_alert(
            anomaly_id=anomaly_id,
            kind="production",
            severity="warning",
            status="open",
            ts=1_700_003_000,
            title="Production under target",
        )

        response = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"new_status": "acknowledged", "acknowledged_by": "ops-1", "note": "Investigating"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["alert_id"], alert_id)
        self.assertEqual(payload["status"], "acknowledged")
        self.assertEqual(payload["acknowledged_by"], "ops-1")

    def test_acknowledge_endpoint_returns_404_for_unknown_alert(self):
        response = self.client.post(
            "/api/alerts/424242/acknowledge",
            json={"new_status": "acknowledged", "acknowledged_by": "ops-2", "note": "Missing"},
        )
        self.assertEqual(response.status_code, 404)

    def test_acknowledge_endpoint_rejects_invalid_status(self):
        anomaly_id = self._insert_anomaly(metric="consumption_kw", direction="above", severity="warning", sample_ts=1_700_003_500)
        alert_id = self._insert_alert(
            anomaly_id=anomaly_id,
            kind="consumption",
            severity="warning",
            status="open",
            ts=1_700_003_500,
            title="Transient spike",
        )
        response = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"new_status": "open"},
        )
        self.assertEqual(response.status_code, 422)

    def test_intelligence_summary_returns_open_counts_and_latest_domain_summaries(self):
        anomaly_consumption = self._insert_anomaly(metric="consumption_kw", direction="above", severity="critical", sample_ts=1_700_004_000)
        anomaly_production = self._insert_anomaly(metric="production_kw", direction="below", severity="warning", sample_ts=1_700_004_100)
        self._insert_alert(
            anomaly_id=anomaly_consumption,
            kind="consumption",
            severity="critical",
            status="open",
            ts=1_700_004_000,
            title="Consumption sustained high",
        )
        self._insert_alert(
            anomaly_id=anomaly_production,
            kind="production",
            severity="warning",
            status="open",
            ts=1_700_004_100,
            title="Production daylight dip",
        )

        response = self.client.get("/api/intelligence/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("generated_at_ts", payload)
        self.assertEqual(payload["open_counts"]["total"], 2)
        self.assertEqual(payload["open_counts"]["by_kind"]["consumption"], 1)
        self.assertEqual(payload["open_counts"]["by_kind"]["production"], 1)
        self.assertEqual(payload["consumption"]["latest_alert"]["kind"], "consumption")
        self.assertEqual(payload["production"]["latest_alert"]["kind"], "production")
        self.assertEqual(payload["consumption"]["latest_anomaly"]["metric"], "consumption_kw")
        self.assertEqual(payload["production"]["latest_anomaly"]["metric"], "production_kw")


if __name__ == "__main__":
    unittest.main()
