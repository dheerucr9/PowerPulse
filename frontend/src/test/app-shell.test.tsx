import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useDashboardShellState } from "@/features/shell/useDashboardShellState";

describe("useDashboardShellState", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("hydrates the selected tab and history filters from localStorage", () => {
    window.localStorage.setItem("tab", "history");
    window.localStorage.setItem(
      "history_filters",
      JSON.stringify({
        from: "2026-03-01T12:00",
        to: "2026-03-02T12:00",
        panel: "PANEL-01",
        interval: "5m"
      })
    );

    const { result } = renderHook(() => useDashboardShellState(""));

    expect(result.current.tab).toBe("history");
    expect(result.current.historyFilters).toEqual({
      from: "2026-03-01T12:00",
      to: "2026-03-02T12:00",
      panel: "PANEL-01",
      interval: "5m"
    });
    expect(result.current.activePreset).toBe("custom");
  });

  it("applies presets and persists the chosen range", () => {
    const { result } = renderHook(() => useDashboardShellState(""));

    act(() => {
      result.current.applyPreset("24h");
      result.current.setTab("history");
    });

    const savedFilters = JSON.parse(window.localStorage.getItem("history_filters") ?? "{}");

    expect(result.current.historyFilters.from).toBeTruthy();
    expect(result.current.historyFilters.to).toBeTruthy();
    expect(result.current.historyFilters.interval).toBe("raw");
    expect(savedFilters.interval).toBe("raw");
    expect(window.localStorage.getItem("tab")).toBe("history");
  });
});
