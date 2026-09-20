"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageLoader } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { mapWorkOrderFromApi } from "@/lib/workOrderMapper";
import { HomeBriefing, buildActivity } from "@/components/dashboard/HomeBriefing";
import type { DailyPlan, WorkOrder } from "@/types";

export default function DashboardPage() {
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [plansResult, ordersResult] = await Promise.allSettled([
      api.plans.listMine(),
      api.workOrders.listMine(),
    ]);
    if (plansResult.status === "fulfilled" && plansResult.value.length > 0) {
      setPlan(plansResult.value[0]);
    }
    if (ordersResult.status === "fulfilled") {
      setOrders(ordersResult.value.map(mapWorkOrderFromApi));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const needsDecision = useMemo(
    () =>
      orders
        .filter((o) => o.status === "needs_approval")
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [orders]
  );
  const inProgress = useMemo(
    () =>
      orders
        .filter((o) => o.status === "running" || o.status === "queued")
        .sort(
          (a, b) =>
            new Date(b.startedAt ?? b.createdAt).getTime() - new Date(a.startedAt ?? a.createdAt).getTime()
        ),
    [orders]
  );
  const activity = useMemo(() => buildActivity(orders).slice(0, 6), [orders]);

  // Resolving the block that paused the order is the one real, domain-correct
  // one-click action here (LifecycleControls.tsx: needs_approval -> queued is
  // labeled "Requeue", never "Approve" — that verb belongs to the Jarvis
  // suggested-action flow, a different transition entirely). Everything else
  // (cancel, deeper review) goes through the unchanged operator detail page.
  async function requeue(id: string) {
    setPendingId(id);
    try {
      await api.workOrders.update(id, { status: "queued" });
      await load();
    } finally {
      setPendingId(null);
    }
  }

  if (loading) return <PageLoader />;

  return (
    <HomeBriefing
      plan={plan}
      needsDecision={needsDecision}
      inProgress={inProgress}
      activity={activity}
      pendingId={pendingId}
      onRequeue={requeue}
    />
  );
}
