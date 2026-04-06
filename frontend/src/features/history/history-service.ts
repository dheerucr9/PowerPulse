import {
  BarHistoryInterval,
  ChargerHistorySample,
  ChartPoint,
  HistoryDashboardData,
  HistoryFilters,
  HouseSample,
  PaginatedSamplesResponse,
  PanelSample
} from "@/api/models";
import { fetchJson } from "@/api/client";
import { parseLocalInput, toLocalInput } from "@/lib/date-time";

const COMPARISON_SOURCE_INTERVAL = "1h";

const comparisonConfig: Record<BarHistoryInterval, { bucketCount: number; label: string }> = {
  day: { bucketCount: 7, label: "Last 7 days" },
  week: { bucketCount: 8, label: "Last 8 weeks" },
  month: { bucketCount: 12, label: "Last 12 months" }
};

export function getTodayFilters(): HistoryFilters {
  const now = new Date();
  const todayMidnight = new Date(now);
  todayMidnight.setHours(0, 0, 0, 0);

  return {
    from: toLocalInput(todayMidnight),
    to: toLocalInput(now),
    panel: "",
    interval: "raw"
  };
}

export function extractTodayFromHistory(historyData: HistoryDashboardData | null): HistoryDashboardData | null {
  if (!historyData) {
    return null;
  }

  const now = new Date();
  const todayMidnight = new Date(now);
  todayMidnight.setHours(0, 0, 0, 0);
  const todayStartTs = todayMidnight.getTime() / 1000;
  const todayEndTs = now.getTime() / 1000;

  function filterToRange(series: ChartPoint[]) {
    return series.filter((point) => point.ts >= todayStartTs && point.ts <= todayEndTs);
  }

  return {
    data: {
      production: filterToRange(historyData.data.production),
      consumption: filterToRange(historyData.data.consumption),
      net: filterToRange(historyData.data.net),
      panel: filterToRange(historyData.data.panel),
      charger: filterToRange(historyData.data.charger)
    },
    panelLabel: historyData.panelLabel
  };
}

function toSeries<TSample extends { ts: number }>(samples: TSample[], key: keyof TSample) {
  return samples
    .filter((sample) => sample[key] != null)
    .map((sample) => ({
      ts: Number(sample.ts),
      val: Number(sample[key])
    }))
    .filter((sample) => Number.isFinite(sample.ts) && Number.isFinite(sample.val));
}

async function fetchAllPages<TSample>(path: string, query: Record<string, string>) {
  const samples: TSample[] = [];
  let cursor: string | null | undefined;

  do {
    const page = await fetchJson<PaginatedSamplesResponse<TSample>>(path, {
      query: {
        ...query,
        limit: "2000",
        cursor
      }
    });

    samples.push(...(page.samples ?? []));
    cursor = page.page_info?.has_more ? page.page_info.next_cursor : null;
  } while (cursor);

  return samples;
}

function parseFilterTimestamp(value: string | null, fallback: Date) {
  const parsed = parseLocalInput(value);
  return Math.floor((parsed ?? fallback).getTime() / 1000);
}

function buildHistoryRange(filters: Pick<HistoryFilters, "from" | "to">) {
  const now = new Date();
  const fallbackFrom = new Date(now.getTime() - 24 * 3600 * 1000);
  const fromTimestamp = parseFilterTimestamp(filters.from, fallbackFrom);
  const toTimestamp = parseFilterTimestamp(filters.to, now);

  if (!Number.isFinite(fromTimestamp) || !Number.isFinite(toTimestamp)) {
    throw new Error("History filters must include a valid start and end range.");
  }

  if (fromTimestamp >= toTimestamp) {
    throw new Error("History filters must include a start that is earlier than the end.");
  }

  return {
    fromTimestamp,
    toTimestamp
  };
}

function getStartOfDay(date: Date) {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

function getStartOfWeek(date: Date) {
  const next = getStartOfDay(date);
  const day = next.getDay();
  const offset = day === 0 ? 6 : day - 1;
  next.setDate(next.getDate() - offset);
  return next;
}

function getStartOfMonth(date: Date) {
  const next = getStartOfDay(date);
  next.setDate(1);
  return next;
}

function shiftBucket(date: Date, interval: BarHistoryInterval, amount: number) {
  const next = new Date(date);

  if (interval === "day") {
    next.setDate(next.getDate() + amount);
    return next;
  }

  if (interval === "week") {
    next.setDate(next.getDate() + amount * 7);
    return next;
  }

  next.setMonth(next.getMonth() + amount);
  return next;
}

function getBucketStart(date: Date, interval: BarHistoryInterval) {
  if (interval === "day") {
    return getStartOfDay(date);
  }

  if (interval === "week") {
    return getStartOfWeek(date);
  }

  return getStartOfMonth(date);
}

function buildComparisonWindow(anchorInput: string | null, interval: BarHistoryInterval) {
  const anchor = parseLocalInput(anchorInput) ?? new Date();
  const normalizedAnchor = new Date(anchor);
  normalizedAnchor.setSeconds(0, 0);

  const bucketCount = comparisonConfig[interval].bucketCount;
  const currentBucketStart = getBucketStart(normalizedAnchor, interval);
  const bucketStarts = Array.from({ length: bucketCount }, (_, index) => {
    const offset = index - (bucketCount - 1);
    return shiftBucket(currentBucketStart, interval, offset);
  });
  const rangeStart = bucketStarts[0];

  return {
    bucketStarts,
    label: comparisonConfig[interval].label,
    fromTimestamp: Math.floor(rangeStart.getTime() / 1000),
    toTimestamp: Math.floor(normalizedAnchor.getTime() / 1000)
  };
}

function aggregateSeriesToBuckets(points: ChartPoint[], interval: BarHistoryInterval, bucketStarts: Date[], rangeEndTimestamp: number) {
  if (points.length < 2 || bucketStarts.length === 0) {
    return [];
  }

  const sortedPoints = [...points].sort((left, right) => left.ts - right.ts);
  const bucketStartsMs = bucketStarts.map((bucket) => bucket.getTime());
  const bucketTotals = bucketStartsMs.map(() => 0);
  const rangeStartMs = bucketStartsMs[0];
  const rangeEndMs = rangeEndTimestamp * 1000;

  const resolveBucketIndex = (timestampMs: number) => {
    for (let index = bucketStartsMs.length - 1; index >= 0; index -= 1) {
      if (timestampMs >= bucketStartsMs[index]) {
        return index;
      }
    }

    return -1;
  };

  for (let index = 1; index < sortedPoints.length; index += 1) {
    const previous = sortedPoints[index - 1];
    const current = sortedPoints[index];
    const averageKw = Math.max((previous.val + current.val) / 2, 0);

    if (!Number.isFinite(averageKw)) {
      continue;
    }

    let segmentStartMs = Math.max(previous.ts * 1000, rangeStartMs);
    const segmentEndMs = Math.min(current.ts * 1000, rangeEndMs);

    if (segmentEndMs <= segmentStartMs) {
      continue;
    }

    while (segmentStartMs < segmentEndMs) {
      const bucketIndex = resolveBucketIndex(segmentStartMs);

      if (bucketIndex < 0) {
        break;
      }

      const nextBoundaryMs = bucketIndex === bucketStartsMs.length - 1
        ? rangeEndMs
        : Math.min(shiftBucket(bucketStarts[bucketIndex], interval, 1).getTime(), rangeEndMs);
      const sliceEndMs = Math.min(segmentEndMs, nextBoundaryMs);
      const durationHours = Math.max(0, (sliceEndMs - segmentStartMs) / 36e5);

      bucketTotals[bucketIndex] += averageKw * durationHours;
      segmentStartMs = sliceEndMs;
    }
  }

  const hasData = bucketTotals.some((value) => value > 0);

  if (!hasData) {
    return [];
  }

  return bucketStarts.map((bucketStart, index) => ({
    ts: Math.floor(bucketStart.getTime() / 1000),
    val: Number(bucketTotals[index].toFixed(2))
  }));
}

export function getComparisonWindowLabel(interval: BarHistoryInterval) {
  return comparisonConfig[interval].label;
}

export async function getHistoryDashboardData(filters: HistoryFilters): Promise<HistoryDashboardData> {
  const { fromTimestamp, toTimestamp } = buildHistoryRange(filters);
  const query = {
    from: String(fromTimestamp),
    to: String(toTimestamp),
    interval: filters.interval
  };

  const houseSamples = await fetchAllPages<HouseSample>("/house_series", query);
  const chargerSamples = await fetchAllPages<ChargerHistorySample>("/charger/history", query);
  const panelSamples = filters.panel
    ? await fetchAllPages<PanelSample>("/series", {
        ...query,
        panel_id: filters.panel
      })
    : [];

  return {
    data: {
      production: toSeries(houseSamples, "production_kw"),
      consumption: toSeries(houseSamples, "consumption_kw"),
      net: toSeries(houseSamples, "net_kw"),
      panel: toSeries(panelSamples, "p_kw"),
      charger: toSeries(chargerSamples, "power_kw")
    },
    panelLabel: filters.panel || "Panel"
  };
}

export async function getHistoryComparisonData(anchorInput: string | null, interval: BarHistoryInterval): Promise<HistoryDashboardData> {
  const window = buildComparisonWindow(anchorInput, interval);
  const paddedFromTimestamp = Math.max(0, window.fromTimestamp - 3600);
  const query = {
    from: String(paddedFromTimestamp),
    to: String(window.toTimestamp),
    interval: COMPARISON_SOURCE_INTERVAL
  };

  const [houseSamples, chargerSamples] = await Promise.all([
    fetchAllPages<HouseSample>("/series", query),
    fetchAllPages<ChargerHistorySample>("/charger/history", query)
  ]);

  const productionSeries = aggregateSeriesToBuckets(toSeries(houseSamples, "production_kw"), interval, window.bucketStarts, window.toTimestamp);
  const consumptionSeries = aggregateSeriesToBuckets(toSeries(houseSamples, "consumption_kw"), interval, window.bucketStarts, window.toTimestamp);
  const chargerSeries = aggregateSeriesToBuckets(toSeries(chargerSamples, "power_kw"), interval, window.bucketStarts, window.toTimestamp);
  const netSeries = aggregateSeriesToBuckets(toSeries(houseSamples, "net_kw"), interval, window.bucketStarts, window.toTimestamp);

  return {
    data: {
      production: productionSeries,
      consumption: consumptionSeries,
      charger: chargerSeries,
      net: netSeries,
      panel: []
    },
    panelLabel: window.label
  };
}
