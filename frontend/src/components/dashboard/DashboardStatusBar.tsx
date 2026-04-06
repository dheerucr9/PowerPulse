import { AlertsResponse, LiveDashboardData, ReadinessResponse } from "@/api/models";
import { formatRelativeAgeFromUnix, formatTimestampFromUnix } from "@/lib/format";

interface DashboardStatusBarProps {
  readiness?: ReadinessResponse;
  readinessLoading: boolean;
  readinessError: boolean;
  liveData?: LiveDashboardData;
  liveLoading: boolean;
  liveError: boolean;
  alerts?: AlertsResponse;
  alertsLoading: boolean;
  alertsError: boolean;
}

interface StatusMetric {
  label: string;
  value: string;
  detail: string;
  tone: "healthy" | "warning" | "critical" | "neutral";
  pulse?: boolean;
}

function createFreshnessMetric(
  readiness: ReadinessResponse | undefined,
  loading: boolean,
  hasError: boolean
): StatusMetric {
  if (loading && !readiness) {
    return {
      label: "Freshness",
      value: "Checking",
      detail: "Verifying the latest ingest window.",
      tone: "neutral",
      pulse: false
    };
  }

  if (hasError || !readiness) {
    return {
      label: "Freshness",
      value: "Unknown",
      detail: "Readiness telemetry is unavailable.",
      tone: "critical",
      pulse: false
    };
  }

  if (!readiness.last_successful_ingest_ts) {
    return {
      label: "Freshness",
      value: "Awaiting ingest",
      detail: "No successful ingest has been recorded yet.",
      tone: "warning",
      pulse: false
    };
  }

  return {
    label: "Freshness",
    value: readiness.checks.ingest_fresh ? "Fresh" : "Stale",
    detail: `Last sample ${formatRelativeAgeFromUnix(readiness.last_successful_ingest_ts)} • ${formatTimestampFromUnix(
      readiness.last_successful_ingest_ts
    )}`,
    tone: readiness.checks.ingest_fresh ? "healthy" : "warning",
    pulse: readiness.checks.ingest_fresh
  };
}

function createGatewayMetric(liveData: LiveDashboardData | undefined, loading: boolean, hasError: boolean): StatusMetric {
  if (loading && !liveData) {
    return {
      label: "Gateway",
      value: "Connecting",
      detail: "Polling the live gateway feed.",
      tone: "neutral",
      pulse: false
    };
  }

  if (hasError) {
    return {
      label: "Gateway",
      value: "Offline",
      detail: "Live gateway telemetry is not reachable.",
      tone: "critical",
      pulse: false
    };
  }

  const gatewayModel = liveData?.meta.gw?.MODEL;
  const gatewayFirmware = liveData?.meta.gw?.SWVER;

  return {
    label: "Gateway",
    value: gatewayModel ? "Reachable" : "Limited",
    detail: gatewayModel ? `${gatewayModel} • FW ${gatewayFirmware ?? "N/A"}` : "Live telemetry is present without gateway metadata.",
    tone: gatewayModel ? "healthy" : "warning",
    pulse: Boolean(gatewayModel)
  };
}

function createApiMetric(readiness: ReadinessResponse | undefined, loading: boolean, hasError: boolean): StatusMetric {
  if (loading && !readiness) {
    return {
      label: "API",
      value: "Checking",
      detail: "Validating database, migrations, and readiness.",
      tone: "neutral",
      pulse: false
    };
  }

  if (hasError || !readiness) {
    return {
      label: "API",
      value: "Unavailable",
      detail: "Readiness checks could not be loaded.",
      tone: "critical",
      pulse: false
    };
  }

  const degradedChecks = Object.entries(readiness.checks)
    .filter(([, passed]) => !passed)
    .map(([key]) => key.replace("_", " "));

  return {
    label: "API",
    value: readiness.status === "ok" ? "Healthy" : "Degraded",
    detail:
      readiness.status === "ok"
        ? "Database, migrations, and ingest checks are passing."
        : `Needs attention: ${degradedChecks.join(", ")}.`,
    tone: readiness.status === "ok" ? "healthy" : "warning",
    pulse: false
  };
}

function createAlertsMetric(alerts: AlertsResponse | undefined, loading: boolean, hasError: boolean): StatusMetric {
  if (loading && !alerts) {
    return {
      label: "Alerts",
      value: "Loading",
      detail: "Collecting current alert count.",
      tone: "neutral",
      pulse: false
    };
  }

  if (hasError || !alerts) {
    return {
      label: "Alerts",
      value: "Unknown",
      detail: "Alert service did not respond.",
      tone: "critical",
      pulse: false
    };
  }

  const openCount = alerts.meta?.open_badge_count ?? 0;

  return {
    label: "Alerts",
    value: openCount === 0 ? "Clear" : String(openCount),
    detail: openCount === 1 ? "1 active alert requires review." : `${openCount} active alerts require review.`,
    tone: openCount > 0 ? "warning" : "healthy",
    pulse: false
  };
}

export function DashboardStatusBar({
  readiness,
  readinessLoading,
  readinessError,
  liveData,
  liveLoading,
  liveError,
  alerts,
  alertsLoading,
  alertsError
}: DashboardStatusBarProps) {
  const metrics = [
    createFreshnessMetric(readiness, readinessLoading, readinessError),
    createGatewayMetric(liveData, liveLoading, liveError),
    createApiMetric(readiness, readinessLoading, readinessError),
    createAlertsMetric(alerts, alertsLoading, alertsError)
  ];

  return (
    <section className="dashboard-status-bar" data-testid="dashboard-status-bar" aria-label="System diagnostics">
      <div className="dashboard-status-grid">
        {metrics.map((metric) => (
          <article
            key={metric.label}
            className={`dashboard-status-item tone-${metric.tone} ${metric.pulse ? "dashboard-status-item-pulse" : ""}`.trim()}
            title={metric.detail}
          >
            <span className={`status-item-accent ${metric.pulse ? "dashboard-status-dot-pulse" : ""}`.trim()} aria-hidden="true" />
            <span className="dashboard-status-label">{metric.label}</span>
            <span className="dashboard-status-value">{metric.value}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
