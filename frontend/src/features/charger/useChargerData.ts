import { useQuery } from "@tanstack/react-query";

import { getChargerSnapshot } from "@/features/charger/charger-service";

export function useChargerData() {
  return useQuery({
    queryKey: ["charger-data"],
    queryFn: getChargerSnapshot,
    refetchInterval: 30_000
  });
}
