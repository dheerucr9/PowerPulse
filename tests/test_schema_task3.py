import importlib
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


class CanonicalSchemaTask3Tests(unittest.TestCase):
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

        cls.models = importlib.reload(importlib.import_module("backend.models"))

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.db_path)
        except OSError:
            pass

    def setUp(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM alert_acknowledgements")
        conn.execute("DELETE FROM alerts")
        conn.execute("DELETE FROM anomaly_evidence")
        conn.execute("DELETE FROM anomalies")
        conn.execute("DELETE FROM panel_power_baselines")
        conn.execute("DELETE FROM site_power_baselines")
        conn.execute("DELETE FROM panel_power_samples")
        conn.execute("DELETE FROM site_power_samples")
        conn.execute("DELETE FROM site_panels")
        conn.execute("DELETE FROM sites WHERE site_id <> 'default'")
        conn.commit()
        conn.close()

    def test_canonical_tables_exist(self):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row[0] for row in rows}
        conn.close()

        expected = {
            "sites",
            "site_panels",
            "site_power_samples",
            "panel_power_samples",
            "site_power_baselines",
            "panel_power_baselines",
            "anomalies",
            "anomaly_evidence",
            "alerts",
            "alert_acknowledgements",
        }
        self.assertTrue(expected.issubset(table_names))

    def test_alerts_have_ack_and_typed_evidence_columns(self):
        conn = sqlite3.connect(self.db_path)
        columns = conn.execute("PRAGMA table_info('alerts')").fetchall()
        conn.close()
        names = {row[1] for row in columns}

        self.assertIn("status", names)
        self.assertIn("kind", names)
        self.assertIn("dedupe_key", names)
        self.assertIn("first_seen_ts", names)
        self.assertIn("last_seen_ts", names)
        self.assertIn("acknowledged_at", names)
        self.assertIn("acknowledged_by", names)
        self.assertIn("acknowledged_note", names)
        self.assertIn("baseline_kw", names)
        self.assertIn("observed_kw", names)
        self.assertIn("deviation_kw", names)
        self.assertIn("deviation_pct", names)
        self.assertIn("confidence_score", names)
        self.assertIn("explanation_payload", names)

    def test_anomalies_have_typed_explainability_columns(self):
        conn = sqlite3.connect(self.db_path)
        columns = conn.execute("PRAGMA table_info('anomalies')").fetchall()
        conn.close()
        names = {row[1] for row in columns}

        self.assertIn("metric", names)
        self.assertIn("baseline_kw", names)
        self.assertIn("observed_kw", names)
        self.assertIn("deviation_kw", names)
        self.assertIn("deviation_pct", names)
        self.assertIn("z_score", names)
        self.assertIn("confidence_score", names)
        self.assertIn("panel_state", names)

    def test_site_power_sample_uniqueness_is_enforced(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO site_power_samples (site_id, ts, production_kw, consumption_kw, net_kw)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("default", 1_700_000_000, 1.0, 2.0, -1.0),
        )
        conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO site_power_samples (site_id, ts, production_kw, consumption_kw, net_kw)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("default", 1_700_000_000, 1.0, 2.0, -1.0),
            )
            conn.commit()
        conn.close()

    def test_models_cover_all_task3_canonical_tables(self):
        expected = {
            "sites",
            "site_panels",
            "site_power_samples",
            "panel_power_samples",
            "site_power_baselines",
            "panel_power_baselines",
            "anomalies",
            "anomaly_evidence",
            "alerts",
            "alert_acknowledgements",
        }
        model_tables = set(self.models.Base.metadata.tables.keys())
        self.assertTrue(expected.issubset(model_tables))

    def test_models_match_task3_column_sets_for_anomalies_alerts_and_acks(self):
        expected_columns = {
            "site_power_baselines": {
                "baseline_id",
                "site_id",
                "metric",
                "bucket_start_ts",
                "bucket_granularity_seconds",
                "baseline_kw",
                "baseline_stddev_kw",
                "sample_count",
                "confidence_score",
                "model_version",
                "computed_at",
            },
            "panel_power_baselines": {
                "baseline_id",
                "site_id",
                "panel_id",
                "metric",
                "bucket_start_ts",
                "bucket_granularity_seconds",
                "baseline_kw",
                "baseline_stddev_kw",
                "sample_count",
                "confidence_score",
                "model_version",
                "computed_at",
            },
            "anomalies": {
                "anomaly_id",
                "site_id",
                "panel_id",
                "metric",
                "source",
                "direction",
                "severity",
                "state",
                "detected_at_ts",
                "sample_ts",
                "bucket_start_ts",
                "bucket_end_ts",
                "baseline_kw",
                "observed_kw",
                "deviation_kw",
                "deviation_pct",
                "z_score",
                "confidence_score",
                "sample_count",
                "panel_state",
                "explanation",
                "evidence",
                "created_at",
                "updated_at",
            },
            "anomaly_evidence": {
                "evidence_id",
                "anomaly_id",
                "site_id",
                "panel_id",
                "evidence_type",
                "reference_ts",
                "window_start_ts",
                "window_end_ts",
                "metric",
                "baseline_kw",
                "observed_kw",
                "deviation_kw",
                "deviation_pct",
                "z_score",
                "confidence_score",
                "sample_count",
                "panel_state",
                "details",
                "context",
                "created_at",
            },
            "alerts": {
                "alert_id",
                "anomaly_id",
                "site_id",
                "dedupe_key",
                "kind",
                "panel_id",
                "category",
                "severity",
                "status",
                "state",
                "title",
                "message",
                "first_seen_ts",
                "last_seen_ts",
                "detected_at_ts",
                "last_observed_ts",
                "baseline_kw",
                "observed_kw",
                "deviation_kw",
                "deviation_pct",
                "confidence_score",
                "affected_panel_count",
                "evidence_summary",
                "explanation_payload",
                "created_at",
                "updated_at",
                "acknowledged_at",
                "acknowledged_by",
                "acknowledged_note",
                "resolved_at",
                "resolved_by",
                "resolution_note",
            },
            "alert_acknowledgements": {
                "ack_id",
                "alert_id",
                "acknowledged_at",
                "acknowledged_by",
                "previous_status",
                "new_status",
                "note",
            },
        }

        for table_name, columns in expected_columns.items():
            self.assertEqual(set(self.models.Base.metadata.tables[table_name].columns.keys()), columns)

    def test_model_id_column_types_match_migration_int_ids(self):
        id_columns = [
            self.models.SitePowerBaseline.__table__.c.baseline_id,
            self.models.PanelPowerBaseline.__table__.c.baseline_id,
            self.models.Anomaly.__table__.c.anomaly_id,
            self.models.AnomalyEvidence.__table__.c.evidence_id,
            self.models.Alert.__table__.c.alert_id,
            self.models.AlertAcknowledgement.__table__.c.ack_id,
        ]
        for col in id_columns:
            self.assertEqual(col.type.__class__.__name__, "Integer")


if __name__ == "__main__":
    unittest.main()
