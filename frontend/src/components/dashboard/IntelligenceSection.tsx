import { AlertKind, IntelligenceDomainSummaryResponse, IntelligenceSummaryResponse } from "@/api/models";
import { DashboardStatePanel } from "@/components/dashboard/DashboardStatePanel";
import { formatRelativeAgeFromUnix, formatTimestampFromUnix } from "@/lib/format";

interface IntelligenceSectionProps {
  summary?: IntelligenceSummaryResponse;
  isLoading: boolean;
  hasError: boolean;
  errorMessage: string;
  isStale: boolean;
  onRetry: () => void;
}

const kindLabels: Record<AlertKind, string> = {
  production: "Production",
  consumption: "Consumption"
};

interface IntelligenceDisplayItem {
  id: string;
  kind: AlertKind;
  title: string;
  summary: string;
}

function buildSummaryItem(kind: AlertKind, domain: IntelligenceDomainSummaryResponse, openCount: number): IntelligenceDisplayItem | null {
  const latestAlert = domain.latest_alert;
  const latestAnomaly = domain.latest_anomaly;

  if (!latestAlert && !latestAnomaly) {
    return null;
  }

  const title = latestAlert?.title ?? `${kindLabels[kind]} anomaly detected`;
  const primarySummary = latestAlert?.message ?? latestAnomaly?.explanation ?? `${kindLabels[kind]} intelligence is available for review.`;
  const detailBits = [
    openCount > 0 ? `${openCount} open ${openCount === 1 ? "alert" : "alerts"}` : null,
    latestAlert?.last_seen_ts ? `Last seen ${formatRelativeAgeFromUnix(latestAlert.last_seen_ts)}` : null,
    !latestAlert && latestAnomaly?.sample_ts ? `Sample ${formatTimestampFromUnix(latestAnomaly.sample_ts)}` : null
  ].filter(Boolean);

  return {
    id: `${kind}-${latestAlert?.alert_id ?? latestAnomaly?.anomaly_id ?? "summary"}`,
    kind,
    title,
    summary: detailBits.length > 0 ? `${primarySummary} • ${detailBits.join(" • ")}` : primarySummary
  };
}

export function IntelligenceSection({
  summary,
  isLoading,
  hasError,
  errorMessage,
  isStale,
  onRetry
}: IntelligenceSectionProps) {
  const summaryItems = summary
    ? (["production", "consumption"] as const)
        .map((kind) => buildSummaryItem(kind, summary[kind], summary.open_counts.by_kind[kind] ?? 0))
        .filter((item): item is IntelligenceDisplayItem => item !== null)
    : [];

  return (
    <section className="intelligence-section" aria-label="Intelligence summary">
      <div className="intelligence-head">
        <div>
          <p className="k-title">Insights</p>
          <h2 className="dashboard-section-title">Narrative context for what deserves attention.</h2>
        </div>
        <p className="intelligence-generated-at">
          {summary?.generated_at_ts ? `Updated ${formatTimestampFromUnix(summary.generated_at_ts)}` : "Awaiting summary generation"}
        </p>
      </div>

      {isStale ? (
        <DashboardStatePanel
          tone="stale"
          compact
          title="Summary context may lag"
          message="Intelligence is based on the most recent available ingest, which is currently outside the freshness threshold."
        />
      ) : null}

      {isLoading && !summary ? (
        <DashboardStatePanel
          tone="loading"
          title="Loading intelligence"
          message="Compiling the latest production and consumption takeaways."
        />
      ) : null}

      {hasError && !summary ? (
        <DashboardStatePanel
          tone="error"
          title="Intelligence summary unavailable"
          message={errorMessage}
          actionLabel="Retry intelligence"
          onAction={onRetry}
        />
      ) : null}

      {!isLoading && !hasError && summary && summary.open_counts.total > 0 ? (
        <p className="intelligence-summary-copy">{summary.open_counts.total} active intelligence alerts are currently open across production and consumption.</p>
      ) : null}

      {!isLoading && !hasError && summaryItems.length === 0 ? (
        <DashboardStatePanel
          tone="empty"
          title="No intelligence summaries yet"
          message="The backend has not produced any narrative highlights for the current site conditions yet."
        />
      ) : null}

      {summaryItems.length > 0 ? (
        <div className="intelligence-list">
          {summaryItems.map((item) => (
            <article key={item.id} className={`intelligence-card intelligence-item kind-${item.kind}`.trim()}>
              <div className="intelligence-item-head">
                <span className={`pill intelligence-card-kind intelligence-kind-${item.kind}`}>{kindLabels[item.kind]}</span>
                <h3 className="intelligence-card-title intelligence-item-title">{item.title}</h3>
              </div>
              <p className="intelligence-card-summary intelligence-item-summary">{item.summary}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
