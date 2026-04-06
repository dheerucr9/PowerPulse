import { DraftHistoryInterval, GatewayDevice } from "@/api/models";

type RelativePreset = "last15m" | "last30m" | "last1h" | "last6h" | "last12h";
type AbsolutePreset = "today" | "yesterday" | "24h" | "7d" | "30d";
type Preset = RelativePreset | AbsolutePreset | "custom";

interface HistoryFiltersProps {
  activePreset: Preset;
  setActivePreset: (preset: Preset) => void;
  draftRange: {
    from: string | null;
    to: string | null;
  };
  setDraftRange: (range: { from: string | null; to: string | null }) => void;
  draftPanel: string;
  setDraftPanel: (panel: string) => void;
  draftInterval: DraftHistoryInterval;
  setDraftInterval: (interval: DraftHistoryInterval) => void;
  onApplyPreset: (preset: AbsolutePreset) => void;
  onApplyRelative: (preset: RelativePreset) => void;
  onReset: () => void;
  onApply: () => void;
  hasPendingChanges: boolean;
  panels: GatewayDevice[];
}

const relativePresets: { value: RelativePreset; label: string }[] = [
  { value: "last15m", label: "Last 15m" },
  { value: "last30m", label: "Last 30m" },
  { value: "last1h", label: "Last 1h" },
  { value: "last6h", label: "Last 6h" },
  { value: "last12h", label: "Last 12h" }
];

const absolutePresets: { value: AbsolutePreset | "custom"; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "custom", label: "Custom" }
];

export function HistoryFilters({
  activePreset,
  setActivePreset,
  draftRange,
  setDraftRange,
  draftPanel,
  setDraftPanel,
  draftInterval,
  setDraftInterval,
  onApplyPreset,
  onApplyRelative,
  onReset,
  onApply,
  hasPendingChanges,
  panels
}: HistoryFiltersProps) {
  const isCustom = activePreset === "custom";

  function handleRelative(preset: RelativePreset) {
    onApplyRelative(preset);
  }

  function handleAbsolute(preset: AbsolutePreset | "custom") {
    if (preset === "custom") {
      setActivePreset("custom");
    } else {
      onApplyPreset(preset);
    }
  }

  function isRelative(p: Preset): p is RelativePreset {
    return (["last15m", "last30m", "last1h", "last6h", "last12h"] as Preset[]).includes(p);
  }

  return (
    <div className="grid history-controls">
      <div className="card filter-rail filter-rail-surface history-filter-card">
        <div className="time-range-section">
          <span className="k-title time-section-label">Relative</span>
          <div className="time-range-grid">
            {relativePresets.map((p) => (
              <button
                key={p.value}
                type="button"
                className={`time-chip ${activePreset === p.value ? "active" : ""}`}
                onClick={() => handleRelative(p.value)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="time-range-section">
          <span className="k-title time-section-label">Absolute</span>
          <div className="time-range-grid">
            {absolutePresets.map((p) => (
              <button
                key={p.value}
                type="button"
                className={`time-chip ${activePreset === p.value ? "active" : ""}`}
                onClick={() => handleAbsolute(p.value)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className={`time-range-custom ${isCustom ? "open" : ""}`}>
          <div className="time-range-custom-inputs">
            <div className="field">
              <label htmlFor="history-start">From</label>
              <input
                id="history-start"
                className="input compact datetime-input"
                type="text"
                inputMode="numeric"
                placeholder="YYYY-MM-DD HH:MM"
                value={draftRange.from ?? ""}
                onChange={(e) => {
                  setActivePreset("custom");
                  setDraftRange({ ...draftRange, from: e.target.value });
                }}
              />
            </div>
            <div className="field">
              <label htmlFor="history-end">To</label>
              <input
                id="history-end"
                className="input compact datetime-input"
                type="text"
                inputMode="numeric"
                placeholder="YYYY-MM-DD HH:MM"
                value={draftRange.to ?? ""}
                onChange={(e) => {
                  setActivePreset("custom");
                  setDraftRange({ ...draftRange, to: e.target.value });
                }}
              />
            </div>
          </div>
        </div>

        <div className="filter-footer">
          <div className="field history-field">
            <label>Interval</label>
            <div className="interval-row">
              {(["auto", "raw", "5m", "1h"] as DraftHistoryInterval[]).map((interval) => (
                <button
                  key={interval}
                  type="button"
                  className={`interval-chip ${draftInterval === interval ? "active" : ""}`}
                  onClick={() => setDraftInterval(interval)}
                >
                  {interval}
                </button>
              ))}
            </div>
          </div>

          <div className="field history-field">
            <label htmlFor="history-panel">Panel</label>
            <select
              id="history-panel"
              className="input compact"
              value={draftPanel}
              onChange={(e) => setDraftPanel(e.target.value)}
            >
              <option value="">All panels</option>
              {panels.map((panel) => {
                const value = String(panel.SERIAL ?? panel.panel_id ?? panel.TYPE ?? "Unknown Panel");
                return (
                  <option key={value} value={value}>
                    {value}
                  </option>
                );
              })}
            </select>
          </div>

          <div className="filter-actions">
            <button type="button" className="mini-btn filter-action-btn" onClick={onReset} disabled={!hasPendingChanges}>
              Reset
            </button>
            <button
              type="button"
              className="mini-btn active filter-action-btn"
              data-testid="history-apply-button"
              onClick={onApply}
              disabled={!hasPendingChanges}
            >
              Apply
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
