import type { AlertRecord } from "@/api/models";
import { AlertAcknowledgeForm } from "@/components/alerts/AlertAcknowledgeForm";
import { AlertStructuredEvidence } from "@/components/alerts/AlertStructuredEvidence";
import { DashboardStatePanel } from "@/components/dashboard/DashboardStatePanel";
import type { AcknowledgementStatus } from "@/api/models";

interface AlertDetailProps {
  alert: AlertRecord;
  onAcknowledge: (body: { new_status: AcknowledgementStatus; acknowledged_by: string; note: string }) => void;
  isPending: boolean;
  hasError: boolean;
}

function formatTs(ts: number) {
  return new Date(ts * 1000).toLocaleString();
}

function formatKw(kw: number | null) {
  if (kw === null) return "—";
  return `${kw.toFixed(2)} kW`;
}

function formatPct(pct: number | null) {
  if (pct === null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function AlertDetail({ alert, onAcknowledge, isPending, hasError }: AlertDetailProps) {
  const explanationPayload = alert.explanation_payload;
  const evidence = explanationPayload?.evidence;
  const classification = explanationPayload
    ? {
        source: explanationPayload.source,
        metric: explanationPayload.metric,
        direction: explanationPayload.direction,
        sample_ts: explanationPayload.sample_ts
      }
    : null;

  return (
    <div className="alert-detail" data-testid="alert-detail">
      <div className="alert-detail-head">
        <p className="k-title">Alert detail</p>
        <h2 className="alert-detail-title">{alert.title}</h2>
        <p className="alert-detail-message muted">{alert.message}</p>
      </div>

      <dl className="alert-evidence-grid">
        <div className="alert-evidence-item">
          <dt className="muted">Kind</dt>
          <dd>{alert.kind}</dd>
        </div>
        <div className="alert-evidence-item">
          <dt className="muted">Severity</dt>
          <dd>{alert.severity}</dd>
        </div>
        <div className="alert-evidence-item">
          <dt className="muted">Status</dt>
          <dd>{alert.status}</dd>
        </div>
        <div className="alert-evidence-item">
          <dt className="muted">Category</dt>
          <dd>{alert.category}</dd>
        </div>
        {alert.panel_id ? (
          <div className="alert-evidence-item">
            <dt className="muted">Panel</dt>
            <dd>{alert.panel_id}</dd>
          </div>
        ) : null}
        {alert.state ? (
          <div className="alert-evidence-item">
            <dt className="muted">State</dt>
            <dd>{alert.state}</dd>
          </div>
        ) : null}
        {alert.baseline_kw !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Baseline</dt>
            <dd>{formatKw(alert.baseline_kw)}</dd>
          </div>
        ) : null}
        {alert.observed_kw !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Observed</dt>
            <dd>{formatKw(alert.observed_kw)}</dd>
          </div>
        ) : null}
        {alert.deviation_pct !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Deviation</dt>
            <dd>{formatPct(alert.deviation_pct)}</dd>
          </div>
        ) : null}
        {alert.deviation_kw !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Deviation kW</dt>
            <dd>{formatKw(alert.deviation_kw)}</dd>
          </div>
        ) : null}
        {alert.confidence_score !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Confidence</dt>
            <dd>{alert.confidence_score.toFixed(2)}</dd>
          </div>
        ) : null}
        {alert.affected_panel_count !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Affected panels</dt>
            <dd>{alert.affected_panel_count}</dd>
          </div>
        ) : null}
        <div className="alert-evidence-item">
          <dt className="muted">Detected</dt>
          <dd>{formatTs(alert.detected_at_ts)}</dd>
        </div>
        <div className="alert-evidence-item">
          <dt className="muted">First seen</dt>
          <dd>{formatTs(alert.first_seen_ts)}</dd>
        </div>
        <div className="alert-evidence-item">
          <dt className="muted">Last seen</dt>
          <dd>{formatTs(alert.last_seen_ts)}</dd>
        </div>
        {alert.last_observed_ts !== null ? (
          <div className="alert-evidence-item">
            <dt className="muted">Last observed</dt>
            <dd>{formatTs(alert.last_observed_ts)}</dd>
          </div>
        ) : null}
        {alert.acknowledged_at ? (
          <div className="alert-evidence-item">
            <dt className="muted">Acknowledged</dt>
            <dd>
              {formatTs(Math.floor(new Date(alert.acknowledged_at).getTime() / 1000))} by{" "}
              {alert.acknowledged_by ?? "—"}
            </dd>
          </div>
        ) : null}
        {alert.acknowledged_note ? (
          <div className="alert-evidence-item alert-evidence-note">
            <dt className="muted">Operator note</dt>
            <dd>{alert.acknowledged_note}</dd>
          </div>
        ) : null}
        {alert.evidence_summary ? (
          <div className="alert-evidence-item alert-evidence-note">
            <dt className="muted">Evidence summary</dt>
            <dd>{alert.evidence_summary}</dd>
          </div>
        ) : null}
      </dl>

      {explanationPayload?.explanation ? <p className="alert-detail-explanation muted">{explanationPayload.explanation}</p> : null}

      {classification ? <AlertStructuredEvidence title="Classification" data={classification} /> : null}
      {evidence && Object.keys(evidence).length > 0 ? (
        <AlertStructuredEvidence title="Structured evidence" data={evidence} testId="alert-structured-evidence" />
      ) : null}

      {alert.status === "open" ? (
        <div className="alert-detail-actions">
          <p className="alert-detail-actions-label k-title">Take action</p>
          <AlertAcknowledgeForm
            alertId={alert.alert_id}
            currentStatus={alert.status}
            onSubmit={onAcknowledge}
            isPending={isPending}
            hasError={hasError}
          />
        </div>
      ) : (
        <DashboardStatePanel
          tone="empty"
          compact
          title={`Alert is ${alert.status}`}
          message="This alert has already been actioned."
        />
      )}
    </div>
  );
}
