import os
import sqlite3
import subprocess
import tempfile
import unittest
import importlib
from pathlib import Path
from typing import Sequence


def _alembic_binary() -> str:
    return str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "alembic")


def _run_alembic_upgrade(env: dict[str, str]) -> None:
    subprocess.run(
        [
            _alembic_binary(),
            "-c",
            str(Path(__file__).resolve().parents[1] / "alembic.ini"),
            "upgrade",
            "head",
        ],
        check=True,
        env=env,
    )


def _init_source_sqlite(
    path: str,
    rows: Sequence[tuple[object, ...]],
    panel_rows: Sequence[tuple[object, ...]],
) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE house_raw (
            ts BIGINT,
            production_kw FLOAT,
            consumption_kw FLOAT,
            net_kw FLOAT,
            v_sys FLOAT,
            v_l1 FLOAT,
            v_l2 FLOAT,
            gateway_swver TEXT,
            gateway_ip TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE samples_raw (
            ts BIGINT,
            panel_id TEXT,
            p_kw FLOAT,
            v_ac FLOAT,
            v_dc FLOAT,
            i_dc FLOAT,
            temp_c FLOAT,
            state TEXT,
            serial TEXT,
            gateway_swver TEXT,
            gateway_ip TEXT
        )
        """
    )
    if rows:
        conn.executemany(
            """
            INSERT INTO house_raw
            (ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    if panel_rows:
        conn.executemany(
            """
            INSERT INTO samples_raw
            (ts, panel_id, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial, gateway_swver, gateway_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            panel_rows,
        )
    conn.commit()
    conn.close()


class MigrationToolingTests(unittest.TestCase):
    target_db_path = ""
    source_db_path = ""
    target_dsn = ""

    def setUp(self):
        target_fd, self.target_db_path = tempfile.mkstemp()
        os.close(target_fd)

        source_fd, self.source_db_path = tempfile.mkstemp()
        os.close(source_fd)

        self.target_dsn = f"sqlite+pysqlite:///{self.target_db_path}"
        env = os.environ.copy()
        env["DATABASE_DSN"] = self.target_dsn
        env["DB_PATH"] = self.target_db_path
        env["GATEWAY_IP"] = "127.0.0.1"
        env["GATEWAY_USER"] = "u"
        env["GATEWAY_PASS"] = "p"
        env["TZ"] = "UTC"
        _run_alembic_upgrade(env)

    def tearDown(self):
        for path in (self.target_db_path, self.source_db_path):
            try:
                os.unlink(path)
            except OSError:
                pass

    def _target_counts(self) -> tuple[int, int]:
        conn = sqlite3.connect(self.target_db_path)
        site_count = conn.execute("SELECT COUNT(*) FROM site_power_samples WHERE site_id = 'default'").fetchone()[0]
        panel_count = conn.execute("SELECT COUNT(*) FROM panel_power_samples WHERE site_id = 'default'").fetchone()[0]
        conn.close()
        return int(site_count), int(panel_count)

    def _migrate(self):
        module = importlib.import_module("backend.migrate_sqlite")
        return module.migrate

    def _verify(self):
        module = importlib.import_module("backend.verify_migration")
        return module.verify

    def test_empty_source_db_migrates_as_noop(self):
        _init_source_sqlite(self.source_db_path, rows=[], panel_rows=[])

        result = self._migrate()(sqlite_path=self.source_db_path, target_dsn=self.target_dsn, site_id="default", dry_run=False)
        self.assertEqual(result, 0)
        self.assertEqual(self._target_counts(), (0, 0))

    def test_dry_run_cli_prints_plan_and_exits_zero(self):
        _init_source_sqlite(
            self.source_db_path,
            rows=[(1_700_000_000, 2.1, 1.3, 0.8, 240.0, 120.0, 120.0, "1.0", "127.0.0.1")],
            panel_rows=[(1_700_000_000, "panel-A", 0.9, 121.0, 45.0, 2.0, 36.0, "OK", "A", "1.0", "127.0.0.1")],
        )
        cmd = [
            str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"),
            "-m",
            "backend.migrate_sqlite",
            "--sqlite-path",
            self.source_db_path,
            "--target-dsn",
            self.target_dsn,
            "--dry-run",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("PLAN: site_power_samples rows to process=1", result.stdout)
        self.assertIn("PLAN: panel_power_samples rows to process=1", result.stdout)
        self.assertEqual(self._target_counts(), (0, 0))

    def test_duplicate_source_rows_are_deduped_and_rerun_is_idempotent(self):
        house_rows = [
            (1_700_000_000, 2.1, 1.3, 0.8, 240.0, 120.0, 120.0, "1.0", "127.0.0.1"),
            (1_700_000_000, 2.1, 1.3, 0.8, 240.0, 120.0, 120.0, "1.0", "127.0.0.1"),
            (1_700_000_001, 2.2, 1.4, 0.8, 240.1, 120.1, 120.0, "1.0", "127.0.0.1"),
        ]
        panel_rows = [
            (1_700_000_000, "panel-A", 0.9, 121.0, 45.0, 2.0, 36.0, "OK", "A", "1.0", "127.0.0.1"),
            (1_700_000_000, "panel-A", 0.9, 121.0, 45.0, 2.0, 36.0, "OK", "A", "1.0", "127.0.0.1"),
            (1_700_000_001, "panel-B", 1.1, 122.0, 46.0, 2.1, 37.0, "OK", "B", "1.0", "127.0.0.1"),
        ]
        _init_source_sqlite(self.source_db_path, rows=house_rows, panel_rows=panel_rows)

        first = self._migrate()(sqlite_path=self.source_db_path, target_dsn=self.target_dsn, site_id="default", dry_run=False)
        second = self._migrate()(sqlite_path=self.source_db_path, target_dsn=self.target_dsn, site_id="default", dry_run=False)
        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(self._target_counts(), (2, 2))

        verify_result = self._verify()(sqlite_path=self.source_db_path, target_dsn=self.target_dsn, site_id="default")
        self.assertEqual(verify_result, 0)

    def test_bad_source_path_fails_without_mutating_target(self):
        before_counts = self._target_counts()
        with self.assertRaises(FileNotFoundError):
            self._migrate()(
                sqlite_path=f"{self.source_db_path}.missing",
                target_dsn=self.target_dsn,
                site_id="default",
                dry_run=False,
            )
        self.assertEqual(before_counts, self._target_counts())


if __name__ == "__main__":
    unittest.main()
