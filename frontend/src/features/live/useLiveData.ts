import { useQuery } from "@tanstack/react-query";

import { getLiveDashboardData } from "@/features/live/live-service";

export function useLiveData(locationSearch: string) {
  return useQuery({
    queryKey: ["live-dashboard-data", locationSearch],
    queryFn: () => getLiveDashboardData(locationSearch),
    refetchInterval: 20_000
  });
}
