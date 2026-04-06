import { DraftHistoryInterval, HistoryFilters, HistoryInterval } from "@/api/models";
import { parseLocalInput, toLocalInput } from "@/lib/date-time";

export function pickIntervalForRange(from: Date, to: Date): HistoryInterval {
  const spanHours = Math.abs((to.getTime() - from.getTime()) / 36e5);

  if (spanHours > 24 * 14) {
    return "1h";
  }

  if (spanHours > 36) {
    return "5m";
  }

  return "raw";
}

export function resolveDraftInterval(
  draftInterval: DraftHistoryInterval,
  draftRange: Pick<HistoryFilters, "from" | "to">,
  appliedInterval: HistoryInterval
) {
  if (draftInterval !== "auto") {
    return draftInterval;
  }

  const from = parseLocalInput(draftRange.from);
  const to = parseLocalInput(draftRange.to);

  if (!from || !to) {
    return appliedInterval;
  }

  return pickIntervalForRange(from, to);
}

export function createPresetRange(preset: "today" | "24h" | "7d" | "30d" | "yesterday") {
  const to = new Date();
  const from = new Date(to);

  if (preset === "today") {
    from.setHours(0, 0, 0, 0);
  } else if (preset === "yesterday") {
    from.setDate(to.getDate() - 1);
    from.setHours(0, 0, 0, 0);
    to.setHours(0, 0, 0, 0);
  } else if (preset === "24h") {
    from.setHours(to.getHours() - 24);
  } else if (preset === "7d") {
    from.setDate(to.getDate() - 7);
  } else if (preset === "30d") {
    from.setDate(to.getDate() - 30);
  }

  return {
    range: {
      from: toLocalInput(from),
      to: toLocalInput(to)
    },
    interval: pickIntervalForRange(from, to)
  };
}

export function createRelativeRange(minutesAgo: number) {
  const now = new Date();
  const from = new Date(now.getTime() - minutesAgo * 60 * 1000);
  const spanHours = minutesAgo / 60;
  const interval: HistoryInterval = spanHours >= 6 ? "1h" : spanHours >= 1 ? "5m" : "raw";
  return {
    range: {
      from: toLocalInput(from),
      to: toLocalInput(now)
    },
    interval
  };
}
