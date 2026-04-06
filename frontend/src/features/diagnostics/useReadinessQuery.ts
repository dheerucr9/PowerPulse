import { useQuery } from "@tanstack/react-query";

import { getReadiness } from "@/features/diagnostics/readiness-service";

export function useReadinessQuery() {
  return useQuery({
    queryKey: ["system-readiness"],
    queryFn: getReadiness,
    refetchInterval: 20_000
  });
}
