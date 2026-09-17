"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
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
    // Cancelling a running work order does not stop the local harness
    // process — it only marks the work order as withdrawn so a later
    // result import can no longer land on it (running -> cancelled means
    // the harness's eventual running -> review_ready/blocked/failed import
    // attempt is rejected as an illegal_transition instead of clobbering a
    // cancelled work order).
    { action: "cancelled", labelKey: "operator.lifecycle.cancel", variant: "secondary" },
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
  const options = TRANSITIONS[status];

  if (!options || options.length === 0) return null;

  async function handleClick(action: WorkOrderStatus) {
    setPending(action);
    try {
      await onStatusChange(action);
    } finally {
      setPending(null);
    }
  }

  return (
    <Card variant="bordered">
      <CardHeader>
        <CardTitle>{t("operator.lifecycle.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {!isLive && <p className="text-amber-400/70 text-xs">{t("operator.lifecycle.demo_note")}</p>}
        <div className="flex flex-wrap gap-2">
          {options.map(({ action, labelKey, variant }) => (
            <Button
              key={action}
              size="sm"
              variant={variant}
              disabled={!isLive || pending !== null}
              loading={pending === action}
              onClick={() => handleClick(action)}
            >
              {t(labelKey)}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
