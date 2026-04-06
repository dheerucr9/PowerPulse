interface DashboardStatePanelProps {
  tone: "loading" | "empty" | "error" | "stale";
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  compact?: boolean;
  testId?: string;
}

const eyebrowCopy: Record<DashboardStatePanelProps["tone"], string> = {
  loading: "Loading",
  empty: "Empty",
  error: "Attention needed",
  stale: "Data delay"
};

function StateIcon({ tone }: Pick<DashboardStatePanelProps, "tone">) {
  if (tone === "loading") {
    return <span className="skeleton-dot-pulse" aria-hidden="true" />;
  }

  if (tone === "error") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M12 7.5v5.75M12 17.25h.01" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
        <path d="M10.29 3.86 2.9 17.02a1.5 1.5 0 0 0 1.31 2.23h15.58a1.5 1.5 0 0 0 1.31-2.23L13.71 3.86a1.96 1.96 0 0 0-3.42 0Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
      </svg>
    );
  }

  if (tone === "stale") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M12 7.5v5l3 2" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="m7.5 12 3 3 6-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function DashboardStatePanel({
  tone,
  title,
  message,
  actionLabel,
  onAction,
  compact = false,
  testId
}: DashboardStatePanelProps) {
  return (
    <div data-testid={testId} className={`dashboard-state dashboard-state-${tone} ${compact ? "compact" : ""}`.trim()} role={tone === "error" ? "alert" : "status"}>
      <div className={`dashboard-state-icon dashboard-state-icon-${tone}`.trim()} aria-hidden="true">
        <StateIcon tone={tone} />
      </div>

      <div className="dashboard-state-copy">
        <p className="k-title dashboard-state-eyebrow">{eyebrowCopy[tone]}</p>
        <h2 className="dashboard-state-title">{title}</h2>
        <p className="dashboard-state-message">{message}</p>
      </div>

      {actionLabel && onAction ? (
        <button type="button" className="mini-btn dashboard-state-action" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
