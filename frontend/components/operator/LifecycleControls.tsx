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
// running → review_ready is exclusively the import script's job (see
// scripts/import_work_order_result.py's atomic gate, OP-Import-Integrity-001)
// — no manual button here for that transition. The backend now rejects a
// direct PATCH to review_ready without a review package regardless
// (OP-E2E-Loop-001), but removing the button avoids offering an action
// that would just fail with a 400.
const TRANSITIONS: Partial<Record<WorkOrderStatus, { action: WorkOrderStatus; labelKey: string; variant: "primary" | "secondary" }[]>> = {
  draft: [{ action: "approved", labelKey: "operator.lifecycle.approve", variant: "primary" }],
  approved: [{ action: "queued", labelKey: "operator.lifecycle.mark_queued", variant: "primary" }],
  queued: [{ action: "running", labelKey: "operator.lifecycle.mark_running", variant: "primary" }],
  review_ready: [
    { action: "accepted", labelKey: "operator.lifecycle.accept", variant: "primary" },
    { action: "rework_requested", labelKey: "operator.lifecycle.request_rework", variant: "secondary" },
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
