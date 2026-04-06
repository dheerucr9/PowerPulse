import importlib
import os
import tempfile
import time
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from requests.exceptions import RequestException  # pyright: ignore[reportMissingModuleSource]

worker_metrics_module = importlib.import_module("backend.worker_metrics")
WORKER_JOB_DURATION_SECONDS = worker_metrics_module.WORKER_JOB_DURATION_SECONDS
WORKER_JOB_FAILURES_TOTAL = worker_metrics_module.WORKER_JOB_FAILURES_TOTAL
WORKER_JOB_LAST_FAILURE_TIMESTAMP = worker_metrics_module.WORKER_JOB_LAST_FAILURE_TIMESTAMP
WORKER_JOB_LAST_RUN_TIMESTAMP = worker_metrics_module.WORKER_JOB_LAST_RUN_TIMESTAMP
WORKER_JOB_LAST_SUCCESS_TIMESTAMP = worker_metrics_module.WORKER_JOB_LAST_SUCCESS_TIMESTAMP
WORKER_JOB_SUCCESSES_TOTAL = worker_metrics_module.WORKER_JOB_SUCCESSES_TOTAL


@contextmanager
def worker_test_env():
    names = ["GATEWAY_IP", "GATEWAY_USER", "GATEWAY_PASS", "TZ", "DATABASE_DSN", "DB_PATH"]
    backup = {name: os.environ.get(name) for name in names}
    tmp_db = tempfile.NamedTemporaryFile(delete=False)
    tmp_db_path = tmp_db.name
    tmp_db.close()
    try:
        os.environ["GATEWAY_IP"] = "127.0.0.1"
        os.environ["GATEWAY_USER"] = "u"
        os.environ["GATEWAY_PASS"] = "p"
        os.environ["TZ"] = "UTC"
        os.environ["DATABASE_DSN"] = f"sqlite+pysqlite:///{tmp_db_path}"
        os.environ["DB_PATH"] = tmp_db_path
        yield
    finally:
        for name, value in backup.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        try:
            os.unlink(tmp_db_path)
        except OSError:
            pass


def _load_worker_modules():
    poller = importlib.reload(importlib.import_module("backend.poller"))
    worker_entry = importlib.reload(importlib.import_module("backend.worker_entry"))
    return poller, worker_entry


class WorkerSchedulerTests(unittest.TestCase):
    def test_register_jobs_is_idempotent_and_prevents_duplicates(self):
        with worker_test_env():
            _, worker_entry = _load_worker_modules()
            scheduler_module = importlib.import_module("apscheduler.schedulers.background")
            scheduler = scheduler_module.BackgroundScheduler(timezone="UTC")
            try:
                first = worker_entry.register_jobs(scheduler)
                second = worker_entry.register_jobs(scheduler)

                self.assertEqual(
                    first,
                    {
                        worker_entry.POLL_JOB_ID: True,
                        worker_entry.INTELLIGENCE_JOB_ID: True,
                    },
                )
                self.assertEqual(
                    second,
                    {
                        worker_entry.POLL_JOB_ID: False,
                        worker_entry.INTELLIGENCE_JOB_ID: False,
                    },
                )
                self.assertEqual({job.id for job in scheduler.get_jobs()}, {"poll-ingest", "periodic-intelligence"})
            finally:
                if scheduler.running:
                    scheduler.shutdown(wait=False)

    def test_run_job_with_metrics_records_failure_and_timestamps(self):
        with worker_test_env():
            _, worker_entry = _load_worker_modules()
            job_name = f"failing-job-{time.time_ns()}"

            def _boom():
                raise RuntimeError("failure")

            with self.assertRaises(RuntimeError):
                worker_entry.run_job_with_metrics(job_name, _boom)

            self.assertGreaterEqual(WORKER_JOB_FAILURES_TOTAL.labels(job_name=job_name)._value.get(), 1)
            self.assertEqual(WORKER_JOB_SUCCESSES_TOTAL.labels(job_name=job_name)._value.get(), 0)
            self.assertGreater(WORKER_JOB_LAST_RUN_TIMESTAMP.labels(job_name=job_name)._value.get(), 0)
            self.assertGreater(WORKER_JOB_LAST_FAILURE_TIMESTAMP.labels(job_name=job_name)._value.get(), 0)
            self.assertEqual(WORKER_JOB_LAST_SUCCESS_TIMESTAMP.labels(job_name=job_name)._value.get(), 0)

            duration_count = 0.0
            for metric in WORKER_JOB_DURATION_SECONDS.collect():
                for sample in metric.samples:
                    if sample.name.endswith("_count") and sample.labels.get("job_name") == job_name:
                        duration_count = sample.value
            self.assertGreaterEqual(duration_count, 1)

    def test_fetch_devices_returns_none_on_request_failure(self):
        with worker_test_env():
            poller, _ = _load_worker_modules()
            with patch("backend.poller.requests.Session") as session_factory:
                session = session_factory.return_value
                session.get.side_effect = RequestException("gateway-down")

                result = poller.fetch_devices()

            self.assertIsNone(result)
            self.assertGreaterEqual(session.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
