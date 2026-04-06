# pyright: reportMissingImports=false

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

AlertKind = Literal["production", "consumption"]
AlertSeverity = Literal["info", "warning", "critical"]
AlertStatus = Literal["open", "acknowledged", "resolved", "suppressed"]
AcknowledgementStatus = Literal["acknowledged", "resolved", "suppressed"]


class AlertExplanationPayload(BaseModel):
    kind: str
    source: str
    metric: str
    direction: str
    title: str
    message: str
    explanation: str
    evidence: dict[str, Any]
    sample_ts: int


class AlertResponse(BaseModel):
    alert_id: int
    anomaly_id: int | None = None
    site_id: str
    dedupe_key: str
    kind: AlertKind
    panel_id: str | None = None
    category: str
    severity: AlertSeverity
    status: AlertStatus
    state: str | None = None
    title: str
    message: str
    first_seen_ts: int
    last_seen_ts: int
    detected_at_ts: int
    last_observed_ts: int | None = None
    baseline_kw: float | None = None
    observed_kw: float | None = None
    deviation_kw: float | None = None
    deviation_pct: float | None = None
    confidence_score: float | None = None
    affected_panel_count: int | None = None
    evidence_summary: str | None = None
    explanation_payload: AlertExplanationPayload | dict[str, Any]
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    acknowledged_note: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None


class AlertListMeta(BaseModel):
    filtered_total: int
    returned: int
    open_badge_count: int
    open_by_kind: dict[str, int]
    open_by_severity: dict[str, int]


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    meta: AlertListMeta


class AlertAcknowledgeRequest(BaseModel):
    new_status: AcknowledgementStatus = "acknowledged"
    acknowledged_by: str | None = None
    note: str | None = None


class AnomalyResponse(BaseModel):
    anomaly_id: int
    site_id: str
    panel_id: str | None = None
    metric: str
    source: str
    direction: str
    severity: AlertSeverity
    state: str
    detected_at_ts: int
    sample_ts: int
    bucket_start_ts: int | None = None
    bucket_end_ts: int | None = None
    baseline_kw: float | None = None
    observed_kw: float | None = None
    deviation_kw: float | None = None
    deviation_pct: float | None = None
    z_score: float | None = None
    confidence_score: float | None = None
    sample_count: int | None = None
    panel_state: str | None = None
    explanation: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AnomalyEvidenceResponse(BaseModel):
    evidence_id: int
    anomaly_id: int
    site_id: str
    panel_id: str | None = None
    evidence_type: str
    reference_ts: int | None = None
    window_start_ts: int | None = None
    window_end_ts: int | None = None
    metric: str | None = None
    baseline_kw: float | None = None
    observed_kw: float | None = None
    deviation_kw: float | None = None
    deviation_pct: float | None = None
    z_score: float | None = None
    confidence_score: float | None = None
    sample_count: int | None = None
    panel_state: str | None = None
    details: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AlertDetailResponse(BaseModel):
    alert: AlertResponse
    anomaly: AnomalyResponse | None = None
    anomaly_evidence: list[AnomalyEvidenceResponse]


class AlertSummaryResponse(BaseModel):
    alert_id: int
    kind: AlertKind
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    last_seen_ts: int
    evidence_summary: str | None = None


class AnomalySummaryResponse(BaseModel):
    anomaly_id: int
    metric: str
    direction: str
    severity: AlertSeverity
    sample_ts: int
    explanation: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class IntelligenceDomainSummaryResponse(BaseModel):
    latest_alert: AlertSummaryResponse | None = None
    latest_anomaly: AnomalySummaryResponse | None = None


class IntelligenceOpenCountsResponse(BaseModel):
    total: int
    by_kind: dict[str, int]
    by_severity: dict[str, int]


class IntelligenceSummaryResponse(BaseModel):
    generated_at_ts: int
    open_counts: IntelligenceOpenCountsResponse
    production: IntelligenceDomainSummaryResponse
    consumption: IntelligenceDomainSummaryResponse
