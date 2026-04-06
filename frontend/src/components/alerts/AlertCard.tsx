import type { CSSProperties, MouseEvent } from "react";

import type { AlertRecord, AlertSeverity, AlertStatus } from "@/api/models";
import { formatRelativeAgeFromUnix, formatTimestampFromUnix } from "@/lib/format";

interface AlertCardProps {
  alert: AlertRecord;
  isSelected: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  onAcknowledge?: () => void;
  isAcknowledging?: boolean;
  hasAcknowledgeError?: boolean;
  index: number;
}

const severityLabel: Record<AlertSeverity, string> = {
  info: "Info",
  warning: "Warning",
  critical: "Critical"
};

const statusLabel: Record<AlertStatus, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
  suppressed: "Suppressed"
};

export function AlertCard({
  alert,
  isSelected,
  isExpanded,
  onToggle,
  onAcknowledge,
  isAcknowledging = false,
  hasAcknowledgeError = false,
  index
}: AlertCardProps) {
  const handleAcknowledgeClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    onAcknowledge?.();
  };

  const detailId = `alert-card-panel-${alert.alert_id}`;
  const relativeTime = formatRelativeAgeFromUnix(alert.last_seen_ts);
  const absoluteTime = formatTimestampFromUnix(alert.last_seen_ts);

  return (
    <article
      data-testid={`alert-card-${alert.alert_id}`}
      className={`alert-card ${isSelected ? "alert-card-selected" : ""} ${isExpanded ? "alert-card-expanded" : "alert-card-collapsed"} alert-card-${alert.severity}`}
      style={{ "--alert-index": index } as CSSProperties}
      onClick={onToggle}
    >
      <button
        type="button"
        className="alert-card-trigger"
        onClick={(event) => {
          event.stopPropagation();
          onToggle();
        }}
        aria-expanded={isExpanded}
        aria-controls={detailId}
      >
        <span className={`alert-card-severity-dot alert-card-severity-dot-${alert.severity}`} aria-hidden="true" />

        <div className="alert-card-title-group">
          <h3 className="alert-card-title">{alert.title}</h3>
          <span className="alert-card-kind-sr-only" data-testid="alert-kind-badge">
            {alert.kind}
          </span>
          <span className="alert-card-status-sr-only" data-testid={`alert-status-${alert.alert_id}`}>
            {alert.status}
          </span>
        </div>

        <div className="alert-card-summary-meta">
          <span className="alert-card-time muted" title={absoluteTime}>
            {relativeTime}
          </span>
          <span className={`alert-card-chevron ${isExpanded ? "is-expanded" : ""}`} aria-hidden="true">
            <svg viewBox="0 0 16 16" focusable="false">
              <path d="m5.5 3.5 5 4.5-5 4.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
            </svg>
          </span>
        </div>
      </button>

      <div id={detailId} className={`alert-card-content ${isExpanded ? "is-expanded" : ""}`} aria-hidden={!isExpanded}>
        <div className="alert-card-head">
          <span className={`pill alert-severity-badge alert-severity-${alert.severity}`} data-testid="alert-severity-badge">
            {severityLabel[alert.severity]}
          </span>
          <span className="alert-card-status-text muted">{statusLabel[alert.status]}</span>
        </div>

        <div className="alert-card-body">
          <p className="alert-card-message muted">{alert.message}</p>
          <p className="alert-card-detail-time muted">Last seen {absoluteTime}</p>
        </div>

        {alert.status === "open" ? (
          <div className="alert-card-actions">
            <button
              type="button"
              className="alert-card-action"
              onClick={handleAcknowledgeClick}
              disabled={isAcknowledging}
              data-testid="acknowledge-submit-button"
            >
              {isAcknowledging ? "Acknowledging…" : "Acknowledge"}
            </button>

            {hasAcknowledgeError ? (
              <p className="acknowledge-error" data-testid="acknowledge-error" role="alert">
                Acknowledgement failed. The alert remains open. Please try again.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="alert-card-resolution muted">Already {statusLabel[alert.status].toLowerCase()}.</p>
        )}
      </div>
    </article>
  );
}
