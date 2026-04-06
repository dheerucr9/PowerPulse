import { BarHistoryInterval, HistoryChartType, HistoryDashboardData, HistoryFilters as HistoryFilterValues, GatewayDevice } from "@/api/models";
import { PowerHistoryChart } from "@/components/charts/PowerHistoryChart";
import { DashboardStatePanel } from "@/components/dashboard/DashboardStatePanel";
import { HistoryFilters } from "@/components/dashboard/HistoryFilters";

type RelativePreset = "last15m" | "last30m" | "last1h" | "last6h" | "last12h";
type AbsolutePreset = "today" | "yesterday" | "24h" | "7d" | "30d";
type CustomPreset = "custom";
type Preset = RelativePreset | AbsolutePreset | CustomPreset;

interface HistoryDashboardSectionProps {
  historyData: HistoryDashboardData | null;
  filters: HistoryFilterValues;
  chartType: HistoryChartType;
  setChartType: (chartType: HistoryChartType) => void;
  barInterval: BarHistoryInterval;
  setBarInterval: (interval: BarHistoryInterval) => void;
  draftRange: {
    from: string | null;
    to: string | null;
  };
  draftPanel: string;
  draftInterval: "auto" | "raw" | "5m" | "1h";
  activePreset: Preset;
  setActivePreset: (preset: Preset) => void;
  setDraftRange: (range: { from: string | null; to: string | null }) => void;
  setDraftPanel: (panel: string) => void;
  setDraftInterval: (interval: "auto" | "raw" | "5m" | "1h") => void;
  onApplyPreset: (preset: "today" | "yesterday" | "24h" | "7d" | "30d") => void;
  onApplyRelative: (preset: RelativePreset) => void;
  onReset: () => void;
  onApply: () => void;
  hasPendingChanges: boolean;
  panels: GatewayDevice[];
  isLoading: boolean;
  isRefreshing: boolean;
  hasError: boolean;
  errorMessage: string;
  isStale: boolean;
  hasAppliedRange: boolean;
  onReload: () => void;
}

function hasHistorySeries(data: HistoryDashboardData | null) {
  if (!data) {
    return false;
  }

  return Object.values(data.data).some((series) => series.length > 0);
}

export function HistoryDashboardSection({
  historyData,
  filters,
  chartType,
  setChartType,
  barInterval,
  setBarInterval,
  draftRange,
  draftPanel,
  draftInterval,
  activePreset,
  setActivePreset,
  setDraftRange,
  setDraftPanel,
  setDraftInterval,
  onApplyPreset,
  onApplyRelative,
  onReset,
  onApply,
  hasPendingChanges,
  panels,
  isLoading,
  isRefreshing,
  hasError,
  errorMessage,
  isStale,
  hasAppliedRange,
  onReload
}: HistoryDashboardSectionProps) {
  const barIntervalLabel = {
    day: "Last 7 days",
    week: "Last 8 weeks",
    month: "Last 12 months"
  } satisfies Record<BarHistoryInterval, string>;
  const hasChartData = hasHistorySeries(historyData);
  const hasResolvedData = Boolean(historyData);
  const showInitialLoading = hasAppliedRange && isLoading && !hasResolvedData;
  const showInitialError = hasAppliedRange && hasError && !hasResolvedData;
  const showRefreshLoading = hasAppliedRange && isRefreshing && hasResolvedData;
  const showRefreshError = hasAppliedRange && hasError && hasResolvedData;
  const showEmptyState = hasAppliedRange && !isLoading && !hasError && !hasChartData;
  const showHistoryChart = hasAppliedRange && hasChartData;

  return (
    <section className="history-section" aria-label="Historical analysis">
      <div className="history-layout">
        <div className="history-main-card history-panel">
          <div className="history-head">
            <div>
              <p className="k-title history-title">History</p>
              <h2 className="dashboard-section-title">Production, demand, net flow, charger, and panel output across the selected window</h2>
            </div>
            <button type="button" className="mini-btn history-reload-btn" onClick={onReload}>
              Reload
            </button>
          </div>

          {!hasAppliedRange ? (
            <DashboardStatePanel
              tone="empty"
              title="Choose a time window"
              message="Apply a preset or custom range to load historical production, consumption, net, charger, and panel traces."
            />
          ) : null}

          {hasAppliedRange ? (
            <div className="history-chart-toolbar" aria-label="History chart controls">
              <div className="history-chart-mode" role="tablist" aria-label="History chart type">
                {(["line", "bar"] as HistoryChartType[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    role="tab"
                    aria-selected={chartType === mode}
                    className={`tab ${chartType === mode ? "active" : ""}`}
                    onClick={() => setChartType(mode)}
                  >
                    {mode === "line" ? "Line" : "Bar"}
                  </button>
                ))}
              </div>

              {chartType === "bar" ? (
                <div className="history-chart-aggregation" role="tablist" aria-label="Bar chart aggregation">
                  {(["day", "week", "month"] as BarHistoryInterval[]).map((interval) => (
                    <button
                      key={interval}
                      type="button"
                      role="tab"
                      aria-selected={barInterval === interval}
                      className={`interval-chip ${barInterval === interval ? "active" : ""}`}
                      onClick={() => setBarInterval(interval)}
                    >
                      {interval}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {showInitialLoading ? (
            <DashboardStatePanel
              tone="loading"
              title="Loading history"
              message="Collecting the requested range and building chart series for the selected interval."
            />
          ) : null}

          {showInitialError ? (
            <DashboardStatePanel
              tone="error"
              testId="history-error-state"
              title="History unavailable for this range"
              message={errorMessage}
              actionLabel="Retry history"
              onAction={onReload}
            />
          ) : null}

          {showRefreshLoading ? (
            <DashboardStatePanel
              tone="loading"
              compact
              title="Refreshing history"
              message="Updating the selected time window while keeping the last successful chart in view."
            />
          ) : null}

          {showRefreshError ? (
            <DashboardStatePanel
              tone="error"
              compact
              testId="history-error-state"
              title="History refresh failed"
              message={`${errorMessage}. Showing the most recently loaded range while the history request retries.`}
              actionLabel="Retry history"
              onAction={onReload}
            />
          ) : null}

          {showEmptyState ? (
            <DashboardStatePanel
              tone="empty"
              title="No history points found"
              message="The selected range returned no production, consumption, net, charger, or panel data. Adjust the time window or panel scope and apply again."
            />
          ) : null}

          {showHistoryChart ? (
            <>
              {isStale ? (
                <DashboardStatePanel
                  tone="stale"
                  compact
                  title="Recent ingest is stale"
                  message="Historical charts are still available, but the newest ingest has missed the freshness threshold."
                />
              ) : null}

              <div className="history-chart">
                <PowerHistoryChart
                  data={historyData?.data ?? null}
                  panelLabel={historyData?.panelLabel ?? "Panel"}
                  chartType={chartType}
                  barInterval={barInterval}
                  className="history-chart-canvas"
                  testId="history-chart"
                />
              </div>

              <div className="history-meta">
                {chartType === "line"
                  ? `Showing ${filters.panel || "All panels"} • ${filters.interval} • ${filters.from || "--"} -> ${filters.to || "--"}`
                  : `Showing grouped energy totals • ${barIntervalLabel[barInterval]} • anchored to ${filters.to || "now"}`}
              </div>
            </>
          ) : null}
        </div>

        <HistoryFilters
          activePreset={activePreset}
          setActivePreset={setActivePreset}
          draftRange={draftRange}
          setDraftRange={setDraftRange}
          draftPanel={draftPanel}
          setDraftPanel={setDraftPanel}
          draftInterval={draftInterval}
          setDraftInterval={setDraftInterval}
          onApplyPreset={onApplyPreset}
          onApplyRelative={onApplyRelative}
          onReset={onReset}
          onApply={onApply}
          hasPendingChanges={hasPendingChanges}
          panels={panels}
        />
      </div>
    </section>
  );
}
