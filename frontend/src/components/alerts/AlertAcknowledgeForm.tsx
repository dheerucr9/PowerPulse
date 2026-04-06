import { useState } from "react";

import type { AcknowledgementStatus } from "@/api/models";

interface AlertAcknowledgeFormProps {
  alertId: number;
  currentStatus: string;
  onSubmit: (body: { new_status: AcknowledgementStatus; acknowledged_by: string; note: string }) => void;
  isPending: boolean;
  hasError: boolean;
}

export function AlertAcknowledgeForm({ currentStatus: _currentStatus, onSubmit, isPending, hasError }: AlertAcknowledgeFormProps) {
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<AcknowledgementStatus>("acknowledged");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ new_status: status, acknowledged_by: "local-operator", note });
  };

  return (
    <form className="acknowledge-form" onSubmit={handleSubmit}>
      {hasError ? (
        <div className="acknowledge-error" data-testid="acknowledge-error" role="alert">
          Acknowledgement failed. The alert remains in its previous state. Please try again.
        </div>
      ) : null}

      <div className="acknowledge-form-row">
        <label className="acknowledge-status-label" htmlFor="acknowledge-status">
          Action
        </label>
        <select
          id="acknowledge-status"
          className="acknowledge-status-select"
          value={status}
          onChange={(e) => setStatus(e.target.value as AcknowledgementStatus)}
          disabled={isPending}
        >
          <option value="acknowledged">Acknowledge</option>
          <option value="resolved">Resolve</option>
          <option value="suppressed">Suppress</option>
        </select>
      </div>

      <div className="acknowledge-form-row">
        <label className="acknowledge-note-label" htmlFor="acknowledge-note">
          Note <span className="muted">(optional)</span>
        </label>
        <textarea
          id="acknowledge-note"
          className="acknowledge-note-textarea"
          placeholder="Reviewed on dashboard…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={isPending}
          rows={3}
          data-testid="acknowledge-note-input"
        />
      </div>

      <button
        type="submit"
        className="btn btn-compact acknowledge-submit-btn"
        disabled={isPending}
        data-testid="acknowledge-submit-button"
      >
        {isPending ? "Submitting…" : "Submit update"}
      </button>
    </form>
  );
}
