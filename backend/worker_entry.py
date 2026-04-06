import logging
import signal
import threading
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler  # pyright: ignore[reportMissingImports]
from apscheduler.triggers.interval import IntervalTrigger  # pyright: ignore[reportMissingImports]
from prometheus_client import start_http_server  # pyright: ignore[reportMissingImports]

from . import poller
from . import db as worker_db
from .jobs.production_monitor import run_production_monitor_cycle
from . import settings
from .observability import configure_json_logging
from .worker_metrics import (
    WORKER_JOB_DURATION_SECONDS,
    WORKER_JOB_FAILURES_TOTAL,
    WORKER_JOB_LAST_FAILURE_TIMESTAMP,
    WORKER_JOB_LAST_RUN_TIMESTAMP,
    WORKER_JOB_LAST_SUCCESS_TIMESTAMP,
    WORKER_JOB_SUCCESSES_TOTAL,
)


configure_json_logging(service="worker")
log = logging.getLogger("worker")
_stop = threading.Event()
_scheduler_lock = threading.Lock()

POLL_JOB_ID = "poll-ingest"
CHARGER_POLL_JOB_ID = "charger-poll-ingest"
INTELLIGENCE_JOB_ID = "periodic-intelligence"
PRODUCTION_MONITOR_JOB_ID = "production-monitor"


def _request_stop(_signum, _frame):
    _stop.set()


def run_job_with_metrics(job_name: str, job_callable):
    started_at = time.perf_counter()
    now = datetime.now(tz=timezone.utc).timestamp()
    WORKER_JOB_LAST_RUN_TIMESTAMP.labels(job_name=job_name).set(now)
    try:
        job_callable()
    except Exception:
        WORKER_JOB_FAILURES_TOTAL.labels(job_name=job_name).inc()
        WORKER_JOB_LAST_FAILURE_TIMESTAMP.labels(job_name=job_name).set(now)
        raise
    else:
        WORKER_JOB_SUCCESSES_TOTAL.labels(job_name=job_name).inc()
        WORKER_JOB_LAST_SUCCESS_TIMESTAMP.labels(job_name=job_name).set(now)
    finally:
        elapsed = time.perf_counter() - started_at
        WORKER_JOB_DURATION_SECONDS.labels(job_name=job_name).observe(elapsed)


def _register_interval_job(scheduler: BackgroundScheduler, job_id: str, seconds: int, func) -> bool:
    with _scheduler_lock:
        if scheduler.get_job(job_id):
            log.info("Worker job '%s' already registered; skipping", job_id)
            return False
        scheduler.add_job(
            func,
            trigger=IntervalTrigger(seconds=seconds),
            id=job_id,
            coalesce=True,
            max_instances=1,
            replace_existing=False,
            next_run_time=datetime.now(tz=timezone.utc),
            misfire_grace_time=max(seconds, 1),
        )
        log.info("Registered worker job '%s' on %ss interval", job_id, seconds)
        return True


def _run_monitor():
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    last_poll_ts = poller.get_last_successful_poll_ts()
    gateway_failure_seconds_ago = (now_ts - last_poll_ts) if last_poll_ts is not None else None
    with worker_db.get_session() as session:
        run_production_monitor_cycle(
            session,
            now_ts=now_ts,
            gateway_failure_seconds_ago=gateway_failure_seconds_ago,
        )


def register_jobs(scheduler: BackgroundScheduler) -> dict[str, bool]:
    registrations = {
        POLL_JOB_ID: _register_interval_job(
            scheduler=scheduler,
            job_id=POLL_JOB_ID,
            seconds=settings.POLL_SECONDS,
            func=lambda: run_job_with_metrics(POLL_JOB_ID, poller.ingest),
        ),
        INTELLIGENCE_JOB_ID: _register_interval_job(
            scheduler=scheduler,
            job_id=INTELLIGENCE_JOB_ID,
            seconds=settings.INTELLIGENCE_SECONDS,
            func=lambda: run_job_with_metrics(INTELLIGENCE_JOB_ID, poller.run_periodic_intelligence_cycle),
        ),
        PRODUCTION_MONITOR_JOB_ID: _register_interval_job(
            scheduler=scheduler,
            job_id=PRODUCTION_MONITOR_JOB_ID,
            seconds=60,
            func=lambda: run_job_with_metrics(PRODUCTION_MONITOR_JOB_ID, _run_monitor),
        ),
    }

    if settings.WALL_CONNECTOR_IP:
        registrations[CHARGER_POLL_JOB_ID] = _register_interval_job(
            scheduler=scheduler,
            job_id=CHARGER_POLL_JOB_ID,
            seconds=settings.WALL_CONNECTOR_POLL_SECONDS,
            func=lambda: run_job_with_metrics(CHARGER_POLL_JOB_ID, poller.ingest_charger),
        )
    else:
        log.info("WALL_CONNECTOR_IP not configured; charger poll job disabled")
        registrations[CHARGER_POLL_JOB_ID] = False

    return registrations


def _start_metrics_server():
    if not settings.WORKER_METRICS_ENABLED:
        return
    start_http_server(settings.WORKER_METRICS_PORT)
    log.info("Worker metrics server listening on port %s", settings.WORKER_METRICS_PORT)


def main():
    _start_metrics_server()
    scheduler = BackgroundScheduler(timezone=poller.TZ)
    try:
        registration = register_jobs(scheduler)
        scheduler.start()
        log.info("Worker scheduler started with jobs: %s", registration)
        while not _stop.wait(1):
            continue
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            log.info("Worker scheduler stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    main()
