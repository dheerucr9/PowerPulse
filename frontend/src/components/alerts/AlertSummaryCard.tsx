import type { AlertKind, AlertRecord } from "@/api/models";

interface AlertSummaryCardProps {
  kind: AlertKind;
  openCount: number;
  latestAlert: AlertRecord | null;
  isActive: boolean;
  isLoading: boolean;
  onClick: () => void;
}

const kindLabel: Record<AlertKind, string> = {
  production: "Production",
  consumption: "Consumption"
};

const emptyCopy: Record<AlertKind, string> = {
  production: "No production alerts are currently active.",
  consumption: "No consumption alerts are currently active."
};

function formatTs(ts: number) {
  return new Date(ts * 1000).toLocaleString();
}

export function AlertSummaryCard({ kind, openCount, latestAlert, isActive, isLoading, onClick }: AlertSummaryCardProps) {
  return (
    <button
      type="button"
      className={`alert-summary-card alert-summary-card-${kind} ${isActive ? "active" : ""}`.trim()}
      data-testid={`alert-summary-${kind}`}
      onClick={onClick}
    >
      <div className="alert-summary-card-head">
        <p className="k-title">{kindLabel[kind]} focus</p>
        <span className={`pill alert-kind-badge alert-kind-badge-${kind}`}>{openCount} open</span>
      </div>

      <div className="alert-summary-card-body">
        <p className="alert-summary-card-count">{String(openCount).padStart(2, "0")}</p>
        <div className="alert-summary-card-copy">
          <h3 className="alert-summary-card-title">{latestAlert?.title ?? emptyCopy[kind]}</h3>
          <p className="muted alert-summary-card-caption">
            {latestAlert
              ? `Last seen ${formatTs(latestAlert.last_seen_ts)}`
              : isLoading
                ? "Loading the latest open alert context."
                : "Filter the unified list to inspect this alert stream."}
          </p>
        </div>
      </div>
    </button>
  );
}
