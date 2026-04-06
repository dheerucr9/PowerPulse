import os
from urllib.parse import unquote, urlparse


def _as_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _as_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() not in ("0", "false", "no")


def _sqlite_path_from_dsn(dsn: str, fallback: str) -> str:
    if not dsn.startswith("sqlite:///"):
        return fallback
    parsed = urlparse(dsn)
    path = unquote(parsed.path or "")
    return path or fallback


def _default_database_dsn() -> str:
    user = os.environ.get("POSTGRES_USER", "solar")
    password = os.environ.get("POSTGRES_PASSWORD", "solar")
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "solar")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


DB_PATH = os.environ.get("DB_PATH", "/data/solar.db")
DATABASE_DSN = os.environ.get("DATABASE_DSN", _default_database_dsn())
SQLITE_DB_PATH = _sqlite_path_from_dsn(DATABASE_DSN, DB_PATH)

GATEWAY_IP = os.environ.get("GATEWAY_IP")
GATEWAY_USER = os.environ.get("GATEWAY_USER")
GATEWAY_PASS = os.environ.get("GATEWAY_PASS")
GATEWAY_TIMEOUT = _as_int("GATEWAY_TIMEOUT", 20)
POLL_SECONDS = _as_int("POLL_SECONDS", 60)
INTELLIGENCE_SECONDS = _as_int("INTELLIGENCE_SECONDS", 300)

TZ_NAME = os.environ.get("TZ")
LATITUDE = os.environ.get("LATITUDE")
LONGITUDE = os.environ.get("LONGITUDE")

ENABLE_METRICS = _as_bool("ENABLE_METRICS", True)
METRICS_ENABLED = _as_bool("METRICS_ENABLED", ENABLE_METRICS)
WORKER_METRICS_ENABLED = _as_bool("WORKER_METRICS_ENABLED", METRICS_ENABLED)
WORKER_METRICS_PORT = _as_int("WORKER_METRICS_PORT", 9101)
INGEST_FRESHNESS_MAX_AGE_SECONDS = _as_int("INGEST_FRESHNESS_MAX_AGE_SECONDS", max(POLL_SECONDS * 3, 180))

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")
BACKUP_FILE = os.environ.get("BACKUP_FILE", f"{BACKUP_DIR}/solar-backup.sql")
BACKUP_RETENTION_DAYS = _as_int("BACKUP_RETENTION_DAYS", 7)

FRONTEND_API_ORIGIN = os.environ.get("FRONTEND_API_ORIGIN", "http://127.0.0.1:8000")
API_ASSUME_FRONTEND_SAME_ORIGIN = _as_bool("API_ASSUME_FRONTEND_SAME_ORIGIN", True)

# Tesla Wall Connector
WALL_CONNECTOR_IP = os.environ.get("WALL_CONNECTOR_IP")
WALL_CONNECTOR_POLL_SECONDS = _as_int("WALL_CONNECTOR_POLL_SECONDS", 60)
