import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Coordinates,
  DashboardTab,
  DraftHistoryInterval,
  HistoryFilters,
  HistoryInterval
} from "@/api/models";
import { createPresetRange, createRelativeRange, resolveDraftInterval } from "@/features/history/history-utils";

const TAB_STORAGE_KEY = "tab";
const HISTORY_FILTERS_STORAGE_KEY = "history_filters";
const LAT_LON_STORAGE_KEY = "latlon";

const defaultCoordinates: Coordinates = {
  lat: 37.7749,
  lon: -122.4194
};

type DateRange = {
  from: string | null;
  to: string | null;
};

function readStoredJson<TValue>(key: string) {
  const raw = window.localStorage.getItem(key);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as TValue;
  } catch {
    return null;
  }
}

function resolveInitialCoordinates(search: string) {
  const params = new URLSearchParams(search);
  const lat = Number.parseFloat(params.get("lat") ?? "");
  const lon = Number.parseFloat(params.get("lon") ?? "");

  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    const coordinates = { lat, lon };
    window.localStorage.setItem(LAT_LON_STORAGE_KEY, JSON.stringify(coordinates));
    return coordinates;
  }

  const stored = readStoredJson<Coordinates>(LAT_LON_STORAGE_KEY);

  if (stored && Number.isFinite(stored.lat) && Number.isFinite(stored.lon)) {
    return stored;
  }

  return defaultCoordinates;
}

function resolveInitialHistoryState() {
  const stored = readStoredJson<{
    from?: string;
    to?: string;
    panel?: string;
    interval?: HistoryInterval;
  }>(HISTORY_FILTERS_STORAGE_KEY);

  if (!stored?.from || !stored?.to) {
  return {
      appliedRange: { from: null, to: null } as DateRange,
      draftRange: { from: null, to: null } as DateRange,
      appliedPanel: "",
      draftPanel: "",
      appliedInterval: "raw" as HistoryInterval,
      draftInterval: "raw" as DraftHistoryInterval,
      activePreset: "24h" as const
    };
  }

  const panel = stored.panel ?? "";
  const interval = stored.interval ?? "raw";
  const range = { from: stored.from, to: stored.to };

  return {
    appliedRange: range,
    draftRange: range,
    appliedPanel: panel,
    draftPanel: panel,
    appliedInterval: interval,
    draftInterval: interval,
    activePreset: "custom" as const
  };
}

export function useDashboardShellState(locationSearch: string) {
  const initialHistoryState = resolveInitialHistoryState();

  const [tab, setTab] = useState<DashboardTab>(() => {
    const storedTab = window.localStorage.getItem(TAB_STORAGE_KEY);
    return storedTab === "history" ? "history" : "live";
  });
  const [appliedRange, setAppliedRange] = useState<DateRange>(initialHistoryState.appliedRange);
  const [draftRange, setDraftRange] = useState<DateRange>(initialHistoryState.draftRange);
  const [appliedPanel, setAppliedPanel] = useState(initialHistoryState.appliedPanel);
  const [draftPanel, setDraftPanel] = useState(initialHistoryState.draftPanel);
  const [appliedInterval, setAppliedInterval] = useState<HistoryInterval>(initialHistoryState.appliedInterval);
  const [draftInterval, setDraftInterval] = useState<DraftHistoryInterval>(initialHistoryState.draftInterval);
  const [activePreset, setActivePreset] = useState<"last15m" | "last30m" | "last1h" | "last6h" | "last12h" | "today" | "yesterday" | "24h" | "7d" | "30d" | "custom">(
    initialHistoryState.activePreset
  );
  const [latLon, setLatLonState] = useState<Coordinates>(() => resolveInitialCoordinates(locationSearch));

  useEffect(() => {
    window.localStorage.setItem(TAB_STORAGE_KEY, tab);
  }, [tab]);

  useEffect(() => {
    if (!appliedRange.from || !appliedRange.to) {
      return;
    }

    window.localStorage.setItem(
      HISTORY_FILTERS_STORAGE_KEY,
      JSON.stringify({
        from: appliedRange.from,
        to: appliedRange.to,
        panel: appliedPanel,
        interval: appliedInterval
      })
    );
  }, [appliedInterval, appliedPanel, appliedRange.from, appliedRange.to]);

  const resolvedDraftHistoryInterval = useMemo(
    () => resolveDraftInterval(draftInterval, draftRange, appliedInterval),
    [appliedInterval, draftInterval, draftRange]
  );

  const hasPendingHistoryChanges =
    draftRange.from !== appliedRange.from ||
    draftRange.to !== appliedRange.to ||
    draftPanel !== appliedPanel ||
    resolvedDraftHistoryInterval !== appliedInterval;

  const applyPreset = useCallback((preset: "today" | "yesterday" | "24h" | "7d" | "30d") => {
    const next = createPresetRange(preset);

    setActivePreset(preset);
    setDraftRange(next.range);
    setAppliedRange(next.range);
    setDraftInterval(next.interval);
    setAppliedInterval(next.interval);
  }, []);

  const applyRelative = useCallback((preset: "last15m" | "last30m" | "last1h" | "last6h" | "last12h") => {
    const minutesMap = { last15m: 15, last30m: 30, last1h: 60, last6h: 360, last12h: 720 } as const;
    const next = createRelativeRange(minutesMap[preset]);

    setActivePreset(preset);
    setDraftRange(next.range);
    setAppliedRange(next.range);
    setDraftInterval(next.interval);
    setAppliedInterval(next.interval);
  }, []);

  const applyHistoryFilters = useCallback(() => {
    setAppliedRange(draftRange);
    setAppliedPanel(draftPanel);
    setAppliedInterval(resolvedDraftHistoryInterval);

    if (activePreset !== "custom") {
      setActivePreset("custom");
    }
  }, [activePreset, draftPanel, draftRange, resolvedDraftHistoryInterval]);

  const resetHistoryFilters = useCallback(() => {
    setDraftRange(appliedRange);
    setDraftPanel(appliedPanel);
    setDraftInterval(appliedInterval);
  }, [appliedInterval, appliedPanel, appliedRange]);

  const setLatLon = useCallback((coordinates: Coordinates) => {
    setLatLonState(coordinates);
    window.localStorage.setItem(LAT_LON_STORAGE_KEY, JSON.stringify(coordinates));
  }, []);

  return {
    tab,
    setTab,
    appliedRange,
    draftRange,
    setDraftRange,
    appliedPanel,
    draftPanel,
    setDraftPanel,
    appliedInterval,
    draftInterval,
    setDraftInterval,
    activePreset,
    setActivePreset,
    latLon,
    setLatLon,
    resolvedDraftHistoryInterval,
    hasPendingHistoryChanges,
    applyPreset,
    applyRelative,
    applyHistoryFilters,
    resetHistoryFilters,
    historyFilters: {
      from: appliedRange.from,
      to: appliedRange.to,
      panel: appliedPanel,
      interval: appliedInterval
    } satisfies HistoryFilters
  };
}
