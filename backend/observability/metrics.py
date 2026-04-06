import time

from prometheus_client import Counter, Gauge, Histogram  # pyright: ignore[reportMissingImports]
from sqlalchemy import event  # pyright: ignore[reportMissingImports]


API_REQUEST_DURATION_SECONDS = Histogram(
    "solar_api_request_duration_seconds",
    "API request latency in seconds.",
    ["method", "path"],
)

API_REQUEST_STATUS_TOTAL = Counter(
    "solar_api_request_status_total",
    "Total API responses by method/path/status code.",
    ["method", "path", "status_code"],
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "solar_db_query_duration_seconds",
    "Database query duration in seconds.",
    ["operation", "status"],
)

POLL_INGEST_SUCCESS_TOTAL = Counter(
    "solar_poll_ingest_success_total",
    "Total successful poll ingest cycles.",
)

POLL_INGEST_FAILURE_TOTAL = Counter(
    "solar_poll_ingest_failure_total",
    "Total failed poll ingest cycles.",
    ["reason"],
)

INGEST_LAST_SUCCESS_TIMESTAMP_SECONDS = Gauge(
    "solar_ingest_last_success_timestamp_seconds",
    "Unix timestamp of latest successful telemetry ingest.",
)

ALERT_GENERATED_TOTAL = Counter(
    "solar_alert_generated_total",
    "Total generated alerts by kind and severity.",
    ["kind", "severity"],
)


def _statement_operation(statement: str | None) -> str:
    if not statement:
        return "unknown"
    first = statement.strip().split(maxsplit=1)
    if not first:
        return "unknown"
    return first[0].lower()


def bind_db_engine_metrics(engine) -> None:
    if getattr(engine, "_solar_metrics_bound", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del cursor, parameters, executemany
        conn.info.setdefault("_solar_query_start_stack", []).append((time.perf_counter(), _statement_operation(statement)))

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del cursor, statement, parameters, context, executemany
        stack = conn.info.get("_solar_query_start_stack", None)
        if not stack:
            return
        started, operation = stack.pop()
        DB_QUERY_DURATION_SECONDS.labels(operation=operation, status="success").observe(time.perf_counter() - started)

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context):
        stack = exception_context.connection.info.get("_solar_query_start_stack", None)
        if not stack:
            return
        started, operation = stack.pop()
        DB_QUERY_DURATION_SECONDS.labels(operation=operation, status="error").observe(time.perf_counter() - started)

    engine._solar_metrics_bound = True
