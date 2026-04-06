import json
from typing import Any

from sqlalchemy import text  # pyright: ignore[reportMissingImports]


class ConsumptionIntelligenceRepository:
    def __init__(self, executor: Any):
        self._executor = executor

    @property
    def executor(self) -> Any:
        return self._executor

    def fetch_latest_site_sample(self, site_id: str) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT ts, production_kw, consumption_kw, net_kw
                FROM house_raw
                ORDER BY ts DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        return dict(row) if row else None

    def fetch_site_samples_between(self, start_ts: int, end_ts: int) -> list[dict[str, Any]]:
        rows = self._executor.execute(
            text(
                """
                SELECT ts, production_kw, consumption_kw, net_kw
                FROM house_raw
                WHERE ts BETWEEN :start_ts AND :end_ts
                ORDER BY ts ASC
                """
            ),
            {"start_ts": start_ts, "end_ts": end_ts},
        ).mappings().all()
        return [dict(row) for row in rows]

    def fetch_consumption_bucket_history(self, bucket_of_day: int, start_ts: int, end_ts: int) -> list[dict[str, Any]]:
        rows = self._executor.execute(
            text(
                """
                SELECT ts, production_kw, consumption_kw, net_kw
                FROM house_raw
                WHERE ts BETWEEN :start_ts AND :end_ts
                  AND (CAST(ts / 300 AS INTEGER) * 300) % 86400 = :bucket_of_day
                  AND consumption_kw IS NOT NULL
                ORDER BY ts ASC
                """
            ),
            {
                "bucket_of_day": bucket_of_day,
                "start_ts": start_ts,
                "end_ts": end_ts,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def upsert_site_baseline(
        self,
        *,
        site_id: str,
        metric: str,
        bucket_start_ts: int,
        bucket_granularity_seconds: int,
        baseline_kw: float,
        baseline_stddev_kw: float | None,
        sample_count: int,
        confidence_score: float,
        model_version: str,
    ) -> None:
        self._executor.execute(
            text(
                """
                INSERT INTO site_power_baselines
                (
                    site_id,
                    metric,
                    bucket_start_ts,
                    bucket_granularity_seconds,
                    baseline_kw,
                    baseline_stddev_kw,
                    sample_count,
                    confidence_score,
                    model_version
                )
                VALUES
                (
                    :site_id,
                    :metric,
                    :bucket_start_ts,
                    :bucket_granularity_seconds,
                    :baseline_kw,
                    :baseline_stddev_kw,
                    :sample_count,
                    :confidence_score,
                    :model_version
                )
                ON CONFLICT (site_id, metric, bucket_start_ts, bucket_granularity_seconds)
                DO UPDATE SET
                    baseline_kw = excluded.baseline_kw,
                    baseline_stddev_kw = excluded.baseline_stddev_kw,
                    sample_count = excluded.sample_count,
                    confidence_score = excluded.confidence_score,
                    model_version = excluded.model_version,
                    computed_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "site_id": site_id,
                "metric": metric,
                "bucket_start_ts": bucket_start_ts,
                "bucket_granularity_seconds": bucket_granularity_seconds,
                "baseline_kw": baseline_kw,
                "baseline_stddev_kw": baseline_stddev_kw,
                "sample_count": sample_count,
                "confidence_score": confidence_score,
                "model_version": model_version,
            },
        )

    def fetch_site_baseline(self, site_id: str, metric: str, bucket_start_ts: int, bucket_granularity_seconds: int) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT baseline_id, baseline_kw, baseline_stddev_kw, sample_count, confidence_score, model_version
                FROM site_power_baselines
                WHERE site_id = :site_id
                  AND metric = :metric
                  AND bucket_start_ts = :bucket_start_ts
                  AND bucket_granularity_seconds = :bucket_granularity_seconds
                """
            ),
            {
                "site_id": site_id,
                "metric": metric,
                "bucket_start_ts": bucket_start_ts,
                "bucket_granularity_seconds": bucket_granularity_seconds,
            },
        ).mappings().first()
        return dict(row) if row else None

    def fetch_existing_site_anomaly(self, site_id: str, metric: str, sample_ts: int, direction: str) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT anomaly_id
                FROM anomalies
                WHERE site_id = :site_id
                  AND panel_id IS NULL
                  AND metric = :metric
                  AND sample_ts = :sample_ts
                  AND direction = :direction
                LIMIT 1
                """
            ),
            {
                "site_id": site_id,
                "metric": metric,
                "sample_ts": sample_ts,
                "direction": direction,
            },
        ).mappings().first()
        return dict(row) if row else None

    def insert_anomaly(
        self,
        *,
        site_id: str,
        panel_id: str | None,
        metric: str,
        source: str,
        direction: str,
        severity: str,
        detected_at_ts: int,
        sample_ts: int,
        bucket_start_ts: int,
        bucket_end_ts: int,
        baseline_kw: float,
        observed_kw: float,
        deviation_kw: float,
        deviation_pct: float | None,
        z_score: float | None,
        confidence_score: float,
        sample_count: int,
        panel_state: str | None,
        explanation: str,
        evidence: dict[str, Any],
    ) -> int:
        row = self._executor.execute(
            text(
                """
                INSERT INTO anomalies
                (
                    site_id,
                    panel_id,
                    metric,
                    source,
                    direction,
                    severity,
                    detected_at_ts,
                    sample_ts,
                    bucket_start_ts,
                    bucket_end_ts,
                    baseline_kw,
                    observed_kw,
                    deviation_kw,
                    deviation_pct,
                    z_score,
                    confidence_score,
                    sample_count,
                    panel_state,
                    explanation,
                    evidence
                )
                VALUES
                (
                    :site_id,
                    :panel_id,
                    :metric,
                    :source,
                    :direction,
                    :severity,
                    :detected_at_ts,
                    :sample_ts,
                    :bucket_start_ts,
                    :bucket_end_ts,
                    :baseline_kw,
                    :observed_kw,
                    :deviation_kw,
                    :deviation_pct,
                    :z_score,
                    :confidence_score,
                    :sample_count,
                    :panel_state,
                    :explanation,
                    :evidence
                )
                RETURNING anomaly_id
                """
            ),
            {
                "site_id": site_id,
                "panel_id": panel_id,
                "metric": metric,
                "source": source,
                "direction": direction,
                "severity": severity,
                "detected_at_ts": detected_at_ts,
                "sample_ts": sample_ts,
                "bucket_start_ts": bucket_start_ts,
                "bucket_end_ts": bucket_end_ts,
                "baseline_kw": baseline_kw,
                "observed_kw": observed_kw,
                "deviation_kw": deviation_kw,
                "deviation_pct": deviation_pct,
                "z_score": z_score,
                "confidence_score": confidence_score,
                "sample_count": sample_count,
                "panel_state": panel_state,
                "explanation": explanation,
                "evidence": json.dumps(evidence),
            },
        ).mappings().first()
        return int(row["anomaly_id"])

    def insert_anomaly_evidence(
        self,
        *,
        anomaly_id: int,
        site_id: str,
        panel_id: str | None,
        evidence_type: str,
        reference_ts: int | None,
        window_start_ts: int | None,
        window_end_ts: int | None,
        metric: str | None,
        baseline_kw: float | None,
        observed_kw: float | None,
        deviation_kw: float | None,
        deviation_pct: float | None,
        z_score: float | None,
        confidence_score: float | None,
        sample_count: int | None,
        panel_state: str | None,
        details: str | None,
        context: dict[str, Any],
    ) -> None:
        self._executor.execute(
            text(
                """
                INSERT INTO anomaly_evidence
                (
                    anomaly_id,
                    site_id,
                    panel_id,
                    evidence_type,
                    reference_ts,
                    window_start_ts,
                    window_end_ts,
                    metric,
                    baseline_kw,
                    observed_kw,
                    deviation_kw,
                    deviation_pct,
                    z_score,
                    confidence_score,
                    sample_count,
                    panel_state,
                    details,
                    context
                )
                VALUES
                (
                    :anomaly_id,
                    :site_id,
                    :panel_id,
                    :evidence_type,
                    :reference_ts,
                    :window_start_ts,
                    :window_end_ts,
                    :metric,
                    :baseline_kw,
                    :observed_kw,
                    :deviation_kw,
                    :deviation_pct,
                    :z_score,
                    :confidence_score,
                    :sample_count,
                    :panel_state,
                    :details,
                    :context
                )
                """
            ),
            {
                "anomaly_id": anomaly_id,
                "site_id": site_id,
                "panel_id": panel_id,
                "evidence_type": evidence_type,
                "reference_ts": reference_ts,
                "window_start_ts": window_start_ts,
                "window_end_ts": window_end_ts,
                "metric": metric,
                "baseline_kw": baseline_kw,
                "observed_kw": observed_kw,
                "deviation_kw": deviation_kw,
                "deviation_pct": deviation_pct,
                "z_score": z_score,
                "confidence_score": confidence_score,
                "sample_count": sample_count,
                "panel_state": panel_state,
                "details": details,
                "context": json.dumps(context),
            },
        )
