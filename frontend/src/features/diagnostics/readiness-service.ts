import { fetchJson } from "@/api/client";
import { ReadinessResponse } from "@/api/models";

export async function getReadiness() {
  return fetchJson<ReadinessResponse>("/health/ready");
}
