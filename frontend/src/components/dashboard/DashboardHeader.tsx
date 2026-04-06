interface DashboardHeaderProps {
  alertCount: number;
  alertTone: "critical" | "warning" | "neutral";
  onAlertClick: () => void;
  onRefresh: () => void;
  theme?: "light" | "dark";
  onThemeToggle?: () => void;
}

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8 1.5v1.5M8 13v1.5M14.5 8h-1.5M2.5 8H1M12.73 3.27l-1.06 1.06M4.33 11.67l-1.06 1.06M12.73 12.73l-1.06-1.06M4.33 4.33l-1.06-1.06" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
      <path d="M10.5 2.9a6.5 6.5 0 1 1-2.45 12.1A5.5 5.5 0 1 0 10.5 2.9Z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function DashboardHeader({ alertCount, alertTone, onAlertClick, onRefresh, theme = "light", onThemeToggle }: DashboardHeaderProps) {
  const alertLabel = alertCount === 0 ? "No alerts" : `${alertCount} ${alertCount === 1 ? "alert" : "alerts"}`;
  const alertClassName = [
    "alert-pill",
    alertTone === "critical" ? "has-alerts" : "",
    alertTone === "warning" ? "has-warnings" : ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <header className="header-shell shell">
      <div className="header">
        <div className="header-brand">
          <p className="header-title">Home Energy</p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="mini-btn theme-btn"
            onClick={onThemeToggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            data-testid="theme-toggle"
          >
            {theme === "dark" ? <MoonIcon /> : <SunIcon />}
          </button>

          <button type="button" className={alertClassName} onClick={onAlertClick} data-testid="alert-pill-button">
            <span className="alert-pill-dot" aria-hidden="true" />
            <span>{alertLabel}</span>
          </button>

          <button type="button" className="mini-btn refresh-btn" onClick={onRefresh} aria-label="Refresh">
            <svg className="refresh-btn-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
              <path d="M13 4.5V1.5M13 1.5H10M13 1.5 9.75 4.75" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M13 8A5 5 0 1 1 8 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <span>Refresh</span>
          </button>
        </div>
      </div>
    </header>
  );
}
