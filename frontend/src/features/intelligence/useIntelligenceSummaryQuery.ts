import { useQuery } from "@tanstack/react-query";

import { fetchOptionalJson } from "@/api/client";
import { IntelligenceSummaryResponse } from "@/api/models";

const emptySummary: IntelligenceSummaryResponse = {
  generated_at_ts: 0,
  open_counts: {
    total: 0,
    by_kind: {
      production: 0,
      consumption: 0
    },
    by_severity: {
      info: 0,
      warning: 0,
      critical: 0
    }
  },
  production: {
    latest_alert: null,
    latest_anomaly: null
  },
  consumption: {
    latest_alert: null,
    latest_anomaly: null
  }
};

export function useIntelligenceSummaryQuery() {
  return useQuery({
    queryKey: ["intelligence-summary"],
    queryFn: () => fetchOptionalJson<IntelligenceSummaryResponse>("/api/intelligence/summary", emptySummary)
  });
}
