"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import type { WorkOrderStatus } from "@/types";

interface Props {
  status: WorkOrderStatus;
  isLive: boolean;
  onStatusChange: (status: WorkOrderStatus) => Promise<void> | void;
  // Not a status transition — sets work_orders.daemon_run_requested_at
  // (supabase/migrations/016_...sql), the trigger signal
  // scripts/run_work_order_daemon.py polls for. Status stays "queued" until
  // the daemon's own run_work_order.py invocation flips it to "running",
  // exactly like the existing manual "Als laufend markieren" path. Optional
  // so this component still renders standalone without the feature wired up.
  onRequestAutonomousStart?: () => Promise<void> | void;
}

// Maps this component's semantic tones onto the shared Button's variants —
// Focus Deck tokens (23.09.2026). Used to render its own terminal-styled
// LifecycleButton (bypassing the shared Button to avoid a Tailwind
// specificity gamble against this surface's now-removed emerald palette);
// that reason no longer applies now that this surface uses the same
// palette as the shared Button itself.
const TONE_TO_VARIANT = {
  primary: "primary",
  danger: "danger",
  neutral: "secondary",
  ghost: "ghost",
} as const;

function LifecycleButton({
  tone = "neutral",
  disabled,
  loading,
  onClick,
  children,
}: {
  tone?: "primary" | "danger" | "neutral" | "ghost";
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button size="sm" variant={TONE_TO_VARIANT[tone]} disabled={disabled} loading={loading} onClick={onClick} className="rounded-xl">
      {children}
    </Button>
  );
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
const TRANSITIONS: Partial<Record<WorkOrderStatus, { action: WorkOrderStatus; labelKey: string; tone: "primary" | "neutral" }[]>> = {
  draft: [
    { action: "approved", labelKey: "operator.lifecycle.approve", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
  approved: [
    { action: "queued", labelKey: "operator.lifecycle.mark_queued", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
  queued: [
    { action: "running", labelKey: "operator.lifecycle.mark_running", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
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
    { action: "cancelled", labelKey: "operator.lifecycle.stop", tone: "neutral" },
  ],
  needs_approval: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
  blocked: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
  failed: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
  review_ready: [
    { action: "accepted", labelKey: "operator.lifecycle.accept", tone: "primary" },
    { action: "rework_requested", labelKey: "operator.lifecycle.request_rework", tone: "neutral" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
  rework_requested: [
    { action: "queued", labelKey: "operator.lifecycle.requeue", tone: "primary" },
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", tone: "neutral" },
  ],
};

export function LifecycleControls({ status, isLive, onStatusChange, onRequestAutonomousStart }: Props) {
  const t = useT();
  const [pending, setPending] = useState<WorkOrderStatus | null>(null);
  // Found 23.09.2026: both handlers below previously had try/finally with no
  // catch — an API failure (e.g. PATCH daemon_run_requested_at against a DB
  // missing migration 016, an expired session, a 403) reset the button back
  // to idle with zero visible feedback; the real error only ever reached the
  // browser console. Every lifecycle action was affected, not just
  // "Autonom starten". This is the one state both handlers now write to.
  const [error, setError] = useState<string | null>(null);
  // Inline confirm — no new modal/dialog component introduced. Cancel/Stop is
  // the one irreversible-feeling action here (every other transition can
  // itself be undone or re-driven; cancelling a work order withdraws it for
  // good, and stopping a running one kills real in-progress work — see the
  // "running" case comment above), so it gets a lightweight "really do this?
  // yes/no" step instead of firing immediately on click.
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  // Separate confirm state from confirmingCancel — "Autonom starten" isn't a
  // WorkOrderStatus transition (see onRequestAutonomousStart's docstring),
  // so it can't share `pending`/`handleClick` below, which are typed around
  // TRANSITIONS' status actions specifically.
  const [confirmingAutonomousStart, setConfirmingAutonomousStart] = useState(false);
  const [autonomousStartPending, setAutonomousStartPending] = useState(false);
  const options = TRANSITIONS[status];
  const canRequestAutonomousStart = status === "queued" && !!onRequestAutonomousStart;

  if ((!options || options.length === 0) && !canRequestAutonomousStart) return null;

  async function handleClick(action: WorkOrderStatus) {
    if (action === "cancelled" && !confirmingCancel) {
      setConfirmingCancel(true);
      return;
    }
    setConfirmingCancel(false);
    setPending(action);
    setError(null);
    try {
      await onStatusChange(action);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setPending(null);
    }
  }

  async function handleAutonomousStartClick() {
    if (!confirmingAutonomousStart) {
      setConfirmingAutonomousStart(true);
      return;
    }
    setConfirmingAutonomousStart(false);
    setAutonomousStartPending(true);
    setError(null);
    try {
      await onRequestAutonomousStart?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setAutonomousStartPending(false);
    }
  }

  const isStop = status === "running"; // real interrupt, not just a withdrawal — see stop_confirm_message

  return (
    <div className="space-y-2">
      {!isLive && <p className="text-[var(--text-tertiary)] text-xs font-mono">{t("operator.lifecycle.demo_note")}</p>}
      {error && (
        <div className="rounded-lg bg-status-danger/10 border border-status-danger/30 px-3 py-2 flex items-start justify-between gap-2">
          <p className="text-status-danger text-xs">{error}</p>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label={t("common.dismiss")}
            className="text-status-danger/70 hover:text-status-danger shrink-0 leading-none"
          >
            ×
          </button>
        </div>
      )}
      {confirmingCancel && (
        <div className="rounded-lg bg-status-danger/10 border border-status-danger/30 px-3 py-2 space-y-2">
          <p className="text-status-danger text-xs">
            {t(isStop ? "operator.lifecycle.stop_confirm_message" : "operator.lifecycle.cancel_confirm_message")}
          </p>
          <div className="flex gap-2">
            <LifecycleButton tone="danger" disabled={pending !== null} loading={pending === "cancelled"} onClick={() => handleClick("cancelled")}>
              {t(isStop ? "operator.lifecycle.stop_confirm_yes" : "operator.lifecycle.cancel_confirm_yes")}
            </LifecycleButton>
            <LifecycleButton tone="ghost" disabled={pending !== null} onClick={() => setConfirmingCancel(false)}>
              {t("operator.lifecycle.cancel_confirm_no")}
            </LifecycleButton>
          </div>
        </div>
      )}
      {confirmingAutonomousStart && (
        <div className="rounded-lg bg-brand-500/10 border border-brand-500/30 px-3 py-2 space-y-2">
          <p className="text-brand-400 text-xs">{t("operator.lifecycle.autonomous_start_confirm_message")}</p>
          <div className="flex gap-2">
            <LifecycleButton tone="primary" disabled={autonomousStartPending} loading={autonomousStartPending} onClick={handleAutonomousStartClick}>
              {t("operator.lifecycle.autonomous_start_confirm_yes")}
            </LifecycleButton>
            <LifecycleButton tone="ghost" disabled={autonomousStartPending} onClick={() => setConfirmingAutonomousStart(false)}>
              {t("operator.lifecycle.cancel_confirm_no")}
            </LifecycleButton>
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {options?.map(({ action, labelKey, tone }) => (
          <LifecycleButton
            key={action}
            tone={action === "cancelled" ? "danger" : tone}
            disabled={!isLive || pending !== null || (action === "cancelled" && confirmingCancel)}
            loading={pending === action && !confirmingCancel}
            onClick={() => handleClick(action)}
          >
            {t(labelKey)}
          </LifecycleButton>
        ))}
        {canRequestAutonomousStart && (
          <LifecycleButton
            tone="primary"
            disabled={!isLive || pending !== null || autonomousStartPending || confirmingAutonomousStart}
            loading={autonomousStartPending && !confirmingAutonomousStart}
            onClick={handleAutonomousStartClick}
          >
            {t("operator.lifecycle.autonomous_start")}
          </LifecycleButton>
        )}
      </div>
    </div>
  );
}
