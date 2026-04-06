import { CSSProperties } from "react";
import { getTimes as getSunTimes } from "suncalc";

import { ChargerSnapshot, Coordinates, GatewayDevice, LiveSnapshot } from "@/api/models";
import { formatKw } from "@/lib/format";

interface LiveFlowProps {
  live?: LiveSnapshot | null;
  charger?: ChargerSnapshot | null;
  panels: GatewayDevice[];
  latLon: Coordinates;
  isRefreshing?: boolean;
}

interface LiveFlowState {
  production: number;
  consumption: number;
  net: number;
  exporting: boolean;
  importing: boolean;
  solarFlowActive: boolean;
  gridFlowActive: boolean;
  gridDirection: "export" | "import" | "idle";
  isNight: boolean;
  statusText: string;
  activePanels: number;
  faultPanels: number;
}

type FlowDotStyle = CSSProperties & {
  animationDelay: string;
};

export function deriveLiveFlowState(live: LiveSnapshot | null | undefined, panels: GatewayDevice[], latLon: Coordinates): LiveFlowState {
  const productionRaw = Number.isFinite(live?.production) ? Number(live?.production) : 0;
  const consumption = Number.isFinite(live?.consumption) ? Math.max(Number(live?.consumption), 0) : 0;
  const production = productionRaw < 0.05 ? 0 : Math.max(productionRaw, 0);
  const netRaw = Number.isFinite(live?.net) ? Number(live?.net) : production - consumption;
  const net = Math.abs(netRaw) < 0.05 ? 0 : netRaw;
  const exporting = net >= 0.05;
  const importing = net <= -0.05;
  const solarFlowActive = production >= 0.05;
  const gridFlowActive = Math.abs(net) >= 0.05;
  const gridDirection = exporting ? "export" : importing ? "import" : "idle";

  const activePanels = panels.filter((panel) => {
    const power = Number.parseFloat(String(panel.p_3phsum_kw ?? 0));
    const state = (panel.STATEDESCR ?? "").toLowerCase();
    return Number.isFinite(power) && power >= 0.05 && !state.includes("fault");
  }).length;

  const faultPanels = panels.filter((panel) => (panel.STATEDESCR ?? "").toLowerCase().includes("fault")).length;
  const now = new Date();

  let dawn = new Date(now);
  dawn.setHours(6, 0, 0, 0);

  let dusk = new Date(now);
  dusk.setHours(18, 30, 0, 0);

  try {
    const sunTimes = getSunTimes(now, latLon.lat, latLon.lon);
    dawn = sunTimes.dawn;
    dusk = sunTimes.dusk;
  } catch {}

  const isNight = now < dawn || now > dusk;
  const statusText = isNight && production < 0.05
    ? "Night mode — panels are idle while the home settles into grid power."
    : exporting
      ? "Solar is covering your home and quietly exporting the excess."
      : importing
        ? "Home demand is pulling support from the grid right now."
        : "Production and demand are moving in balance.";

  return {
    production,
    consumption,
    net,
    exporting,
    importing,
    solarFlowActive,
    gridFlowActive,
    gridDirection,
    isNight,
    statusText,
    activePanels,
    faultPanels
  };
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" className="flow-icon" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="3.8" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 2.75v2.5M12 18.75v2.5M21.25 12h-2.5M5.25 12h-2.5M18.54 5.46l-1.77 1.77M7.23 16.77l-1.77 1.77M18.54 18.54l-1.77-1.77M7.23 7.23 5.46 5.46" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" className="flow-icon" aria-hidden="true" focusable="false">
      <path d="M15.75 4.35a7.85 7.85 0 1 0 4.1 14.45A8.65 8.65 0 1 1 15.75 4.35Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
    </svg>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="flow-icon" aria-hidden="true" focusable="false">
      <path d="M4.75 11.5 12 5.5l7.25 6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
      <path d="M7 10.5v8h10v-8" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
      <path d="M10.5 18.5v-4h3v4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" className="flow-icon" aria-hidden="true" focusable="false">
      <path d="M12 4.5 8.75 10.25h6.5L12 4.5Zm0 0v14.75m-3.5-9.25h7m-8.2 4.5h9.4m-10.3 4.5h11.2" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
    </svg>
  );
}

function ChargerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="flow-icon" aria-hidden="true" focusable="false">
      <path d="M9 7.25v4.25a3 3 0 0 0 3 3h.25" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
      <path d="M14 7.25v4.5m3-4.5v4.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
      <path d="M9 7.25h8v6.25a4.75 4.75 0 0 1-4.75 4.75H11.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
      <path d="m11.25 10.4 1.7-2.15-.2 1.85h1.95l-1.95 2.4.25-2.1h-1.75Z" fill="currentColor" stroke="none" />
      <path d="M11.5 18.25v1.25" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
    </svg>
  );
}

function FlowConnector({
  active,
  dotClassName,
  dotKeyPrefix,
  className = "flow-connector"
}: {
  active: boolean;
  dotClassName: string;
  dotKeyPrefix: string;
  className?: string;
}) {
  return (
    <div className={`${className} ${active ? "active" : "idle"}`.trim()} aria-hidden="true">
      <div className="flow-line" />
      {active ? (
        <div className="flow-dots">
          {[0, 0.4, 0.8].map((delay) => (
            <span key={`${dotKeyPrefix}-${delay}`} className={`flow-dot ${dotClassName}`.trim()} style={{ animationDelay: `${delay}s` } as FlowDotStyle} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function LiveFlow({ live, charger, panels, latLon, isRefreshing = false }: LiveFlowProps) {
  const state = deriveLiveFlowState(live, panels, latLon);
  const gridLabel = state.exporting ? "Exporting" : state.importing ? "Importing" : "Balanced";
  const chargerActive = Boolean(charger?.vehicle_connected && charger?.charging);
  const chargerPower = chargerActive ? Math.max(Number(charger?.power_kw ?? 0), 0) : 0;

  return (
    <div className={`live-flow-shell ${isRefreshing ? "refreshing" : ""}`}>
      <div className="flow-container" data-grid-direction={state.gridDirection}>
        <div className="flow-node flow-node-source">
          <div className="flow-icon-wrapper">{state.isNight ? <MoonIcon /> : <SunIcon />}</div>
          <div className="flow-value">{formatKw(state.production)}</div>
          <div className="flow-label">Solar</div>
        </div>

        <FlowConnector active={state.solarFlowActive} dotClassName="from-source" dotKeyPrefix="source" className="flow-connector flow-connector-solar" />

        <div className="flow-node flow-node-home">
          <div className="flow-icon-wrapper">
            <HomeIcon />
          </div>
          <div className="flow-value">{formatKw(state.consumption)}</div>
          <div className="flow-label">Home</div>
        </div>

        <FlowConnector active={state.gridFlowActive} dotClassName={state.importing ? "from-grid" : "from-home"} dotKeyPrefix="grid" className="flow-connector flow-connector-grid" />

        <div className="flow-node flow-node-grid">
          <div className="flow-icon-wrapper">
            <GridIcon />
          </div>
          <div className="flow-value">{formatKw(Math.abs(state.net))}</div>
          <div className="flow-label">{gridLabel}</div>
        </div>

        {chargerActive ? (
          <>
            <div className="flow-node flow-node-charger" title={`Tesla Wall Connector charging at ${formatKw(chargerPower)}`}>
              <div className="flow-icon-wrapper">
                <ChargerIcon />
              </div>
              <div className="flow-value">{formatKw(chargerPower)}</div>
              <div className="flow-label">Tesla</div>
            </div>

            <FlowConnector active={chargerPower >= 0.05} dotClassName="from-charger" dotKeyPrefix="charger" className="flow-connector flow-connector-charger" />
          </>
        ) : null}
      </div>

      <p className="panel-summary">
        Panels active {state.activePanels}/{panels.length || 0}
        {state.faultPanels ? ` • ${state.faultPanels} fault${state.faultPanels > 1 ? "s" : ""}` : ""}
      </p>
    </div>
  );
}
