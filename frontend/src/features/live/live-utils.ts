import { GatewayDevice } from "@/api/models";

export const chartPalette = {
  production: "#1A7F64",
  consumption: "#B8860B",
  net: "#4A6FA5",
  panel: "#8B7F72",
  charger: "#E67E22"
} as const;

export function deriveConsumption(consumption: number | null, production: number | null) {
  if (consumption == null) {
    return null;
  }

  if (production == null) {
    return consumption;
  }

  if (consumption < 0) {
    return Math.max(production + consumption, 0);
  }

  return consumption;
}

export function pickMeter(devices: GatewayDevice[], role: "prod" | "cons") {
  for (const device of devices) {
    const type = (device.TYPE ?? "").toUpperCase();
    const subtype = (device.subtype ?? "").toLowerCase();
    const meterLocation = (device.METER_LOCATION ?? "").toLowerCase();

    if (role === "prod" && (type.includes("-P") || subtype.includes("prod") || subtype.includes("solar"))) {
      return device;
    }

    if (
      role === "cons" &&
      (type.includes("-C") || subtype.includes("cons") || meterLocation.includes("load") || meterLocation.includes("house"))
    ) {
      return device;
    }
  }

  return devices.find((device) => (device.TYPE ?? "").toUpperCase().includes("METER")) ?? {};
}
