import { useQuery } from "@tanstack/react-query";

import { BarHistoryInterval, HistoryFilters } from "@/api/models";
import { getHistoryComparisonData, getHistoryDashboardData } from "@/features/history/history-service";

export function useHistoryData(filters: HistoryFilters, enabled: boolean) {
  return useQuery({
    queryKey: ["history-dashboard-data", filters.from, filters.to, filters.panel, filters.interval],
    queryFn: () => getHistoryDashboardData(filters),
    enabled
  });
}

export function useHistoryComparisonData(anchorInput: string | null, interval: BarHistoryInterval, enabled: boolean) {
  return useQuery({
    queryKey: ["history-comparison-data", anchorInput, interval],
    queryFn: () => getHistoryComparisonData(anchorInput, interval),
    enabled
  });
}
