from prometheus_client import Counter, Gauge, Histogram  # pyright: ignore[reportMissingImports]


WORKER_JOB_DURATION_SECONDS = Histogram(
    "solar_worker_job_duration_seconds",
    "Worker job execution duration in seconds.",
    ["job_name"],
)

WORKER_JOB_SUCCESSES_TOTAL = Counter(
    "solar_worker_job_success_total",
    "Total successful worker job runs.",
    ["job_name"],
)

WORKER_JOB_FAILURES_TOTAL = Counter(
    "solar_worker_job_failure_total",
    "Total failed worker job runs.",
    ["job_name"],
)

WORKER_JOB_LAST_RUN_TIMESTAMP = Gauge(
    "solar_worker_job_last_run_timestamp_seconds",
    "Unix timestamp for the last worker job attempt.",
    ["job_name"],
)

WORKER_JOB_LAST_SUCCESS_TIMESTAMP = Gauge(
    "solar_worker_job_last_success_timestamp_seconds",
    "Unix timestamp for the last successful worker job run.",
    ["job_name"],
)

WORKER_JOB_LAST_FAILURE_TIMESTAMP = Gauge(
    "solar_worker_job_last_failure_timestamp_seconds",
    "Unix timestamp for the last failed worker job run.",
    ["job_name"],
)
