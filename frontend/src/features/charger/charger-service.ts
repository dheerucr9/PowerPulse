import { fetchJson } from "@/api/client";
import { ChargerSnapshot } from "@/api/models";

interface ChargerSnapshotResponse {
  ts?: unknown;
  vehicle_connected?: unknown;
  contactor_closed?: unknown;
  charging?: unknown;
  power_kw?: unknown;
  session_energy_wh?: unknown;
  lifetime_energy_wh?: unknown;
  pcba_temp_c?: unknown;
  handle_temp_c?: unknown;
}

function toNumber(value: unknown) {
  const parsed = Number.parseFloat(String(value ?? 0));
  return Number.isFinite(parsed) ? parsed : 0;
}

function toBoolean(value: unknown) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "number") {
    return value !== 0;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return ["true", "1", "yes", "on"].includes(normalized);
  }

  return false;
}

export async function getChargerSnapshot(): Promise<ChargerSnapshot> {
  const response = await fetchJson<ChargerSnapshotResponse>("/charger/latest");

  return {
    ts: toNumber(response.ts),
    vehicle_connected: toBoolean(response.vehicle_connected),
    contactor_closed: toBoolean(response.contactor_closed),
    charging: toBoolean(response.charging),
    power_kw: toNumber(response.power_kw),
    session_energy_wh: toNumber(response.session_energy_wh),
    lifetime_energy_wh: toNumber(response.lifetime_energy_wh),
    pcba_temp_c: toNumber(response.pcba_temp_c),
    handle_temp_c: toNumber(response.handle_temp_c)
  };
}
