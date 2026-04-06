import { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: string;
  trend: string;
  tone: "production" | "consumption" | "net" | "panel" | "charger" | "neutral";
  trendDirection?: "up" | "down" | "neutral";
  icon?: ReactNode;
  isLoading?: boolean;
}

function getToneIcon(tone: StatCardProps["tone"]) {
  switch (tone) {
    case "production":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M12 3.5v2.25M12 18.25v2.25M20.5 12h-2.25M5.75 12H3.5M18 6l-1.5 1.5M7.5 16.5 6 18M18 18l-1.5-1.5M7.5 7.5 6 6" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" />
        </svg>
      );
    case "consumption":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M7 16a5 5 0 1 1 10 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
          <path d="m12 12 3.5-1.75" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
          <circle cx="12" cy="12" r="1.4" fill="currentColor" />
        </svg>
      );
    case "net":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M6.25 16.75 17.75 7.25" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
          <path d="M9 7.25h8.75V16" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        </svg>
      );
    case "charger":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M8 6.5h6a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8.5a2 2 0 0 1 2-2Z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
          <path d="M10.5 4.5v2M13.5 4.5v2" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
          <path d="m11 10.25 2.25.25-1.25 2.5 2 .25-2.25 2.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      );
  }
}

export function StatCard({ title, value, trend, tone, trendDirection = "neutral", icon, isLoading = false }: StatCardProps) {
  return (
    <article className={`metric-card metric-card-${tone} ${isLoading ? "metric-card-loading" : ""}`.trim()} data-loading={isLoading ? "true" : "false"}>
      <div className="metric-card-shell">
        <div className="metric-head metric-card-content" aria-hidden={isLoading}>
          <div>
            <p className="metric-label">{title}</p>
            <p className="metric-value">{value}</p>
            <p className={`metric-trend ${trendDirection}`.trim()}>{trend}</p>
          </div>
          <span className="metric-icon" aria-hidden="true">
            {icon ?? getToneIcon(tone)}
          </span>
        </div>

        <div className="metric-card-skeleton skeleton-card" aria-hidden={!isLoading}>
          <div className="metric-head">
            <div className="metric-card-skeleton-copy">
              <span className="skeleton skeleton-shimmer skeleton-text skeleton-text-80" />
              <span className="skeleton skeleton-shimmer skeleton-value" />
              <span className="skeleton skeleton-shimmer skeleton-text skeleton-text-60" />
            </div>
            <span className="skeleton skeleton-shimmer metric-icon-skeleton" />
          </div>
        </div>
      </div>
    </article>
  );
}
