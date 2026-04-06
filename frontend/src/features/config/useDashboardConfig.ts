import { useQuery } from "@tanstack/react-query";

import { fetchJson } from "@/api/client";
import { DashboardConfig } from "@/api/models";

export function useDashboardConfig() {
  return useQuery({
    queryKey: ["dashboard-config"],
    queryFn: () => fetchJson<DashboardConfig>("/config"),
    staleTime: Number.POSITIVE_INFINITY
  });
}
