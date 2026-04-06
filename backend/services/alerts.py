from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from typing import Any

from ..observability import ALERT_GENERATED_TOTAL
from ..repositories.alerts import AlertsRepository

ALERT_SEVERITY_ORDER = {
    "info": 0,
    "warning": 1,
    "critical": 2,
}


def _kind_from_metric(metric: str) -> str:
    return "consumption" if metric == "consumption_kw" else "production"


def _dedupe_key(
    *,
    site_id: str,
    panel_id: str | None,
    kind: str,
    source: str,
    metric: str,
    direction: str,
) -> str:
    return f"{site_id}|{panel_id or '*'}|{kind}|{source}|{metric}|{direction}"


def _coerce_payload(payload: dict[str, Any] | str | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, str):
        try:
            loaded = json.loads(payload)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return payload


class AlertLifecycleService:
    def __init__(self, repository: AlertsRepository):
        self._repository = repository

    def record_anomaly_detection(
        self,
        *,
        anomaly_id: int,
        site_id: str,
        panel_id: str | None,
        source: str,
        metric: str,
        direction: str,
        severity: str,
        sample_ts: int,
        title: str,
        message: str,
        baseline_kw: float | None,
        observed_kw: float | None,
        deviation_kw: float | None,
        deviation_pct: float | None,
        confidence_score: float | None,
        affected_panel_count: int | None,
        explanation: str,
        evidence: dict[str, Any],
    ) -> int:
        kind = _kind_from_metric(metric)
        dedupe_key = _dedupe_key(
            site_id=site_id,
            panel_id=panel_id,
            kind=kind,
            source=source,
            metric=metric,
            direction=direction,
        )
        explanation_payload: dict[str, Any] = {
            "kind": kind,
            "source": source,
            "metric": metric,
            "direction": direction,
            "title": title,
            "message": message,
            "explanation": explanation,
            "evidence": evidence,
            "sample_ts": sample_ts,
        }

        existing = self._repository.fetch_active_alert_by_dedupe_key(dedupe_key=dedupe_key)
        if existing is None:
            ALERT_GENERATED_TOTAL.labels(kind=kind, severity=severity).inc()
            return self._repository.insert_alert(
                anomaly_id=anomaly_id,
                site_id=site_id,
                panel_id=panel_id,
                dedupe_key=dedupe_key,
                kind=kind,
                category=kind,
                severity=severity,
                title=title,
                message=message,
                first_seen_ts=sample_ts,
                last_seen_ts=sample_ts,
                baseline_kw=baseline_kw,
                observed_kw=observed_kw,
                deviation_kw=deviation_kw,
                deviation_pct=deviation_pct,
                confidence_score=confidence_score,
                affected_panel_count=affected_panel_count,
                evidence_summary=explanation,
                explanation_payload=explanation_payload,
            )

        existing_severity = str(existing.get("severity") or "info")
        if ALERT_SEVERITY_ORDER.get(severity, 0) < ALERT_SEVERITY_ORDER.get(existing_severity, 0):
            severity = existing_severity

        self._repository.update_existing_alert_observation(
            alert_id=int(existing["alert_id"]),
            anomaly_id=anomaly_id,
            severity=severity,
            last_seen_ts=sample_ts,
            baseline_kw=baseline_kw,
            observed_kw=observed_kw,
            deviation_kw=deviation_kw,
            deviation_pct=deviation_pct,
            confidence_score=confidence_score,
            affected_panel_count=affected_panel_count,
            evidence_summary=explanation,
            explanation_payload=explanation_payload,
        )
        return int(existing["alert_id"])

    def acknowledge_alert(
        self,
        *,
        alert_id: int,
        new_status: str = "acknowledged",
        acknowledged_by: str | None = None,
        note: str | None = None,
        acknowledged_at: datetime | None = None,
    ) -> dict[str, Any]:
        if new_status not in {"acknowledged", "resolved", "suppressed"}:
            raise ValueError("new_status must be one of acknowledged, resolved, suppressed")

        alert = self._repository.fetch_alert_by_id(alert_id=alert_id)
        if alert is None:
            raise ValueError(f"alert {alert_id} not found")

        if str(alert.get("status")) == new_status:
            return alert

        actor = (acknowledged_by or "").strip() or "local-operator"
        at = acknowledged_at or datetime.now(tz=timezone.utc)
        previous_status = str(alert["status"])

        self._repository.update_alert_status(
            alert_id=alert_id,
            new_status=new_status,
            acknowledged_at=at,
            acknowledged_by=actor,
            note=note,
        )
        self._repository.insert_alert_acknowledgement(
            alert_id=alert_id,
            acknowledged_at=at,
            acknowledged_by=actor,
            previous_status=previous_status,
            new_status=new_status,
            note=note,
        )

        refreshed = self._repository.fetch_alert_by_id(alert_id=alert_id)
        if refreshed is None:
            raise ValueError(f"alert {alert_id} was updated but not readable")
        refreshed["explanation_payload"] = _coerce_payload(refreshed.get("explanation_payload"))
        return refreshed
