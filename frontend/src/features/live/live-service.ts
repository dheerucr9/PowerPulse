import { fetchJson, getGatewayQuery } from "@/api/client";
import { DevicesResponse, LiveDashboardData } from "@/api/models";
import { deriveConsumption, pickMeter } from "@/features/live/live-utils";

function safeFloat(value: unknown) {
  const parsed = Number.parseFloat(String(value ?? 0));
  return Number.isFinite(parsed) ? parsed : 0;
}

export async function getLiveDashboardData(locationSearch: string) {
  const response = await fetchJson<DevicesResponse>("/devices", {
    query: getGatewayQuery(locationSearch)
  });

  const devices = response.devices ?? [];
  const productionMeter = pickMeter(devices, "prod");
  const consumptionMeter = pickMeter(devices, "cons");
  const gateway = devices.find((device) => device.DEVICE_TYPE === "PVS");
  const panels = devices.filter((device) => device.TYPE === "SOLARBRIDGE");

  const production = safeFloat(productionMeter.p_3phsum_kw);
  const rawConsumption = safeFloat(consumptionMeter.p_3phsum_kw);
  const consumption = deriveConsumption(rawConsumption, production) ?? 0;
  const net = production - consumption;

  const liveData: LiveDashboardData = {
    live: {
      production,
      consumption,
      net,
      lifetime: safeFloat(productionMeter.net_ltea_3phsum_kwh),
      vsys: consumptionMeter.v12_v,
      v1: consumptionMeter.v1n_v,
      v2: consumptionMeter.v2n_v,
      pfProd: productionMeter.tot_pf_rto,
      pfCons: consumptionMeter.tot_pf_rto,
      updated: typeof productionMeter.CURTIME === "string" ? productionMeter.CURTIME : undefined
    },
    panels,
    meta: {
      gw: gateway
    }
  };

  return liveData;
}
