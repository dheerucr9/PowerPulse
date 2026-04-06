import userEvent from "@testing-library/user-event";
import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AlertCenter } from "@/components/alerts/AlertCenter";
import { renderWithProviders } from "@/test/test-utils";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function createAlertRecord(overrides?: Partial<Record<string, unknown>>) {
  const baseTimestamp = Math.floor(Date.now() / 1000) - 120;

  return {
    alert_id: Number(overrides?.alert_id ?? 201),
    anomaly_id: null,
    site_id: "site-main",
    dedupe_key: String(overrides?.dedupe_key ?? `alert-${overrides?.alert_id ?? 201}`),
    kind: (overrides?.kind as "production" | "consumption" | undefined) ?? "production",
    panel_id: (overrides?.panel_id as string | null | undefined) ?? null,
    category: String(overrides?.category ?? "baseline"),
    severity: (overrides?.severity as "info" | "warning" | "critical" | undefined) ?? "warning",
    status: (overrides?.status as "open" | "acknowledged" | "resolved" | "suppressed" | undefined) ?? "open",
    state: (overrides?.state as string | null | undefined) ?? null,
    title: String(overrides?.title ?? "Low production"),
    message: String(overrides?.message ?? "Production is running below the expected baseline."),
    first_seen_ts: Number(overrides?.first_seen_ts ?? baseTimestamp - 600),
    last_seen_ts: Number(overrides?.last_seen_ts ?? baseTimestamp),
    detected_at_ts: Number(overrides?.detected_at_ts ?? baseTimestamp - 600),
    last_observed_ts: Number(overrides?.last_observed_ts ?? baseTimestamp),
    baseline_kw: (overrides?.baseline_kw as number | null | undefined) ?? 4.8,
    observed_kw: (overrides?.observed_kw as number | null | undefined) ?? 3.1,
    deviation_kw: (overrides?.deviation_kw as number | null | undefined) ?? -1.7,
    deviation_pct: (overrides?.deviation_pct as number | null | undefined) ?? -35.4,
    confidence_score: (overrides?.confidence_score as number | null | undefined) ?? 0.82,
    affected_panel_count: (overrides?.affected_panel_count as number | null | undefined) ?? 2,
    evidence_summary: String(overrides?.evidence_summary ?? "Generation remains below the midday baseline."),
    explanation_payload: {
      kind: String(overrides?.kind ?? "production"),
      source: String(overrides?.source ?? "system"),
      metric: String(overrides?.metric ?? "production_kw"),
      direction: String(overrides?.direction ?? "below"),
      title: String(overrides?.title ?? "Low production"),
      message: String(overrides?.message ?? "Production is running below the expected baseline."),
      explanation: String(overrides?.explanation ?? "Observed output is lower than similar daylight windows."),
      evidence: (overrides?.evidence as Record<string, unknown> | undefined) ?? {
        expected_baseline_kw: 4.8,
        actual_production_kw: 3.1,
        percent_deviation: -35.4,
        affected_panel_count: 2,
        daylight: {
          is_daylight: true,
          sunrise_ts: baseTimestamp - 14_400,
          sunset_ts: baseTimestamp + 14_400
        },
        peer_underperforming_panels: [
          {
            panel_id: "PANEL-01",
            peer_median_kw: 0.9,
            p_kw: 0.2
          }
        ]
      },
      sample_ts: Number(overrides?.last_observed_ts ?? baseTimestamp)
    },
    created_at: new Date((baseTimestamp - 600) * 1000).toISOString(),
    updated_at: new Date(baseTimestamp * 1000).toISOString(),
    acknowledged_at: (overrides?.acknowledged_at as string | null | undefined) ?? null,
    acknowledged_by: (overrides?.acknowledged_by as string | null | undefined) ?? null,
    acknowledged_note: (overrides?.acknowledged_note as string | null | undefined) ?? null,
    resolved_at: null,
    resolved_by: null,
    resolution_note: null,
    ...overrides
  };
}

function buildAlertsResponse(items: Array<ReturnType<typeof createAlertRecord>>) {
  const openItems = items.filter((item) => item.status === "open");

  return {
    items,
    meta: {
      filtered_total: items.length,
      returned: items.length,
      open_badge_count: openItems.length,
      open_by_kind: {
        production: openItems.filter((item) => item.kind === "production").length,
        consumption: openItems.filter((item) => item.kind === "consumption").length
      },
      open_by_severity: {
        info: openItems.filter((item) => item.severity === "info").length,
        warning: openItems.filter((item) => item.severity === "warning").length,
        critical: openItems.filter((item) => item.severity === "critical").length
      }
    }
  };
}

function installAlertFetchMock(options: {
  initialAlerts: Array<ReturnType<typeof createAlertRecord>>;
  failAcknowledge?: boolean;
}) {
  let alerts = [...options.initialAlerts];

  return vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const requestUrl = new URL(url, window.location.origin);
    const status = requestUrl.searchParams.get("status");
    const kind = requestUrl.searchParams.get("kind");

    if (requestUrl.pathname === "/api/alerts" && (init?.method ?? "GET") === "GET") {
      const items = alerts.filter((alert) => {
        const matchesStatus = status ? alert.status === status : true;
        const matchesKind = kind ? alert.kind === kind : true;
        return matchesStatus && matchesKind;
      });

      return jsonResponse(buildAlertsResponse(items));
    }

    const acknowledgeMatch = requestUrl.pathname.match(/^\/api\/alerts\/(\d+)\/acknowledge$/);

    if (acknowledgeMatch) {
      if (options.failAcknowledge) {
        await new Promise((resolve) => setTimeout(resolve, 40));
        return jsonResponse({ detail: "Acknowledge request failed" }, 500);
      }

      const alertId = Number(acknowledgeMatch[1]);
      const body = JSON.parse(String(init?.body ?? "{}"));

      alerts = alerts.map((alert) =>
        alert.alert_id === alertId
          ? {
              ...alert,
              status: body.new_status,
              acknowledged_at: "2026-04-03T12:15:00Z",
              acknowledged_by: body.acknowledged_by,
              acknowledged_note: body.note
            }
          : alert
      );

      const updatedAlert = alerts.find((alert) => alert.alert_id === alertId);

      return jsonResponse(updatedAlert);
    }

    throw new Error(`Unhandled fetch request: ${url}`);
  });
}

describe("AlertCenter", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the empty state when no alerts match", async () => {
    installAlertFetchMock({ initialAlerts: [] });

    renderWithProviders(<AlertCenter />);

    expect(await screen.findByText("No alerts")).toBeInTheDocument();
    expect(screen.getByText("All alerts · 0 results")).toBeInTheDocument();
  });

  it("filters by kind with the compact scope control", async () => {
    installAlertFetchMock({
      initialAlerts: [
        createAlertRecord(),
        createAlertRecord({
          alert_id: 202,
          kind: "consumption",
          category: "demand",
          severity: "critical",
          title: "Consumption spike anomaly",
          message: "Demand stayed above the expected range.",
          baseline_kw: 2.1,
          observed_kw: 3.7,
          deviation_kw: 1.6,
          deviation_pct: 76.2,
          evidence: {
            pattern_type: "spike",
            is_spike_like: true,
            duration_seconds: 300,
            expected_range_kw: {
              low: 1.5,
              high: 2.4,
              baseline: 2.1,
              stddev: 0.2
            },
            solar_context: {
              production_kw: 1.4,
              demand_exceeds_solar: true,
              demand_exceeds_solar_by_kw: 2.3
            }
          }
        })
      ]
    });

    const user = userEvent.setup();
    renderWithProviders(<AlertCenter />);

    const scopeFilter = await screen.findByLabelText("Filter alerts by type");
    await user.selectOptions(scopeFilter, "consumption");

    await waitFor(() => {
      expect(screen.getByText("Consumption only · 1 result")).toBeInTheDocument();
    });

    const visibleCard = screen.getByTestId("alert-card-202");
    expect(visibleCard).toBeInTheDocument();
    expect(visibleCard).toHaveTextContent("Consumption spike anomaly");
    expect(screen.queryByTestId("alert-card-201")).not.toBeInTheDocument();
  });

  it("acknowledges an alert successfully and keeps the change after refetch", async () => {
    installAlertFetchMock({ initialAlerts: [createAlertRecord()] });

    const user = userEvent.setup();
    renderWithProviders(<AlertCenter />);

    await user.click(await screen.findByTestId("alert-card-201"));
    await user.click(screen.getByTestId("acknowledge-submit-button"));

    await waitFor(() => {
      expect(screen.queryByText("Low production")).not.toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("No alerts")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("alert-filter-all"));

    const acknowledgedCard = await screen.findByTestId("alert-card-201");
    expect(acknowledgedCard).toHaveTextContent("Low production");

    await user.click(acknowledgedCard);
    expect(within(acknowledgedCard).getByText("Acknowledged")).toBeInTheDocument();
    expect(within(acknowledgedCard).getByTestId("alert-status-201")).toHaveTextContent("acknowledged");
  });

  it("rolls optimistic acknowledgement updates back on failure", async () => {
    installAlertFetchMock({ initialAlerts: [createAlertRecord()], failAcknowledge: true });

    const user = userEvent.setup();
    renderWithProviders(<AlertCenter />);

    await user.click(await screen.findByTestId("alert-card-201"));
    await user.click(screen.getByTestId("acknowledge-submit-button"));

    await waitFor(() => {
      expect(screen.getByTestId("alert-card-201")).toHaveTextContent("Acknowledge");
    });

    expect(await screen.findByTestId("acknowledge-error")).toBeInTheDocument();
    expect(screen.getByTestId("alert-status-201")).toHaveTextContent("open");
  });
});
