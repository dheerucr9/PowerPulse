# pyright: reportMissingImports=false

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text


@dataclass
class ReadinessReport:
    ok: bool
    checks: dict[str, Any]
    last_ingest_ts: int | None


def _fetch_last_ingest_ts(conn) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT MAX(ts) AS last_ts
            FROM (
                SELECT MAX(ts) AS ts FROM house_raw
                UNION ALL
                SELECT MAX(ts) AS ts FROM samples_raw
                UNION ALL
                SELECT MAX(ts) AS ts FROM site_power_samples
                UNION ALL
                SELECT MAX(ts) AS ts FROM panel_power_samples
            ) ingest
            """
        )
    ).mappings().one()
    value = row.get("last_ts")
    return int(value) if value is not None else None


def build_readiness_report(*, get_connection, max_ingest_age_seconds: int) -> ReadinessReport:
    checks: dict[str, Any] = {
        "database": False,
        "migrations": False,
        "ingest_fresh": False,
    }
    last_ingest_ts: int | None = None

    try:
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
            checks["database"] = True

            try:
                migration_row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).mappings().first()
                checks["migrations"] = migration_row is not None and bool(migration_row.get("version_num"))
            except Exception:
                checks["migrations"] = False

            try:
                last_ingest_ts = _fetch_last_ingest_ts(conn)
                now = int(time.time())
                checks["ingest_fresh"] = (
                    last_ingest_ts is not None and (now - last_ingest_ts) <= max_ingest_age_seconds
                )
            except Exception:
                checks["ingest_fresh"] = False
    except Exception:
        checks["database"] = False
        checks["migrations"] = False
        checks["ingest_fresh"] = False

    return ReadinessReport(ok=all(bool(v) for v in checks.values()), checks=checks, last_ingest_ts=last_ingest_ts)
