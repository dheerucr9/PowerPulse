# pyright: reportMissingImports=false

import argparse

from sqlalchemy import create_engine

from . import settings
from .migrate_sqlite import _print_stats
from .migrate_sqlite import _target_stats
from .migrate_sqlite import _validate_count_and_range
from .migrate_sqlite import collect_source_stats


def verify(sqlite_path: str, target_dsn: str, site_id: str = "default") -> int:
    source = collect_source_stats(sqlite_path)
    _print_stats("SOURCE", source)

    engine = create_engine(target_dsn, future=True)
    with engine.connect() as conn:
        target = _target_stats(conn, site_id)
    _print_stats("TARGET", target)
    engine.dispose()

    _validate_count_and_range(source, target)
    print("Verification passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SQLite historical data matches canonical telemetry tables")
    parser.add_argument("--sqlite-path", required=True, help="Path to source SQLite file (e.g. /data/solar.db)")
    parser.add_argument("--site-id", default="default", help="Canonical site_id target (default: default)")
    parser.add_argument("--target-dsn", default=settings.DATABASE_DSN, help="Target SQLAlchemy DSN")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return verify(sqlite_path=args.sqlite_path, target_dsn=args.target_dsn, site_id=args.site_id)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
