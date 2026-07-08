"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
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

function WorkOrderCard({ order }: { order: WorkOrder }) {
  const t = useT();

  return (
    <Link href={`/operator/${order.id}`}>
      <Card className="hover:border-slate-600 transition-colors cursor-pointer">
        <CardContent className="py-3">
          <div className="flex gap-3 items-start">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1.5">
                <p className="text-slate-200 text-sm font-medium">{order.title}</p>
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono", WORK_ORDER_STATUS_COLORS[order.status])}>
                  {t(`operator.status.${order.status}`)}
                </span>
              </div>
              <p className="text-slate-400 text-xs mb-1.5 line-clamp-2">{order.goal}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                <span className="flex items-center gap-1">
                  <FolderTree className="h-3 w-3" /> {order.repo}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {order.timeLimitMinutes} {t("operator.section.minutes")}
                </span>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-slate-600 shrink-0 mt-1" />
          </div>
        </CardContent>
      </Card>
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
          <Button size="sm">
            <Plus className="h-4 w-4" />
            {t("operator.list.new_button")}
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="py-8 flex justify-center">
          <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          title={t("operator.empty_title")}
          description={t("operator.empty_desc")}
          action={
            <Link href="/operator/new">
              <Button size="sm">
                <Plus className="h-4 w-4" />
                {t("operator.empty_cta")}
              </Button>
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
