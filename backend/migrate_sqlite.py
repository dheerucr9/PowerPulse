# pyright: reportMissingImports=false

import argparse
import sqlite3
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text

from . import settings


@dataclass(frozen=True)
class TableStats:
    count: int
    min_ts: int | None
    max_ts: int | None


@dataclass(frozen=True)
class SourceStats:
    house: TableStats
    panel: TableStats


REQUIRED_COLUMNS = {
    "house_raw": {
        "ts",
        "production_kw",
        "consumption_kw",
        "net_kw",
        "v_sys",
        "v_l1",
        "v_l2",
        "gateway_swver",
        "gateway_ip",
    },
    "samples_raw": {
        "ts",
        "panel_id",
        "p_kw",
        "v_ac",
        "v_dc",
        "i_dc",
        "temp_c",
        "state",
        "serial",
        "gateway_swver",
        "gateway_ip",
    },
}


def _validate_sqlite_path(sqlite_path: str) -> Path:
    path = Path(sqlite_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite source not found: {sqlite_path}")
    if not path.is_file():
        raise ValueError(f"SQLite source is not a file: {sqlite_path}")
    return path


def _open_source(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(row[1]) for row in rows}


def _validate_source_schema(conn: sqlite3.Connection) -> None:
    tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for table_name, required in REQUIRED_COLUMNS.items():
        if table_name not in tables:
            raise ValueError(f"Source SQLite is missing table '{table_name}'")
        columns = _table_columns(conn, table_name)
        missing = sorted(required - columns)
        if missing:
            raise ValueError(f"Source SQLite table '{table_name}' is missing columns: {', '.join(missing)}")


def _table_stats(conn: sqlite3.Connection, table_name: str, key_columns: tuple[str, ...]) -> TableStats:
    partition_cols = ", ".join(key_columns)
    query = f"""
        SELECT COUNT(*) AS c, MIN(ts) AS min_ts, MAX(ts) AS max_ts
        FROM (
            SELECT
                ts,
                ROW_NUMBER() OVER (PARTITION BY {partition_cols} ORDER BY rowid ASC) AS rn
            FROM {table_name}
        ) q
        WHERE q.rn = 1
    """
    row = conn.execute(query).fetchone()
    return TableStats(count=int(row[0] or 0), min_ts=row[1], max_ts=row[2])


def collect_source_stats(sqlite_path: str) -> SourceStats:
    path = _validate_sqlite_path(sqlite_path)
    conn = _open_source(path)
    try:
        _validate_source_schema(conn)
        return SourceStats(
            house=_table_stats(conn, "house_raw", ("ts",)),
            panel=_table_stats(conn, "samples_raw", ("panel_id", "ts")),
        )
    finally:
        conn.close()


def _target_stats(conn, site_id: str) -> SourceStats:
    site_row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS c, MIN(ts) AS min_ts, MAX(ts) AS max_ts
            FROM site_power_samples
            WHERE site_id = :site_id
            """
        ),
        {"site_id": site_id},
    ).mappings().one()
    panel_row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS c, MIN(ts) AS min_ts, MAX(ts) AS max_ts
            FROM panel_power_samples
            WHERE site_id = :site_id
            """
        ),
        {"site_id": site_id},
    ).mappings().one()
    return SourceStats(
        house=TableStats(count=int(site_row["c"]), min_ts=site_row["min_ts"], max_ts=site_row["max_ts"]),
        panel=TableStats(count=int(panel_row["c"]), min_ts=panel_row["min_ts"], max_ts=panel_row["max_ts"]),
    )


def _print_stats(label: str, stats: SourceStats) -> None:
    print(f"{label} house_raw/site_power_samples: count={stats.house.count} min_ts={stats.house.min_ts} max_ts={stats.house.max_ts}")
    print(f"{label} samples_raw/panel_power_samples: count={stats.panel.count} min_ts={stats.panel.min_ts} max_ts={stats.panel.max_ts}")


def _validate_count_and_range(source: SourceStats, target: SourceStats) -> None:
    checks = [
        ("site_power_samples count", source.house.count, target.house.count),
        ("panel_power_samples count", source.panel.count, target.panel.count),
        ("site_power_samples min_ts", source.house.min_ts, target.house.min_ts),
        ("site_power_samples max_ts", source.house.max_ts, target.house.max_ts),
        ("panel_power_samples min_ts", source.panel.min_ts, target.panel.min_ts),
        ("panel_power_samples max_ts", source.panel.max_ts, target.panel.max_ts),
    ]
    mismatches = [f"{name}: source={src} target={dst}" for name, src, dst in checks if src != dst]
    if mismatches:
        joined = "; ".join(mismatches)
        raise RuntimeError(f"Migration verification failed: {joined}")


def _chunked(iterable, size: int):
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            return
        yield batch


def _deduped_house_rows(source_conn: sqlite3.Connection):
    source_conn.row_factory = sqlite3.Row
    rows = source_conn.execute(
        """
        SELECT
            ts,
            production_kw,
            consumption_kw,
            net_kw,
            v_sys,
            v_l1,
            v_l2,
            gateway_swver,
            gateway_ip
        FROM (
            SELECT
                ts,
                production_kw,
                consumption_kw,
                net_kw,
                v_sys,
                v_l1,
                v_l2,
                gateway_swver,
                gateway_ip,
                ROW_NUMBER() OVER (PARTITION BY ts ORDER BY rowid ASC) AS rn
            FROM house_raw
        ) q
        WHERE q.rn = 1
        ORDER BY ts ASC
        """
    )
    for row in rows:
        yield {
            "ts": row["ts"],
            "production_kw": row["production_kw"],
            "consumption_kw": row["consumption_kw"],
            "net_kw": row["net_kw"],
            "v_sys": row["v_sys"],
            "v_l1": row["v_l1"],
            "v_l2": row["v_l2"],
            "gateway_swver": row["gateway_swver"],
            "gateway_ip": row["gateway_ip"],
        }


def _deduped_panel_rows(source_conn: sqlite3.Connection):
    source_conn.row_factory = sqlite3.Row
    rows = source_conn.execute(
        """
        SELECT
            panel_id,
            ts,
            p_kw,
            v_ac,
            v_dc,
            i_dc,
            temp_c,
            state,
            serial,
            gateway_swver,
            gateway_ip
        FROM (
            SELECT
                panel_id,
                ts,
                p_kw,
                v_ac,
                v_dc,
                i_dc,
                temp_c,
                state,
                serial,
                gateway_swver,
                gateway_ip,
                ROW_NUMBER() OVER (PARTITION BY panel_id, ts ORDER BY rowid ASC) AS rn
            FROM samples_raw
        ) q
        WHERE q.rn = 1
        ORDER BY panel_id ASC, ts ASC
        """
    )
    for row in rows:
        yield {
            "panel_id": row["panel_id"],
            "ts": row["ts"],
            "p_kw": row["p_kw"],
            "v_ac": row["v_ac"],
            "v_dc": row["v_dc"],
            "i_dc": row["i_dc"],
            "temp_c": row["temp_c"],
            "state": row["state"],
            "serial": row["serial"],
            "gateway_swver": row["gateway_swver"],
            "gateway_ip": row["gateway_ip"],
        }


def migrate(sqlite_path: str, target_dsn: str, site_id: str = "default", dry_run: bool = False) -> int:
    source = collect_source_stats(sqlite_path)
    _print_stats("SOURCE", source)

    engine = create_engine(target_dsn, future=True)
    with engine.connect() as conn:
        before = _target_stats(conn, site_id)
        _print_stats("TARGET BEFORE", before)

    print("PLAN: upsert source rows into canonical telemetry tables")
    print(f"PLAN: site_power_samples rows to process={source.house.count}")
    print(f"PLAN: panel_power_samples rows to process={source.panel.count}")

    if dry_run:
        print("Dry-run requested; no writes performed.")
        engine.dispose()
        return 0

    source_conn = _open_source(_validate_sqlite_path(sqlite_path))
    try:
        _validate_source_schema(source_conn)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO sites (site_id)
                    VALUES (:site_id)
                    ON CONFLICT (site_id) DO NOTHING
                    """
                ),
                {"site_id": site_id},
            )

            for batch in _chunked(_deduped_house_rows(source_conn), 5_000):
                payload = [{**row, "site_id": site_id} for row in batch]
                conn.execute(
                    text(
                        """
                        INSERT INTO site_power_samples
                        (site_id, ts, production_kw, consumption_kw, net_kw, v_sys, v_l1, v_l2, gateway_swver, gateway_ip)
                        VALUES
                        (:site_id, :ts, :production_kw, :consumption_kw, :net_kw, :v_sys, :v_l1, :v_l2, :gateway_swver, :gateway_ip)
                        ON CONFLICT (site_id, ts) DO NOTHING
                        """
                    ),
                    payload,
                )

            for batch in _chunked(_deduped_panel_rows(source_conn), 5_000):
                payload = [{**row, "site_id": site_id} for row in batch]
                conn.execute(
                    text(
                        """
                        INSERT INTO panel_power_samples
                        (site_id, panel_id, ts, p_kw, v_ac, v_dc, i_dc, temp_c, state, serial, gateway_swver, gateway_ip)
                        VALUES
                        (:site_id, :panel_id, :ts, :p_kw, :v_ac, :v_dc, :i_dc, :temp_c, :state, :serial, :gateway_swver, :gateway_ip)
                        ON CONFLICT (site_id, panel_id, ts) DO NOTHING
                        """
                    ),
                    payload,
                )
    finally:
        source_conn.close()

    with engine.connect() as conn:
        after = _target_stats(conn, site_id)
    _print_stats("TARGET AFTER", after)
    _validate_count_and_range(source, after)
    print("Migration complete and verified.")
    engine.dispose()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill canonical telemetry tables from historical SQLite data")
    parser.add_argument("--sqlite-path", required=True, help="Path to source SQLite file (e.g. /data/solar.db)")
    parser.add_argument("--site-id", default="default", help="Canonical site_id target (default: default)")
    parser.add_argument("--target-dsn", default=settings.DATABASE_DSN, help="Target SQLAlchemy DSN")
    parser.add_argument("--dry-run", action="store_true", help="Only print source/target stats and plan; do not write")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return migrate(
            sqlite_path=args.sqlite_path,
            target_dsn=args.target_dsn,
            site_id=args.site_id,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
