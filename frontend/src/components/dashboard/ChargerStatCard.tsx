import { ChargerSnapshot } from "@/api/models";
import { StatCard } from "@/components/dashboard/StatCard";

interface ChargerStatCardProps {
  chargedTodayKwh: number;
  chargerData: ChargerSnapshot | undefined;
  isLoading: boolean;
}

function formatKwh(value: number) {
  if (!Number.isFinite(value)) {
    return "--";
  }

  return `${value.toFixed(1)} kWh`;
}

function formatKw(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0.0 kW";
  }

  return `${value.toFixed(1)} kW`;
}

export function ChargerStatCard({ chargedTodayKwh, chargerData, isLoading }: ChargerStatCardProps) {
  const isCharging = Boolean(chargerData?.charging && (chargerData?.power_kw ?? 0) > 0.05);

  return (
    <StatCard
      title="Charged today"
      value={formatKwh(chargedTodayKwh)}
      tone="charger"
      trend={isCharging ? `● Charging now · ${formatKw(chargerData?.power_kw ?? 0)}` : "Idle"}
      trendDirection="neutral"
      isLoading={isLoading}
    />
  );
}
