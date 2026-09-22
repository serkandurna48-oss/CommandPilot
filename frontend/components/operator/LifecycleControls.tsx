"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import type { WorkOrderStatus } from "@/types";

interface Props {
  status: WorkOrderStatus;
  isLive: boolean;
  onStatusChange: (status: WorkOrderStatus) => Promise<void> | void;
}

// Only the transitions a human is expected to trigger from this UI.
// running → {needs_approval, blocked, failed, review_ready} is exclusively
// the harness/import script's job (see scripts/import_work_order_result.py's
// atomic gate, OP-Import-Integrity-001) — no manual button for those. The
// backend enforces this as the authoritative state machine regardless
// (CP-OP01, transition_work_order()), so these buttons only ever offer
// edges the backend actually allows.
//
// needs_approval/blocked/failed/rework_requested → queued are the CP-OP01
// human resume paths: a human resolved whatever paused/failed the work
// order and sends it back into the queue. cancelled is offered from every
// non-terminal status ("any non-terminal state is cancellable").
const TRANSITIONS: Partial<Record<WorkOrderStatus, { action: WorkOrderStatus; labelKey: string; variant: "primary" | "secondary" }[]>> = {
  draft: [
    { action: "approved", labelKey: "operator.lifecycle.approve", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  approved: [
    { action: "queued", labelKey: "operator.lifecycle.mark_queued", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  queued: [
    { action: "running", labelKey: "operator.lifecycle.mark_running", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  running: [
    // "Stop", not "Cancel" — this is the same running -> cancelled PATCH as
    // every other cancel button, but for a running order it's no longer
    // inert: a local runner harness (scripts/run_work_order.py) polls
    // status via its ProgressReporter.should_stop() roughly every 15s and
    // kills its own subprocess the moment it sees 'cancelled', marking the
    // in-flight step failed with "Vom Nutzer unterbrochen". See
    // scripts/runner_adapters/base.py's ProgressReporter and
    // claude_code.py's execute() poll loop.
    { action: "cancelled", labelKey: "operator.lifecycle.stop", variant: "secondary" },
  ],
  needs_approval: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  blocked: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  failed: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  review_ready: [
    { action: "accepted", labelKey: "operator.lifecycle.accept", variant: "primary" },
    { action: "rework_requested", labelKey: "operator.lifecycle.request_rework", variant: "secondary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
  rework_requested: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", variant: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
  ],
};

export function LifecycleControls({ status, isLive, onStatusChange }: Props) {
  const t = useT();
  const [pending, setPending] = useState<WorkOrderStatus | null>(null);
  // Inline confirm — no new modal/dialog component introduced. Cancel/Stop is
  // the one irreversible-feeling action here (every other transition can
  // itself be undone or re-driven; cancelling a work order withdraws it for
  // good, and stopping a running one kills real in-progress work — see the
  // "running" case comment above), so it gets a lightweight "really do this?
  // yes/no" step instead of firing immediately on click.
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const options = TRANSITIONS[status];

  if (!options || options.length === 0) return null;

  async function handleClick(action: WorkOrderStatus) {
    if (action === "cancelled" && !confirmingCancel) {
      setConfirmingCancel(true);
      return;
    }
    setConfirmingCancel(false);
    setPending(action);
    try {
      await onStatusChange(action);
    } finally {
      setPending(null);
    }
  }

  const isStop = status === "running"; // real interrupt, not just a withdrawal — see stop_confirm_message

  return (
    <div className="space-y-2">
      {!isLive && <p className="text-[var(--text-tertiary)] text-xs">{t("operator.lifecycle.demo_note")}</p>}
      {confirmingCancel && (
        <div className="rounded-lg bg-status-danger/10 border border-status-danger/30 px-3 py-2 space-y-2">
          <p className="text-status-danger text-xs">
            {t(isStop ? "operator.lifecycle.stop_confirm_message" : "operator.lifecycle.cancel_confirm_message")}
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="danger"
              disabled={pending !== null}
              loading={pending === "cancelled"}
              onClick={() => handleClick("cancelled")}
            >
              {t(isStop ? "operator.lifecycle.stop_confirm_yes" : "operator.lifecycle.cancel_confirm_yes")}
            </Button>
            <Button size="sm" variant="ghost" disabled={pending !== null} onClick={() => setConfirmingCancel(false)}>
              {t("operator.lifecycle.cancel_confirm_no")}
            </Button>
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map(({ action, labelKey, variant }) => (
          <Button
            key={action}
            size="sm"
            variant={action === "cancelled" ? "danger" : variant}
            disabled={!isLive || pending !== null || (action === "cancelled" && confirmingCancel)}
            loading={pending === action && !confirmingCancel}
            onClick={() => handleClick(action)}
          >
            {t(labelKey)}
          </Button>
        ))}
      </div>
    </div>
  );
}
