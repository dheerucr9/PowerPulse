import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { renderWithProviders } from "@/test/test-utils";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function createDevicesResponse() {
  return {
    devices: [
      {
        TYPE: "METER-P",
        subtype: "prod",
        CURTIME: "2026,4,3,12,0,0",
        p_3phsum_kw: "4.2",
        net_ltea_3phsum_kwh: "1234.5",
        tot_pf_rto: "0.98"
      },
      {
        TYPE: "METER-C",
        subtype: "cons",
        METER_LOCATION: "house",
        p_3phsum_kw: "2.1",
        v12_v: "240",
        v1n_v: "120",
        v2n_v: "120",
        tot_pf_rto: "0.95"
      },
      {
        DEVICE_TYPE: "PVS",
        MODEL: "PVS-6",
        SWVER: "1.2.3"
      },
      {
        TYPE: "SOLARBRIDGE",
        SERIAL: "PANEL-01",
        p_3phsum_kw: "2.1",
        STATEDESCR: "Producing"
      }
    ]
  };
}

function createReadinessResponse(overrides?: Partial<Record<"status" | "last_successful_ingest_ts" | "max_ingest_age_seconds", unknown>>) {
  return {
    status: "ok",
    checks: {
      database: true,
      migrations: true,
      ingest_fresh: true
    },
    last_successful_ingest_ts: Math.floor(Date.now() / 1000) - 30,
    max_ingest_age_seconds: 180,
    ...overrides
  };
}

function createAlertRecord(overrides?: Partial<Record<string, unknown>>) {
  const baseTimestamp = Math.floor(Date.now() / 1000) - 60;

  return {
    alert_id: Number(overrides?.alert_id ?? 101),
    anomaly_id: null,
    site_id: "site-main",
    dedupe_key: String(overrides?.dedupe_key ?? "production-drop-site-main"),
    kind: (overrides?.kind as "production" | "consumption" | undefined) ?? "production",
    panel_id: null,
    category: String(overrides?.category ?? "baseline"),
    severity: (overrides?.severity as "info" | "warning" | "critical" | undefined) ?? "warning",
    status: (overrides?.status as "open" | "acknowledged" | "resolved" | "suppressed" | undefined) ?? "open",
    state: null,
    title: String(overrides?.title ?? "Low production"),
    message: String(overrides?.message ?? "Production is running below the expected baseline."),
    first_seen_ts: Number(overrides?.first_seen_ts ?? baseTimestamp - 300),
    last_seen_ts: Number(overrides?.last_seen_ts ?? baseTimestamp),
    detected_at_ts: Number(overrides?.detected_at_ts ?? baseTimestamp - 300),
    last_observed_ts: Number(overrides?.last_observed_ts ?? baseTimestamp),
    baseline_kw: Number(overrides?.baseline_kw ?? 4.8),
    observed_kw: Number(overrides?.observed_kw ?? 3.1),
    deviation_kw: Number(overrides?.deviation_kw ?? -1.7),
    deviation_pct: Number(overrides?.deviation_pct ?? -35.4),
    confidence_score: Number(overrides?.confidence_score ?? 0.82),
    affected_panel_count: Number(overrides?.affected_panel_count ?? 1),
    evidence_summary: String(overrides?.evidence_summary ?? "Generation remains below the midday baseline."),
    explanation_payload: {
      kind: String(overrides?.kind ?? "production"),
      source: "system",
      metric: "production_kw",
      direction: "below",
      title: String(overrides?.title ?? "Low production"),
      message: String(overrides?.message ?? "Production is running below the expected baseline."),
      explanation: "Observed production is lower than comparable windows.",
      evidence: {
        baseline_kw: Number(overrides?.baseline_kw ?? 4.8),
        observed_kw: Number(overrides?.observed_kw ?? 3.1)
      },
      sample_ts: Number(overrides?.last_observed_ts ?? baseTimestamp)
    },
    created_at: new Date((baseTimestamp - 300) * 1000).toISOString(),
    updated_at: new Date(baseTimestamp * 1000).toISOString(),
    acknowledged_at: null,
    acknowledged_by: null,
    acknowledged_note: null,
    resolved_at: null,
    resolved_by: null,
    resolution_note: null,
    ...overrides
  };
}

function createAlertsResponse() {
  return {
    items: [
      createAlertRecord(),
      createAlertRecord({
        alert_id: 102,
        dedupe_key: "gateway-retry-site-main",
        kind: "consumption",
        severity: "critical",
        title: "Gateway retry detected",
        message: "Gateway communication recovered after repeated retries.",
        baseline_kw: 2.2,
        observed_kw: 3.4,
        deviation_kw: 1.2,
        deviation_pct: 54.5
      })
    ],
    meta: {
      filtered_total: 2,
      returned: 2,
      open_badge_count: 2,
      open_by_kind: {
        production: 1,
        consumption: 1
      },
      open_by_severity: {
        info: 0,
        warning: 1,
        critical: 1
      }
    }
  };
}

function mockDashboardFetch(options?: {
  historyError?: boolean;
  liveDevicesError?: boolean;
  failLiveAfterFirstSuccess?: boolean;
  failHistoryAfterFirstSuccess?: boolean;
}) {
  let devicesRequestCount = 0;
  let houseSeriesRequestCount = 0;

  return vi.spyOn(window, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input.toString();

    if (url.includes("/config")) {
      return jsonResponse({ lat: null, lon: null });
    }

    if (url.includes("/health/ready")) {
      return jsonResponse(createReadinessResponse());
    }

    if (url.includes("/api/alerts")) {
      return jsonResponse(createAlertsResponse());
    }

    if (url.includes("/api/intelligence/summary")) {
      return jsonResponse({
        generated_at_ts: 1712145600,
        open_counts: {
          total: 2,
          by_kind: {
            production: 1,
            consumption: 1
          },
          by_severity: {
            info: 0,
            warning: 1,
            critical: 1
          }
        },
        production: {
          latest_alert: {
            alert_id: 301,
            kind: "production",
            severity: "warning",
            status: "open",
            title: "Midday production is stable",
            message: "Solar generation is covering household demand with room to export.",
            last_seen_ts: 1712145300,
            evidence_summary: "Production is operating within the expected daytime range."
          },
          latest_anomaly: {
            anomaly_id: 901,
            metric: "production_kw",
            direction: "below",
            severity: "warning",
            sample_ts: 1712145000,
            explanation: "Observed output briefly dipped below the local daylight baseline.",
            evidence: {
              expected_baseline_kw: 4.8,
              actual_production_kw: 4.1
            }
          }
        },
        consumption: {
          latest_alert: {
            alert_id: 302,
            kind: "consumption",
            severity: "critical",
            status: "open",
            title: "Consumption spike anomaly",
            message: "Demand stayed above the expected range.",
            last_seen_ts: 1712145360,
            evidence_summary: "Household demand exceeded the expected midday band."
          },
          latest_anomaly: {
            anomaly_id: 902,
            metric: "consumption_kw",
            direction: "above",
            severity: "critical",
            sample_ts: 1712145060,
            explanation: "Site demand exceeded the comparable baseline window.",
            evidence: {
              expected_range_kw: {
                low: 1.5,
                high: 2.4
              },
              observed_kw: 3.7
            }
          }
        }
      });
    }

    if (url.includes("/devices")) {
      devicesRequestCount += 1;

      if (options?.liveDevicesError || (options?.failLiveAfterFirstSuccess && devicesRequestCount > 1)) {
        return jsonResponse({ detail: "Live gateway unavailable" }, 500);
      }

      return jsonResponse(createDevicesResponse());
    }

    if (url.includes("/house_series")) {
      houseSeriesRequestCount += 1;

      if (options?.historyError || (options?.failHistoryAfterFirstSuccess && houseSeriesRequestCount > 1)) {
        return jsonResponse({ detail: "History backend unavailable" }, 500);
      }

      return jsonResponse({
        samples: [
          { ts: 1712145600, production_kw: 3.9, consumption_kw: 2.2, net_kw: 1.7 },
          { ts: 1712149200, production_kw: 4.1, consumption_kw: 2.4, net_kw: 1.7 }
        ],
        page_info: {
          has_more: false,
          next_cursor: null,
          returned: 2,
          limit: 2000
        }
      });
    }

    if (url.includes("/series")) {
      return jsonResponse({
        samples: [],
        page_info: {
          has_more: false,
          next_cursor: null,
          returned: 0,
          limit: 2000
        }
      });
    }

    throw new Error(`Unhandled fetch request: ${url}`);
  });
}

describe("App shell states", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders the healthy dashboard shell with diagnostics and intelligence", async () => {
    mockDashboardFetch();

    renderWithProviders(<App />);

    await waitFor(() => {
      expect(screen.getByText("Reachable")).toBeInTheDocument();
    });

    expect(screen.getByTestId("dashboard-status-bar")).toBeInTheDocument();
    expect(screen.getByText("Right now")).toBeInTheDocument();
    expect(screen.getByText("Live overview")).toBeInTheDocument();
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Show history")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /insights/i })).toBeInTheDocument();
  });

  it("shows a scoped live error state while keeping shell diagnostics visible", async () => {
    mockDashboardFetch({ liveDevicesError: true });

    renderWithProviders(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("live-error-state")).toBeInTheDocument();
    });

    expect(screen.getByTestId("dashboard-status-bar")).toBeInTheDocument();
    expect(screen.getByText("Live telemetry unavailable")).toBeInTheDocument();
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("keeps the last live snapshot visible when a manual refresh fails", async () => {
    mockDashboardFetch({ failLiveAfterFirstSuccess: true });

    renderWithProviders(<App />);

    await waitFor(() => {
      expect(screen.getByText("Reachable")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => {
      expect(screen.getByTestId("live-error-state")).toBeInTheDocument();
    });

    expect(screen.getByText("Live refresh failed")).toBeInTheDocument();
    expect(screen.getByText("Solar today")).toBeInTheDocument();
    expect(screen.getByText("Today so far")).toBeInTheDocument();
  });

  it("renders the history chart hook on the actual chart node", async () => {
    window.localStorage.setItem(
      "history_filters",
      JSON.stringify({
        from: "2026-04-02T00:00",
        to: "2026-04-03T00:00",
        panel: "",
        interval: "raw"
      })
    );

    mockDashboardFetch();

    renderWithProviders(<App />);

    fireEvent.click(screen.getByRole("button", { name: /show history/i }));

    await waitFor(() => {
      expect(screen.getByTestId("history-chart")).toBeInTheDocument();
    });

    expect(screen.getByTestId("history-apply-button")).toBeInTheDocument();
  });

  it("shows a scoped history error state while keeping the shell diagnostics active", async () => {
    window.localStorage.setItem(
      "history_filters",
      JSON.stringify({
        from: "2026-04-02T00:00",
        to: "2026-04-03T00:00",
        panel: "",
        interval: "raw"
      })
    );

    mockDashboardFetch({ historyError: true });

    renderWithProviders(<App />);

    fireEvent.click(screen.getByRole("button", { name: /show history/i }));

    await waitFor(() => {
      expect(screen.getByTestId("history-error-state")).toBeInTheDocument();
    });

    expect(screen.getByTestId("dashboard-status-bar")).toBeInTheDocument();
    expect(screen.getByText("History backend unavailable")).toBeInTheDocument();
  });

  it("keeps the rendered history chart visible when a refresh fails", async () => {
    window.localStorage.setItem(
      "history_filters",
      JSON.stringify({
        from: "2026-04-02T00:00",
        to: "2026-04-03T00:00",
        panel: "",
        interval: "raw"
      })
    );

    mockDashboardFetch({ failHistoryAfterFirstSuccess: true });

    renderWithProviders(<App />);

    fireEvent.click(screen.getByRole("button", { name: /show history/i }));

    await waitFor(() => {
      expect(screen.getByTestId("history-chart")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));

    await waitFor(() => {
      expect(screen.getByTestId("history-error-state")).toBeInTheDocument();
    });

    expect(screen.getByText("History refresh failed")).toBeInTheDocument();
    expect(screen.getByTestId("history-chart")).toBeInTheDocument();
  });
});
