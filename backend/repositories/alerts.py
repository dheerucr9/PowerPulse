import json
from datetime import datetime
from typing import Any

from sqlalchemy import text  # pyright: ignore[reportMissingImports]


class AlertsRepository:
    def __init__(self, executor: Any):
        self._executor = executor

    def fetch_active_alert_by_dedupe_key(self, dedupe_key: str) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT *
                FROM alerts
                WHERE dedupe_key = :dedupe_key
                  AND status IN ('open', 'acknowledged')
                ORDER BY alert_id ASC
                LIMIT 1
                """
            ),
            {"dedupe_key": dedupe_key},
        ).mappings().first()
        return self._coerce_alert_row(dict(row)) if row else None

    @staticmethod
    def _coerce_json(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        if isinstance(value, dict):
            return value
        return {}

    def _coerce_alert_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["explanation_payload"] = self._coerce_json(row.get("explanation_payload"))
        return row

    def _coerce_anomaly_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["evidence"] = self._coerce_json(row.get("evidence"))
        return row

    def _coerce_anomaly_evidence_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["context"] = self._coerce_json(row.get("context"))
        return row

    def insert_alert(
        self,
        *,
        anomaly_id: int | None,
        site_id: str,
        panel_id: str | None,
        dedupe_key: str,
        kind: str,
        category: str,
        severity: str,
        title: str,
        message: str,
        first_seen_ts: int,
        last_seen_ts: int,
        baseline_kw: float | None,
        observed_kw: float | None,
        deviation_kw: float | None,
        deviation_pct: float | None,
        confidence_score: float | None,
        affected_panel_count: int | None,
        evidence_summary: str | None,
        explanation_payload: dict[str, Any],
    ) -> int:
        row = self._executor.execute(
            text(
                """
                INSERT INTO alerts
                (
                    anomaly_id,
                    site_id,
                    panel_id,
                    dedupe_key,
                    kind,
                    category,
                    severity,
                    status,
                    state,
                    title,
                    message,
                    first_seen_ts,
                    last_seen_ts,
                    detected_at_ts,
                    last_observed_ts,
                    baseline_kw,
                    observed_kw,
                    deviation_kw,
                    deviation_pct,
                    confidence_score,
                    affected_panel_count,
                    evidence_summary,
                    explanation_payload
                )
                VALUES
                (
                    :anomaly_id,
                    :site_id,
                    :panel_id,
                    :dedupe_key,
                    :kind,
                    :category,
                    :severity,
                    'open',
                    NULL,
                    :title,
                    :message,
                    :first_seen_ts,
                    :last_seen_ts,
                    :detected_at_ts,
                    :last_observed_ts,
                    :baseline_kw,
                    :observed_kw,
                    :deviation_kw,
                    :deviation_pct,
                    :confidence_score,
                    :affected_panel_count,
                    :evidence_summary,
                    :explanation_payload
                )
                RETURNING alert_id
                """
            ),
            {
                "anomaly_id": anomaly_id,
                "site_id": site_id,
                "panel_id": panel_id,
                "dedupe_key": dedupe_key,
                "kind": kind,
                "category": category,
                "severity": severity,
                "title": title,
                "message": message,
                "first_seen_ts": first_seen_ts,
                "last_seen_ts": last_seen_ts,
                "detected_at_ts": first_seen_ts,
                "last_observed_ts": last_seen_ts,
                "baseline_kw": baseline_kw,
                "observed_kw": observed_kw,
                "deviation_kw": deviation_kw,
                "deviation_pct": deviation_pct,
                "confidence_score": confidence_score,
                "affected_panel_count": affected_panel_count,
                "evidence_summary": evidence_summary,
                "explanation_payload": json.dumps(explanation_payload),
            },
        ).mappings().first()
        return int(row["alert_id"])

    def update_existing_alert_observation(
        self,
        *,
        alert_id: int,
        anomaly_id: int | None,
        severity: str,
        last_seen_ts: int,
        baseline_kw: float | None,
        observed_kw: float | None,
        deviation_kw: float | None,
        deviation_pct: float | None,
        confidence_score: float | None,
        affected_panel_count: int | None,
        evidence_summary: str | None,
        explanation_payload: dict[str, Any],
    ) -> None:
        self._executor.execute(
            text(
                """
                UPDATE alerts
                SET anomaly_id = :anomaly_id,
                    severity = :severity,
                    last_seen_ts = :last_seen_ts,
                    last_observed_ts = :last_observed_ts,
                    baseline_kw = :baseline_kw,
                    observed_kw = :observed_kw,
                    deviation_kw = :deviation_kw,
                    deviation_pct = :deviation_pct,
                    confidence_score = :confidence_score,
                    affected_panel_count = :affected_panel_count,
                    evidence_summary = :evidence_summary,
                    explanation_payload = :explanation_payload,
                    updated_at = CURRENT_TIMESTAMP
                WHERE alert_id = :alert_id
                """
            ),
            {
                "alert_id": alert_id,
                "anomaly_id": anomaly_id,
                "severity": severity,
                "last_seen_ts": last_seen_ts,
                "last_observed_ts": last_seen_ts,
                "baseline_kw": baseline_kw,
                "observed_kw": observed_kw,
                "deviation_kw": deviation_kw,
                "deviation_pct": deviation_pct,
                "confidence_score": confidence_score,
                "affected_panel_count": affected_panel_count,
                "evidence_summary": evidence_summary,
                "explanation_payload": json.dumps(explanation_payload),
            },
        )

    def fetch_alert_by_id(self, alert_id: int) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT *
                FROM alerts
                WHERE alert_id = :alert_id
                LIMIT 1
                """
            ),
            {"alert_id": alert_id},
        ).mappings().first()
        return self._coerce_alert_row(dict(row)) if row else None

    def list_alerts(
        self,
        *,
        status: str | None,
        kind: str | None,
        severity: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            conditions.append("status = :status")
            params["status"] = status
        if kind is not None:
            conditions.append("kind = :kind")
            params["kind"] = kind
        if severity is not None:
            conditions.append("severity = :severity")
            params["severity"] = severity

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._executor.execute(
            text(
                f"""
                SELECT *
                FROM alerts
                {where_clause}
                ORDER BY last_seen_ts DESC,
                         CASE severity
                             WHEN 'critical' THEN 0
                             WHEN 'warning' THEN 1
                             ELSE 2
                         END ASC,
                         alert_id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [self._coerce_alert_row(dict(row)) for row in rows]

    def count_alerts(
        self,
        *,
        status: str | None,
        kind: str | None,
        severity: str | None,
    ) -> int:
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if status is not None:
            conditions.append("status = :status")
            params["status"] = status
        if kind is not None:
            conditions.append("kind = :kind")
            params["kind"] = kind
        if severity is not None:
            conditions.append("severity = :severity")
            params["severity"] = severity

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self._executor.execute(
            text(
                f"""
                SELECT COUNT(*) AS c
                FROM alerts
                {where_clause}
                """
            ),
            params,
        ).mappings().one()
        return int(row["c"])

    def count_open_alerts_grouped(self, *, field: str) -> dict[str, int]:
        if field not in {"kind", "severity"}:
            raise ValueError("field must be one of kind or severity")
        rows = self._executor.execute(
            text(
                f"""
                SELECT {field} AS key, COUNT(*) AS c
                FROM alerts
                WHERE status = 'open'
                GROUP BY {field}
                """
            )
        ).mappings().all()
        return {str(row["key"]): int(row["c"]) for row in rows}

    def fetch_latest_alert_for_kind(self, *, kind: str) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT alert_id, kind, severity, status, title, message, last_seen_ts, evidence_summary
                FROM alerts
                WHERE kind = :kind
                ORDER BY last_seen_ts DESC, alert_id DESC
                LIMIT 1
                """
            ),
            {"kind": kind},
        ).mappings().first()
        return dict(row) if row else None

    def fetch_latest_anomaly_for_kind(self, *, kind: str) -> dict[str, Any] | None:
        metric = "consumption_kw" if kind == "consumption" else "production_kw"
        direction = "above" if kind == "consumption" else "below"
        row = self._executor.execute(
            text(
                """
                SELECT anomaly_id, metric, direction, severity, sample_ts, explanation, evidence
                FROM anomalies
                WHERE metric = :metric
                  AND direction = :direction
                ORDER BY sample_ts DESC, anomaly_id DESC
                LIMIT 1
                """
            ),
            {"metric": metric, "direction": direction},
        ).mappings().first()
        return self._coerce_anomaly_row(dict(row)) if row else None

    def fetch_anomaly_by_id(self, *, anomaly_id: int) -> dict[str, Any] | None:
        row = self._executor.execute(
            text(
                """
                SELECT *
                FROM anomalies
                WHERE anomaly_id = :anomaly_id
                LIMIT 1
                """
            ),
            {"anomaly_id": anomaly_id},
        ).mappings().first()
        return self._coerce_anomaly_row(dict(row)) if row else None

    def fetch_anomaly_evidence(self, *, anomaly_id: int) -> list[dict[str, Any]]:
        rows = self._executor.execute(
            text(
                """
                SELECT *
                FROM anomaly_evidence
                WHERE anomaly_id = :anomaly_id
                ORDER BY evidence_id ASC
                """
            ),
            {"anomaly_id": anomaly_id},
        ).mappings().all()
        return [self._coerce_anomaly_evidence_row(dict(row)) for row in rows]

    def update_alert_status(
        self,
        *,
        alert_id: int,
        new_status: str,
        acknowledged_at: datetime,
        acknowledged_by: str,
        note: str | None,
    ) -> None:
        resolved_at = acknowledged_at if new_status in {"resolved", "suppressed"} else None
        resolved_by = acknowledged_by if new_status in {"resolved", "suppressed"} else None
        self._executor.execute(
            text(
                """
                UPDATE alerts
                SET status = :new_status,
                    acknowledged_at = :acknowledged_at,
                    acknowledged_by = :acknowledged_by,
                    acknowledged_note = :acknowledged_note,
                    resolved_at = :resolved_at,
                    resolved_by = :resolved_by,
                    resolution_note = CASE
                        WHEN :new_status IN ('resolved', 'suppressed') THEN :resolution_note
                        ELSE resolution_note
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE alert_id = :alert_id
                """
            ),
            {
                "alert_id": alert_id,
                "new_status": new_status,
                "acknowledged_at": acknowledged_at,
                "acknowledged_by": acknowledged_by,
                "acknowledged_note": note,
                "resolved_at": resolved_at,
                "resolved_by": resolved_by,
                "resolution_note": note,
            },
        )

    def insert_alert_acknowledgement(
        self,
        *,
        alert_id: int,
        acknowledged_at: datetime,
        acknowledged_by: str,
        previous_status: str,
        new_status: str,
        note: str | None,
    ) -> int:
        row = self._executor.execute(
            text(
                """
                INSERT INTO alert_acknowledgements
                (
                    alert_id,
                    acknowledged_at,
                    acknowledged_by,
                    previous_status,
                    new_status,
                    note
                )
                VALUES
                (
                    :alert_id,
                    :acknowledged_at,
                    :acknowledged_by,
                    :previous_status,
                    :new_status,
                    :note
                )
                RETURNING ack_id
                """
            ),
            {
                "alert_id": alert_id,
                "acknowledged_at": acknowledged_at,
                "acknowledged_by": acknowledged_by,
                "previous_status": previous_status,
                "new_status": new_status,
                "note": note,
            },
        ).mappings().first()
        return int(row["ack_id"])
