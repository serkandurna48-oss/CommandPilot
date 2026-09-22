"use client";

import { useState } from "react";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { WorkOrderStatus } from "@/types";
import { Loader2 } from "lucide-react";

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

// Mission Control's own button — deliberately NOT the shared
// components/ui/Button (whose bronze/graphite variants are the locked
// Focus Deck palette used everywhere else in the app). Fighting that
// component's variant classes via a className override risks a CSS
// specificity gamble depending on Tailwind's generated stylesheet order;
// a small, fully self-contained button here keeps the shared Button (and
// therefore every other page) completely untouched, matching this
// redesign's explicit "only /operator" scope.
function MissionButton({
  tone = "neutral",
  size = "sm",
  disabled,
  loading,
  onClick,
  children,
}: {
  tone?: "primary" | "danger" | "neutral" | "ghost";
  size?: "sm" | "md";
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  const toneClasses: Record<string, string> = {
    primary: "bg-emerald-500 hover:bg-emerald-400 text-black border-emerald-400",
    danger: "bg-transparent hover:bg-rose-950/40 text-rose-400 border-rose-800",
    neutral: "bg-black/40 hover:bg-black/60 text-slate-300 border-slate-700",
    ghost: "bg-transparent hover:bg-white/5 text-slate-500 border-transparent",
  };
  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md border font-mono uppercase tracking-wide motion-safe:transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
        size === "sm" ? "px-3 py-1.5 text-[11px]" : "px-4 py-2 text-xs",
        toneClasses[tone]
      )}
    >
      {loading && <Loader2 className="h-3 w-3 motion-safe:animate-spin" />}
      {children}
    </button>
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
    try {
      await onStatusChange(action);
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
    try {
      await onRequestAutonomousStart?.();
    } finally {
      setAutonomousStartPending(false);
    }
  }

  const isStop = status === "running"; // real interrupt, not just a withdrawal — see stop_confirm_message

  return (
    <div className="space-y-2">
      {!isLive && <p className="text-slate-500 text-xs font-mono">{t("operator.lifecycle.demo_note")}</p>}
      {confirmingCancel && (
        <div className="rounded-lg bg-rose-950/20 border border-rose-900/40 px-3 py-2 space-y-2">
          <p className="text-rose-300/90 text-xs">
            {t(isStop ? "operator.lifecycle.stop_confirm_message" : "operator.lifecycle.cancel_confirm_message")}
          </p>
          <div className="flex gap-2">
            <MissionButton tone="danger" disabled={pending !== null} loading={pending === "cancelled"} onClick={() => handleClick("cancelled")}>
              {t(isStop ? "operator.lifecycle.stop_confirm_yes" : "operator.lifecycle.cancel_confirm_yes")}
            </MissionButton>
            <MissionButton tone="ghost" disabled={pending !== null} onClick={() => setConfirmingCancel(false)}>
              {t("operator.lifecycle.cancel_confirm_no")}
            </MissionButton>
          </div>
        </div>
      )}
      {confirmingAutonomousStart && (
        <div className="rounded-lg bg-emerald-950/20 border border-emerald-900/40 px-3 py-2 space-y-2">
          <p className="text-emerald-300/90 text-xs">{t("operator.lifecycle.autonomous_start_confirm_message")}</p>
          <div className="flex gap-2">
            <MissionButton tone="primary" disabled={autonomousStartPending} loading={autonomousStartPending} onClick={handleAutonomousStartClick}>
              {t("operator.lifecycle.autonomous_start_confirm_yes")}
            </MissionButton>
            <MissionButton tone="ghost" disabled={autonomousStartPending} onClick={() => setConfirmingAutonomousStart(false)}>
              {t("operator.lifecycle.cancel_confirm_no")}
            </MissionButton>
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {options?.map(({ action, labelKey, tone }) => (
          <MissionButton
            key={action}
            tone={action === "cancelled" ? "danger" : tone}
            disabled={!isLive || pending !== null || (action === "cancelled" && confirmingCancel)}
            loading={pending === action && !confirmingCancel}
            onClick={() => handleClick(action)}
          >
            {t(labelKey)}
          </MissionButton>
        ))}
        {canRequestAutonomousStart && (
          <MissionButton
            tone="primary"
            disabled={!isLive || pending !== null || autonomousStartPending || confirmingAutonomousStart}
            loading={autonomousStartPending && !confirmingAutonomousStart}
            onClick={handleAutonomousStartClick}
          >
            {t("operator.lifecycle.autonomous_start")}
          </MissionButton>
        )}
      </div>
    </div>
  );
}
