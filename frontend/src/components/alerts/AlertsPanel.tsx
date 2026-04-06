import { useEffect } from "react";

import { AlertCenter } from "@/components/alerts/AlertCenter";

interface AlertsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AlertsPanel({ isOpen, onClose }: AlertsPanelProps) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  return (
    <>
      <button
        type="button"
        className={`alerts-panel-overlay ${isOpen ? "open" : ""}`.trim()}
        onClick={onClose}
        aria-label="Close alerts panel"
      />

      <aside
        className={`alerts-panel ${isOpen ? "open" : ""}`.trim()}
        aria-hidden={!isOpen}
        aria-label="Alerts panel"
        aria-modal="true"
        role="dialog"
      >
        <div className="alerts-panel-header">
          <h2 className="alerts-panel-title">Alerts</h2>
          <button type="button" className="alerts-panel-close" onClick={onClose} aria-label="Close alerts panel">
            ×
          </button>
        </div>

        <div className="alerts-panel-body">
          <AlertCenter />
        </div>
      </aside>
    </>
  );
}
