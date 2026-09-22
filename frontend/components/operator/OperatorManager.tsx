"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/ui/Spinner";
import { SafetyRulesPanel } from "@/components/operator/SafetyRulesPanel";
import { MOCK_WORK_ORDERS } from "@/lib/mockWorkOrders";
import { WORK_ORDER_STATUS_COLORS } from "@/lib/operatorStyles";
import { api } from "@/lib/api";
import { mapWorkOrderFromApi } from "@/lib/workOrderMapper";
import { useT } from "@/lib/i18n";
import type { WorkOrder } from "@/types";
import { Clock, FolderTree, ChevronRight, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

// Mission Control redesign (/operator, /operator/[id] only — see
// WorkOrderDetail.tsx's docstring for the full rationale/scope). Plain
// dark cards instead of components/ui/Card, for the same reason
// LifecycleControls.tsx's MissionButton bypasses components/ui/Button:
// avoids gambling on Tailwind class-order specificity against the shared
// component's own bg/border utilities, and keeps that shared component
// (used by every non-Operator page) completely untouched.
function WorkOrderCard({ order }: { order: WorkOrder }) {
  const t = useT();
  const isRunning = order.status === "running";

  return (
    <Link href={`/operator/${order.id}`}>
      <div className={cn(
        "rounded-lg border bg-black/40 hover:bg-black/60 motion-safe:transition-colors px-4 py-3",
        isRunning ? "border-emerald-800/50" : "border-slate-800"
      )}>
        <div className="flex gap-3 items-start">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              {isRunning && (
                <span className="relative flex h-1.5 w-1.5 shrink-0">
                  <span className="motion-safe:animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
                </span>
              )}
              <p className="text-slate-200 text-sm font-medium">{order.title}</p>
              <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wide", WORK_ORDER_STATUS_COLORS[order.status])}>
                {t(`operator.status.${order.status}`)}
              </span>
            </div>
            <p className="text-slate-500 text-xs mb-1.5 line-clamp-2">{order.goal}</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-600 font-mono">
              <span className="flex items-center gap-1">
                <FolderTree className="h-3 w-3" /> {order.repo}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" /> {order.timeLimitMinutes} {t("operator.section.minutes")}
              </span>
            </div>
          </div>
          <ChevronRight className="h-4 w-4 text-slate-700 shrink-0 mt-1" />
        </div>
      </div>
    </Link>
  );
}

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="text-[11px] font-mono text-amber-400/70 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2 flex-1 min-w-0">
          {usingMocks ? t("operator.mock_banner") : t("operator.live_banner")}
        </div>
        <Link href="/operator/new">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-400 bg-emerald-500 hover:bg-emerald-400 text-black font-mono text-[11px] uppercase tracking-wide px-3 py-2"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("operator.list.new_button")}
          </button>
        </Link>
      </div>

      {loading ? (
        <div className="py-8 flex justify-center">
          <div className="h-6 w-6 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin" />
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          title={t("operator.empty_title")}
          description={t("operator.empty_desc")}
          action={
            <Link href="/operator/new">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-md border border-emerald-400 bg-emerald-500 hover:bg-emerald-400 text-black font-mono text-[11px] uppercase tracking-wide px-3 py-2"
              >
                <Plus className="h-3.5 w-3.5" />
                {t("operator.empty_cta")}
              </button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <WorkOrderCard key={order.id} order={order} />
          ))}
        </div>
      )}

      <SafetyRulesPanel />
    </div>
  );
}
