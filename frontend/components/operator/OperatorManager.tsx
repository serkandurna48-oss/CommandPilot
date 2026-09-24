"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/Spinner";
import { SafetyRulesPanel } from "@/components/operator/SafetyRulesPanel";
import { MOCK_WORK_ORDERS } from "@/lib/mockWorkOrders";
import { WORK_ORDER_STATUS_COLORS, WORK_ORDER_STATUS_DOT } from "@/lib/operatorStyles";
import { api } from "@/lib/api";
import { mapWorkOrderFromApi } from "@/lib/workOrderMapper";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { WorkOrder, WorkOrderStatus } from "@/types";
import { Plus, ChevronDown } from "lucide-react";

function StatusBadge({ status }: { status: WorkOrderStatus }) {
  const t = useT();
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium whitespace-nowrap shrink-0", WORK_ORDER_STATUS_COLORS[status])}>
      {t(`operator.status.${status}`)}
    </span>
  );
}

// One row, same composition family as HomeBriefing's operational rail
// (status dot + title + badge, secondary line for the goal, tertiary mono
// line for repo/time) — the Operator overview is the full version of the
// same list Home only shows a slice of, so it should read as the same
// product, not a separate "terminal" surface.
function WorkOrderRow({ order }: { order: WorkOrder }) {
  const t = useT();
  return (
    <Link
      href={`/operator/${order.id}`}
      className="block px-4 py-3 motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)] focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[-1px] focus-visible:outline-[var(--interactive-border-focus)]"
    >
      <div className="flex items-start gap-3">
        <span className={cn("h-2 w-2 rounded-full shrink-0 mt-1.5", WORK_ORDER_STATUS_DOT[order.status])} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-[var(--text-primary)] truncate">{order.title}</p>
            <StatusBadge status={order.status} />
          </div>
          <p className="text-[var(--text-secondary)] text-xs mt-1 line-clamp-1">{order.goal}</p>
          <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-1.5 truncate">
            {order.repo} · {order.timeLimitMinutes} {t("operator.section.minutes")}
          </p>
        </div>
      </div>
    </Link>
  );
}

// Same surface pattern as HomeBriefing's Section (rounded-2xl, hairline
// border, header + divide-y rows) — collapsible is opt-in per group, only
// the least-actionable bucket (Completed) defaults to closed so a long
// history doesn't bury the groups that actually need a look.
function Group({
  title,
  count,
  collapsible,
  children,
}: {
  title: string;
  count: number;
  collapsible?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(!collapsible);
  if (count === 0) return null;

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)]">
      <button
        type="button"
        onClick={collapsible ? () => setOpen((v) => !v) : undefined}
        className={cn(
          "w-full flex items-center justify-between gap-3 px-4 py-2.5",
          open && "border-b border-white/[0.06]",
          collapsible && "cursor-pointer"
        )}
      >
        <span className="flex items-center gap-2">
          <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">{title}</h2>
          <span className="text-[11px] font-mono text-[var(--text-placeholder)]">{count}</span>
        </span>
        {collapsible && (
          <ChevronDown className={cn("h-3.5 w-3.5 text-[var(--text-tertiary)] motion-safe:transition-transform", !open && "-rotate-90")} />
        )}
      </button>
      {open && <div className="divide-y divide-white/[0.05]">{children}</div>}
    </div>
  );
}

const ATTENTION_STATUSES: WorkOrderStatus[] = ["needs_approval", "blocked", "rework_requested", "failed"];
const PROGRESS_STATUSES: WorkOrderStatus[] = ["running", "review_ready"];
const QUEUE_STATUSES: WorkOrderStatus[] = ["draft", "approved", "queued"];
const DONE_STATUSES: WorkOrderStatus[] = ["accepted", "cancelled"];

export function OperatorManager() {
  const t = useT();
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [usingMocks, setUsingMocks] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await api.workOrders.listMine();
      setOrders(raw.map(mapWorkOrderFromApi));
      setUsingMocks(false);
    } catch (err) {
      // Backend/table not deployed yet, or a real request failure (expired
      // token, network issue, 500) — fall back to seed data so the control
      // plane stays demonstrable either way. Logged (not swallowed) so a
      // genuine live-system problem isn't indistinguishable from "no
      // backend deployed" (OP-UX-001) — the amber banner alone can't carry
      // which case this actually is.
      console.error("Operator: falling back to Demo Mode, work order fetch failed:", err);
      setOrders(MOCK_WORK_ORDERS);
      setUsingMocks(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Real data only, grouped by urgency (not fabricated counts — see
  // ATTENTION/PROGRESS/QUEUE/DONE partitions of the actual fetched orders):
  // the one question this screen answers is "what needs a look," and a
  // single undifferentiated list of dozens of orders across nine possible
  // statuses (most of them long-finished) doesn't answer it.
  const groups = useMemo(() => ({
    attention: orders.filter((o) => ATTENTION_STATUSES.includes(o.status)),
    progress:  orders.filter((o) => PROGRESS_STATUSES.includes(o.status)),
    queue:     orders.filter((o) => QUEUE_STATUSES.includes(o.status)),
    done:      orders.filter((o) => DONE_STATUSES.includes(o.status)),
  }), [orders]);

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-5">
        <p className={cn("text-xs", usingMocks ? "text-status-warning font-medium" : "text-[var(--text-tertiary)]")}>
          {usingMocks ? t("operator.mock_banner") : t("operator.live_banner")}
        </p>
        <Link href="/operator/new" className="shrink-0">
          <Button size="sm" className="rounded-xl">
            <Plus className="h-4 w-4" />
            {t("operator.list.new_button")}
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center">
          <div className="h-6 w-6 rounded-full border-2 border-[var(--interactive-bg-primary-default)] border-t-transparent animate-spin" />
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          title={t("operator.empty_title")}
          description={t("operator.empty_desc")}
          action={
            <Link href="/operator/new">
              <Button size="sm" className="rounded-xl">
                <Plus className="h-4 w-4" />
                {t("operator.empty_cta")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          <Group title={t("operator.list.needs_attention")} count={groups.attention.length}>
            {groups.attention.map((order) => <WorkOrderRow key={order.id} order={order} />)}
          </Group>
          <Group title={t("operator.list.in_progress")} count={groups.progress.length}>
            {groups.progress.map((order) => <WorkOrderRow key={order.id} order={order} />)}
          </Group>
          <Group title={t("operator.list.queue")} count={groups.queue.length}>
            {groups.queue.map((order) => <WorkOrderRow key={order.id} order={order} />)}
          </Group>
          <Group title={t("operator.list.completed")} count={groups.done.length} collapsible>
            {groups.done.map((order) => <WorkOrderRow key={order.id} order={order} />)}
          </Group>
        </div>
      )}

      <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] mt-4">
        <div className="px-4 py-2.5 border-b border-white/[0.06]">
          <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">
            {t("operator.section.safety_rules")}
          </h2>
        </div>
        <div className="p-4">
          <SafetyRulesPanel />
        </div>
      </div>
    </div>
  );
}
