import { useEffect, useMemo, useState } from "react";

import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { DashboardStatusBar } from "@/components/dashboard/DashboardStatusBar";
import { HistoryDashboardSection } from "@/components/dashboard/HistoryDashboardSection";
import { IntelligenceSection } from "@/components/dashboard/IntelligenceSection";
import { LiveFlow, deriveLiveFlowState } from "@/components/dashboard/LiveFlow";
import { ChargerStatCard } from "@/components/dashboard/ChargerStatCard";
import { StatCard } from "@/components/dashboard/StatCard";
import { DashboardStatePanel } from "@/components/dashboard/DashboardStatePanel";
import { AlertsPanel } from "@/components/alerts/AlertsPanel";
import { BarHistoryInterval, ChartPoint, HistoryChartType } from "@/api/models";
import { useAlertsQuery } from "@/features/alerts/useAlertsQuery";
import { useChargerData } from "@/features/charger/useChargerData";
import { useDashboardConfig } from "@/features/config/useDashboardConfig";
import { useReadinessQuery } from "@/features/diagnostics/useReadinessQuery";
import { extractTodayFromHistory, getTodayFilters } from "@/features/history/history-service";
import { useHistoryComparisonData, useHistoryData } from "@/features/history/useHistoryData";
import { useIntelligenceSummaryQuery } from "@/features/intelligence/useIntelligenceSummaryQuery";
import { useLiveData } from "@/features/live/useLiveData";
import { useDashboardShellState } from "@/features/shell/useDashboardShellState";
import { useTheme } from "@/hooks/useTheme";

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected API failure";
}

function integrateSeries(points: ChartPoint[]) {
  if (points.length < 2) {
    return 0;
  }

  let total = 0;

  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const deltaHours = Math.max(0, (current.ts - previous.ts) / 3600);

    total += ((previous.val + current.val) / 2) * deltaHours;
  }

  return total;
}

function formatKwh(value: number) {
  if (!Number.isFinite(value)) {
    return "--";
  }

  return `${value.toFixed(1)} kWh`;
}

function buildAverageTrend(
  currentValue: number,
  totalValue: number,
  from: string | null,
  label: string
): { text: string; direction: "up" | "down" | "neutral" } {
  if (!Number.isFinite(currentValue) || !Number.isFinite(totalValue) || !from) {
    return {
      text: label,
      direction: "neutral" as const
    };
  }

  const fromTime = Date.parse(from);

  if (!Number.isFinite(fromTime)) {
    return {
      text: label,
      direction: "neutral" as const
    };
  }

  const elapsedHours = Math.max((Date.now() - fromTime) / 3.6e6, 0.01);
  const averageKw = totalValue / elapsedHours;

  if (averageKw < 0.05) {
    return {
      text: label,
      direction: "neutral" as const
    };
  }

  const deltaPct = ((currentValue - averageKw) / averageKw) * 100;
  const magnitude = Math.round(Math.abs(deltaPct));

  return {
    text: `${deltaPct >= 0 ? "↑" : "↓"} ${magnitude}% vs range avg`,
    direction: deltaPct >= 0 ? ("up" as const) : ("down" as const)
  };
}

export function App() {
  const shellState = useDashboardShellState(window.location.search);
  const { theme, toggleTheme } = useTheme();
  const [alertsPanelOpen, setAlertsPanelOpen] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyChartType, setHistoryChartType] = useState<HistoryChartType>("line");
  const [historyBarInterval, setHistoryBarInterval] = useState<BarHistoryInterval>("day");
  const [intelligenceExpanded, setIntelligenceExpanded] = useState(false);
  const configQuery = useDashboardConfig();
  const liveQuery = useLiveData(window.location.search);
  const chargerQuery = useChargerData();
  const readinessQuery = useReadinessQuery();
  const alertsQuery = useAlertsQuery();
  const intelligenceQuery = useIntelligenceSummaryQuery();
  const historyEnabled = Boolean(shellState.historyFilters.from && shellState.historyFilters.to);
  const historyQuery = useHistoryData(shellState.historyFilters, historyEnabled);
  const historyComparisonQuery = useHistoryComparisonData(shellState.historyFilters.to, historyBarInterval, historyEnabled && historyChartType === "bar");
  const todayFilters = getTodayFilters();
  const todayQuery = useHistoryData(todayFilters, true);

  useEffect(() => {
    if (!shellState.appliedRange.from || !shellState.appliedRange.to) {
      shellState.applyPreset("today");
    }
  }, [shellState.appliedRange.from, shellState.appliedRange.to, shellState.applyPreset]);

  useEffect(() => {
    const config = configQuery.data;

    if (
      config?.lat != null &&
      config?.lon != null &&
      (shellState.latLon.lat !== config.lat || shellState.latLon.lon !== config.lon)
    ) {
      shellState.setLatLon({
        lat: config.lat,
        lon: config.lon
      });
    }
  }, [configQuery.data, shellState.latLon.lat, shellState.latLon.lon, shellState.setLatLon]);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") {
      document.querySelectorAll(".section-reveal").forEach((element) => {
        element.classList.add("visible");
      });

      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );

    document.querySelectorAll(".section-reveal").forEach((element) => {
      observer.observe(element);
    });

    return () => observer.disconnect();
  }, []);

  const liveData = liveQuery.data;
  const chargerData = chargerQuery.data;
  const panels = liveData?.panels ?? [];
  const lineHistoryData = historyQuery.data ?? null;
  const activeHistoryQuery = historyChartType === "bar" ? historyComparisonQuery : historyQuery;
  const historyData = activeHistoryQuery.data ?? null;
  const liveErrorMessage = getErrorMessage(liveQuery.error);
  const historyErrorMessage = getErrorMessage(activeHistoryQuery.error);
  const intelligenceErrorMessage = getErrorMessage(intelligenceQuery.error);
  const isStale = readinessQuery.data ? !readinessQuery.data.checks.ingest_fresh : false;
  const flowState = deriveLiveFlowState(liveData?.live, panels, shellState.latLon);

  const handleRefresh = () => {
    void liveQuery.refetch();
    void chargerQuery.refetch();
    void readinessQuery.refetch();
    void alertsQuery.refetch();
    void intelligenceQuery.refetch();

    if (historyEnabled) {
      void historyQuery.refetch();

       if (historyChartType === "bar") {
         void historyComparisonQuery.refetch();
       }
    }
  };

  const openCount = alertsQuery.data?.meta?.open_badge_count ?? 0;
  const criticalCount = alertsQuery.data?.meta?.open_by_severity?.critical ?? 0;
  const warningCount = alertsQuery.data?.meta?.open_by_severity?.warning ?? 0;
  const alertTone = criticalCount > 0 ? "critical" : warningCount > 0 || openCount > 0 ? "warning" : "neutral";

  const metricCards = useMemo(() => {
    const todayData = extractTodayFromHistory(todayQuery.data ?? lineHistoryData);
    const productionTotal = integrateSeries(todayData?.data.production ?? []);
    const consumptionTotal = integrateSeries(todayData?.data.consumption ?? []);
    const netTotal = integrateSeries(todayData?.data.net ?? []);
    const chargerTotal = integrateSeries(todayData?.data.charger ?? []);

    const productionTrend = buildAverageTrend(flowState.production, productionTotal, todayFilters.from, "Awaiting trend");
    const consumptionTrend = buildAverageTrend(flowState.consumption, consumptionTotal, todayFilters.from, "Awaiting trend");
    const gridDirection = netTotal >= 0.05 ? ("up" as const) : netTotal <= -0.05 ? ("down" as const) : ("neutral" as const);

    return {
      chargerTotal,
      cards: [
      {
        title: "Solar today",
        value: formatKwh(productionTotal),
        tone: "production" as const,
        trend: productionTrend.text,
        trendDirection: productionTrend.direction
      },
      {
        title: "Used today",
        value: formatKwh(consumptionTotal),
        tone: "consumption" as const,
        trend: consumptionTrend.text,
        trendDirection: consumptionTrend.direction
      },
      {
        title: "Grid",
        value: formatKwh(Math.abs(netTotal)),
        tone: "net" as const,
        trend: netTotal >= 0.05 ? "Exported" : netTotal <= -0.05 ? "Imported" : "Balanced",
        trendDirection: gridDirection
      }
      ]
    };
  }, [flowState.consumption, flowState.production, todayQuery.data, lineHistoryData, todayFilters.from]);

  const showInitialLiveLoading = liveQuery.isPending && !liveData;
  const showInitialLiveError = liveQuery.isError && !liveData;
  const showRefreshError = liveQuery.isError && Boolean(liveData);

  return (
    <>
      <DashboardHeader
        alertCount={openCount}
        alertTone={alertTone}
        onAlertClick={() => setAlertsPanelOpen(true)}
        onRefresh={handleRefresh}
        theme={theme}
        onThemeToggle={toggleTheme}
      />

      <main className="dashboard-main">
        <section className="hero-section section-reveal" aria-label="Current energy flow" style={{ transitionDelay: "0ms" }}>
          <p className="hero-subtitle">{flowState.statusText}</p>

          <div className="hero-content">
            {showInitialLiveLoading ? (
              <div className="live-flow-skeleton">
                <div className="flow-container">
                  <div className="flow-node">
                    <div className="flow-icon-wrapper skeleton skeleton-shimmer" />
                    <div className="flow-value-skeleton skeleton skeleton-shimmer" />
                    <div className="flow-label-skeleton skeleton skeleton-shimmer" />
                  </div>
                  <div className="flow-connector" />
                  <div className="flow-node">
                    <div className="flow-icon-wrapper skeleton skeleton-shimmer" />
                    <div className="flow-value-skeleton skeleton skeleton-shimmer" />
                    <div className="flow-label-skeleton skeleton skeleton-shimmer" />
                  </div>
                  <div className="flow-connector" />
                  <div className="flow-node">
                    <div className="flow-icon-wrapper skeleton skeleton-shimmer" />
                    <div className="flow-value-skeleton skeleton skeleton-shimmer" />
                    <div className="flow-label-skeleton skeleton skeleton-shimmer" />
                  </div>
                </div>
                <div className="flow-summary-skeleton skeleton skeleton-shimmer" />
              </div>
            ) : null}

            {showInitialLiveError ? (
              <DashboardStatePanel
                tone="error"
                testId="live-error-state"
                title="Live telemetry unavailable"
                message={liveErrorMessage}
                actionLabel="Retry live data"
                onAction={() => void liveQuery.refetch()}
              />
            ) : null}

            {liveData ? (
              <LiveFlow
                live={liveData.live}
                charger={chargerData}
                panels={panels}
                latLon={shellState.latLon}
                isRefreshing={(liveQuery.isFetching && !liveQuery.isPending) || (chargerQuery.isFetching && !chargerQuery.isPending)}
              />
            ) : null}

            {showRefreshError ? (
              <DashboardStatePanel
                tone="error"
                compact
                testId="live-error-state"
                title="Live refresh failed"
                message={`${liveErrorMessage}. Showing the latest successful snapshot while live refresh retries.`}
                actionLabel="Retry live data"
                onAction={() => void liveQuery.refetch()}
              />
            ) : null}

            {isStale && liveData ? (
              <DashboardStatePanel
                tone="stale"
                compact
                title="Telemetry is older than the readiness threshold"
                message="Values are still shown so operators keep context, but they may lag behind the current site state."
                actionLabel="Refresh"
                onAction={handleRefresh}
              />
            ) : null}
          </div>
        </section>

        <section className="metrics-section section-reveal" aria-label="Daily metrics" style={{ transitionDelay: "80ms" }}>
          <div className="metrics-grid" aria-busy={showInitialLiveLoading} data-loading={showInitialLiveLoading ? "true" : "false"}>
            {metricCards.cards.map((card) => (
              <StatCard
                key={card.title}
                title={card.title}
                value={card.value}
                trend={card.trend}
                tone={card.tone}
                trendDirection={card.trendDirection}
                isLoading={showInitialLiveLoading}
              />
            ))}

            <ChargerStatCard
              chargedTodayKwh={metricCards.chargerTotal}
              chargerData={chargerData}
              isLoading={showInitialLiveLoading || (todayQuery.isPending && !todayQuery.data && !lineHistoryData)}
            />
          </div>
        </section>

        <section className="expandable-section section-reveal" aria-label="History section" style={{ transitionDelay: "160ms" }}>
          <div className="expandable-surface">
            <button
              type="button"
              className={`expandable-trigger ${historyExpanded ? "open" : ""}`.trim()}
              onClick={() => setHistoryExpanded((current) => !current)}
            >
              <span className="expandable-heading">{historyExpanded ? "Hide history" : "Show history"}</span>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
                <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <div className={`expandable-content ${historyExpanded ? "open" : ""}`.trim()} style={{ maxHeight: historyExpanded ? "2400px" : "0px" }}>
              <HistoryDashboardSection
                historyData={historyData}
                filters={shellState.historyFilters}
                chartType={historyChartType}
                setChartType={setHistoryChartType}
                barInterval={historyBarInterval}
                setBarInterval={setHistoryBarInterval}
                draftRange={shellState.draftRange}
                draftPanel={shellState.draftPanel}
                draftInterval={shellState.draftInterval}
                activePreset={shellState.activePreset}
                setActivePreset={shellState.setActivePreset}
                setDraftRange={shellState.setDraftRange}
                setDraftPanel={shellState.setDraftPanel}
                setDraftInterval={shellState.setDraftInterval}
                onApplyPreset={shellState.applyPreset}
                onApplyRelative={shellState.applyRelative}
                onReset={shellState.resetHistoryFilters}
                onApply={shellState.applyHistoryFilters}
                hasPendingChanges={shellState.hasPendingHistoryChanges}
                panels={panels}
                isLoading={activeHistoryQuery.isPending}
                isRefreshing={activeHistoryQuery.isFetching && !activeHistoryQuery.isPending}
                hasError={activeHistoryQuery.isError}
                errorMessage={historyErrorMessage}
                isStale={isStale}
                hasAppliedRange={Boolean(shellState.historyFilters.from && shellState.historyFilters.to)}
                onReload={() => void activeHistoryQuery.refetch()}
              />
            </div>
          </div>
        </section>

        <section className="expandable-section section-reveal" aria-label="Insights section" style={{ transitionDelay: "240ms" }}>
          <div className="expandable-surface">
            <button
              type="button"
              className={`expandable-trigger ${intelligenceExpanded ? "open" : ""}`.trim()}
              onClick={() => setIntelligenceExpanded((current) => !current)}
            >
              <span className="expandable-heading">{intelligenceExpanded ? "Hide insights" : "Insights"}</span>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
                <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <div className={`expandable-content ${intelligenceExpanded ? "open" : ""}`.trim()} style={{ maxHeight: intelligenceExpanded ? "1800px" : "0px" }}>
              <IntelligenceSection
                summary={intelligenceQuery.data}
                isLoading={intelligenceQuery.isPending}
                hasError={intelligenceQuery.isError}
                errorMessage={intelligenceErrorMessage}
                isStale={isStale}
                onRetry={() => void intelligenceQuery.refetch()}
              />
            </div>
          </div>
        </section>

        <DashboardStatusBar
          readiness={readinessQuery.data}
          readinessLoading={readinessQuery.isPending}
          readinessError={readinessQuery.isError}
          liveData={liveData}
          liveLoading={liveQuery.isPending}
          liveError={liveQuery.isError}
          alerts={alertsQuery.data}
          alertsLoading={alertsQuery.isPending}
          alertsError={alertsQuery.isError}
        />
      </main>

      <AlertsPanel isOpen={alertsPanelOpen} onClose={() => setAlertsPanelOpen(false)} />
    </>
  );
}
