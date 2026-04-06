export type DashboardTab = "live" | "history";
export type HistoryInterval = "raw" | "5m" | "1h";
export type DraftHistoryInterval = HistoryInterval | "auto";
export type HistoryChartType = "line" | "bar";
export type BarHistoryInterval = "day" | "week" | "month";

export interface Coordinates {
  lat: number;
  lon: number;
}

export interface DashboardConfig {
  lat: number | null;
  lon: number | null;
  tz?: string | null;
}

export interface GatewayDevice {
  TYPE?: string;
  subtype?: string;
  METER_LOCATION?: string;
  DEVICE_TYPE?: string;
  STATEDESCR?: string;
  SERIAL?: string;
  MODEL?: string;
  SWVER?: string;
  CURTIME?: string;
  p_3phsum_kw?: string | number;
  net_ltea_3phsum_kwh?: string | number;
  v12_v?: string | number;
  v1n_v?: string | number;
  v2n_v?: string | number;
  tot_pf_rto?: string | number;
  panel_id?: string;
  [key: string]: unknown;
}

export interface DevicesResponse {
  devices?: GatewayDevice[];
}

export interface LiveSnapshot {
  production: number;
  consumption: number;
  net: number;
  lifetime: number;
  charger?: ChargerSnapshot;
  vsys?: string | number;
  v1?: string | number;
  v2?: string | number;
  pfProd?: string | number;
  pfCons?: string | number;
  updated?: string;
}

export interface ChargerSnapshot {
  ts: number;
  vehicle_connected: boolean;
  contactor_closed: boolean;
  charging: boolean;
  power_kw: number;
  session_energy_wh: number;
  lifetime_energy_wh: number;
  pcba_temp_c: number;
  handle_temp_c: number;
}

export interface LiveDashboardData {
  live: LiveSnapshot;
  panels: GatewayDevice[];
  meta: {
    gw?: GatewayDevice;
  };
}

export interface HouseSample {
  ts: number;
  production_kw?: number | null;
  consumption_kw?: number | null;
  net_kw?: number | null;
  v_sys?: number | null;
  v_l1?: number | null;
  v_l2?: number | null;
}

export interface PanelSample {
  ts: number;
  panel_id: string;
  p_kw?: number | null;
  v_ac?: number | null;
  v_dc?: number | null;
  i_dc?: number | null;
  temp_c?: number | null;
  state?: string | null;
  serial?: string | null;
}

export interface ChargerHistorySample {
  ts: number;
  power_kw?: number | null;
}

export interface PageInfo {
  has_more: boolean;
  next_cursor?: string | null;
  returned: number;
  limit: number;
}

export interface PaginatedSamplesResponse<TSample> {
  samples: TSample[];
  page_info: PageInfo;
}

export interface ChartPoint {
  ts: number;
  val: number;
}

export interface HistoryChartData {
  production: ChartPoint[];
  consumption: ChartPoint[];
  net: ChartPoint[];
  panel: ChartPoint[];
  charger: ChartPoint[];
}

export interface HistoryDashboardData {
  data: HistoryChartData;
  panelLabel: string;
}

export interface HistoryFilters {
  from: string | null;
  to: string | null;
  panel: string;
  interval: HistoryInterval;
}

export interface DraftHistoryFilters {
  from: string | null;
  to: string | null;
  panel: string;
  interval: DraftHistoryInterval;
}

export type AlertSeverity = "info" | "warning" | "critical";
export type AlertStatus = "open" | "acknowledged" | "resolved" | "suppressed";
export type AlertKind = "production" | "consumption";
export type AcknowledgementStatus = "acknowledged" | "resolved" | "suppressed";

export interface AlertExplanationPayload {
  kind: string;
  source: string;
  metric: string;
  direction: string;
  title: string;
  message: string;
  explanation: string;
  evidence: Record<string, unknown>;
  sample_ts: number;
}

export interface AlertRecord {
  alert_id: number;
  anomaly_id: number | null;
  site_id: string;
  dedupe_key: string;
  kind: AlertKind;
  panel_id: string | null;
  category: string;
  severity: AlertSeverity;
  status: AlertStatus;
  state: string | null;
  title: string;
  message: string;
  first_seen_ts: number;
  last_seen_ts: number;
  detected_at_ts: number;
  last_observed_ts: number | null;
  baseline_kw: number | null;
  observed_kw: number | null;
  deviation_kw: number | null;
  deviation_pct: number | null;
  confidence_score: number | null;
  affected_panel_count: number | null;
  evidence_summary: string | null;
  explanation_payload: AlertExplanationPayload | null;
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  acknowledged_note: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_note: string | null;
}

export interface AlertListMeta {
  filtered_total: number;
  returned: number;
  open_badge_count: number;
  open_by_kind: Record<string, number>;
  open_by_severity: Record<string, number>;
}

export interface AlertsResponse {
  items: AlertRecord[];
  meta: AlertListMeta;
}

export interface AcknowledgeAlertRequest {
  new_status?: AcknowledgementStatus;
  acknowledged_by?: string;
  note?: string;
}

export interface IntelligenceAlertSummary {
  alert_id: number;
  kind: AlertKind;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  message: string;
  last_seen_ts: number;
  evidence_summary: string | null;
}

export interface IntelligenceAnomalySummary {
  anomaly_id: number;
  metric: string;
  direction: string;
  severity: AlertSeverity;
  sample_ts: number;
  explanation: string | null;
  evidence: Record<string, unknown>;
}

export interface IntelligenceDomainSummaryResponse {
  latest_alert: IntelligenceAlertSummary | null;
  latest_anomaly: IntelligenceAnomalySummary | null;
}

export interface IntelligenceOpenCountsResponse {
  total: number;
  by_kind: Record<AlertKind, number>;
  by_severity: Record<AlertSeverity, number>;
}

export interface IntelligenceSummaryResponse {
  generated_at_ts: number;
  open_counts: IntelligenceOpenCountsResponse;
  production: IntelligenceDomainSummaryResponse;
  consumption: IntelligenceDomainSummaryResponse;
}

export interface ReadinessChecks {
  database: boolean;
  migrations: boolean;
  ingest_fresh: boolean;
}

export interface ReadinessResponse {
  status: "ok" | "not_ready";
  checks: ReadinessChecks;
  last_successful_ingest_ts: number | null;
  max_ingest_age_seconds: number;
}
