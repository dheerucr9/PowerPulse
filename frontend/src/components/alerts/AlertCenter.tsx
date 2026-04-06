import { useEffect, useState } from "react";

import type { AlertRecord, AcknowledgementStatus } from "@/api/models";
import { AlertCard } from "@/components/alerts/AlertCard";
import { DashboardStatePanel } from "@/components/dashboard/DashboardStatePanel";
import { useAlertsQuery, useAcknowledgeAlert } from "@/features/alerts/useAlertsQuery";

type FilterStatus = "open" | "acknowledged" | "all";
type FilterKind = "production" | "consumption" | "all";

const ALERTS_PAGE_SIZE = 15;

export function AlertCenter() {
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("open");
  const [filterKind, setFilterKind] = useState<FilterKind>("all");
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(ALERTS_PAGE_SIZE);

  const statusParam = filterStatus === "all" ? undefined : filterStatus;
  const kindParam = filterKind === "all" ? undefined : filterKind;
  const alertsQuery = useAlertsQuery({ status: statusParam, kind: kindParam });
  const acknowledgeMutation = useAcknowledgeAlert();

  const alerts = alertsQuery.data?.items ?? [];
  const filteredTotal = alertsQuery.data?.meta.filtered_total ?? alerts.length;
  const visibleAlerts = alerts.slice(0, visibleCount);

  useEffect(() => {
    setVisibleCount(ALERTS_PAGE_SIZE);
  }, [filterStatus, filterKind]);

  useEffect(() => {
    if (selectedAlertId === null) {
      return;
    }

    const selectedIndex = alerts.findIndex((alert) => alert.alert_id === selectedAlertId);

    if (selectedIndex === -1) {
      setSelectedAlertId(null);
      return;
    }

    if (selectedIndex >= visibleCount) {
      setVisibleCount(Math.ceil((selectedIndex + 1) / ALERTS_PAGE_SIZE) * ALERTS_PAGE_SIZE);
    }
  }, [alerts, selectedAlertId, visibleCount]);

  const handleAcknowledge = (alertId: number, body: { new_status: AcknowledgementStatus; acknowledged_by: string; note: string }) => {
    acknowledgeMutation.mutate(
      { alertId, body },
      {
        onSuccess: () => {
          setSelectedAlertId(null);
        }
      }
    );
  };

  const isLoading = alertsQuery.isPending;
  const hasError = alertsQuery.isError;

  const selectAlert = (alertId: number | null) => {
    acknowledgeMutation.reset();
    setSelectedAlertId((current) => (current === alertId ? null : alertId));
  };

  const activeScopeLabel = filterKind === "all" ? "All alerts" : filterKind === "production" ? "Production only" : "Consumption only";
  const resultLabel = `${filteredTotal} ${filteredTotal === 1 ? "result" : "results"}`;

  return (
    <section className="alert-center" data-testid="alert-center" aria-label="Alert center">
      <div className="alert-center-toolbar">
        <div className="tabs alert-status-tabs" role="tablist" aria-label="Filter alerts by status">
          <button
            type="button"
            role="tab"
            aria-selected={filterStatus === "open"}
            className={`tab ${filterStatus === "open" ? "active" : ""}`}
            onClick={() => setFilterStatus("open")}
            data-testid="alert-filter-open"
          >
            Open
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filterStatus === "acknowledged"}
            className={`tab ${filterStatus === "acknowledged" ? "active" : ""}`}
            onClick={() => setFilterStatus("acknowledged")}
            data-testid="alert-filter-acknowledged"
          >
            Acknowledged
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filterStatus === "all"}
            className={`tab ${filterStatus === "all" ? "active" : ""}`}
            onClick={() => setFilterStatus("all")}
            data-testid="alert-filter-all"
          >
            All
          </button>
        </div>

        <label className="alert-kind-filter" htmlFor="alert-kind-filter">
          <span className="alert-kind-filter-label">Scope</span>
          <select
            id="alert-kind-filter"
            className="alert-kind-select"
            value={filterKind}
            onChange={(event) => {
              acknowledgeMutation.reset();
              setFilterKind(event.target.value as FilterKind);
            }}
            aria-label="Filter alerts by type"
          >
            <option value="all">All alerts</option>
            <option value="production">Production</option>
            <option value="consumption">Consumption</option>
          </select>
        </label>
      </div>

      <p className="alert-center-context muted">{activeScopeLabel} · {resultLabel}</p>

      <div className="alert-center-body">
        <div className="alert-center-list">
          {isLoading && alerts.length === 0 ? (
            <DashboardStatePanel tone="loading" title="Loading alerts" message="Fetching intelligence alerts…" />
          ) : hasError && alerts.length === 0 ? (
            <DashboardStatePanel
              tone="error"
              title="Alerts unavailable"
              message={alertsQuery.error instanceof Error ? alertsQuery.error.message : "Unexpected failure"}
              actionLabel="Retry"
              onAction={() => void alertsQuery.refetch()}
            />
          ) : alerts.length === 0 ? (
            <DashboardStatePanel tone="empty" title="No alerts" message="No alerts match the current filter." />
          ) : (
            visibleAlerts.map((alert: AlertRecord, index) => (
              <AlertCard
                key={alert.alert_id}
                alert={alert}
                isSelected={selectedAlertId === alert.alert_id}
                isExpanded={selectedAlertId === alert.alert_id}
                onToggle={() => selectAlert(alert.alert_id)}
                onAcknowledge={
                  alert.status === "open"
                    ? () =>
                        handleAcknowledge(alert.alert_id, {
                          new_status: "acknowledged",
                          acknowledged_by: "local-operator",
                          note: ""
                        })
                    : undefined
                }
                isAcknowledging={acknowledgeMutation.isPending && acknowledgeMutation.variables?.alertId === alert.alert_id}
                hasAcknowledgeError={acknowledgeMutation.isError && acknowledgeMutation.variables?.alertId === alert.alert_id}
                index={index}
              />
            ))
          )}
        </div>

        {visibleCount < alerts.length ? (
          <button
            type="button"
            className="pill alert-load-more"
            onClick={() => setVisibleCount((current) => Math.min(current + ALERTS_PAGE_SIZE, alerts.length))}
            data-testid="alert-load-more"
          >
            Load more
          </button>
        ) : null}
      </div>
    </section>
  );
}
