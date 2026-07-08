"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { PageLoader } from "@/components/ui/Spinner";
import { WorkOrderDetail } from "@/components/operator/WorkOrderDetail";
import { api } from "@/lib/api";
import { mapWorkOrderDetailFromApi, type WorkOrderDetailBundle } from "@/lib/workOrderMapper";
import {
  getWorkOrder,
  getApprovalScope,
  getSteps,
  getAgentRuns,
  getActivityLog,
  getArtifacts,
  getReviewPackage,
} from "@/lib/mockWorkOrders";
import { useT } from "@/lib/i18n";
import type { WorkOrderStatus } from "@/types";
import { ArrowLeft } from "lucide-react";

interface Props {
  params: { id: string };
}

function mockBundle(id: string): WorkOrderDetailBundle | null {
  const order = getWorkOrder(id);
  if (!order) return null;
  return {
    order,
    approvalScope: getApprovalScope(id),
    steps: getSteps(id),
    agentRuns: getAgentRuns(id),
    activityLog: getActivityLog(id),
    artifacts: getArtifacts(id),
    reviewPackage: getReviewPackage(id),
  };
}

export default function WorkOrderPage({ params }: Props) {
  const { id } = params;
  const t = useT();
  const [bundle, setBundle] = useState<WorkOrderDetailBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await api.workOrders.get(id);
      setBundle(mapWorkOrderDetailFromApi(raw));
      setIsLive(true);
    } catch (err) {
      // API/table not deployed yet, this id only exists as seed data, or a
      // real request failure (expired token, network issue, 500) — fall
      // back to the mock lookup so the detail view stays demonstrable
      // either way. Logged (not swallowed) so a genuine live-system
      // problem isn't indistinguishable from "no backend deployed"
      // (OP-UX-001).
      console.error(`Operator: falling back to Demo Mode for work order ${id}, fetch failed:`, err);
      setBundle(mockBundle(id));
      setIsLive(false);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function handleStatusChange(status: WorkOrderStatus) {
    if (!isLive) return; // lifecycle controls are display-only against seed data
    await api.workOrders.update(id, { status });
    await load();
  }

  return (
    <AppShell wide>
      <div className="mb-6">
        <Link href="/operator">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> {t("operator.back")}
          </Button>
        </Link>
      </div>

      {loading ? (
        <PageLoader />
      ) : !bundle ? (
        <p className="text-slate-400 text-sm">{t("operator.empty_title")}</p>
      ) : (
        <WorkOrderDetail {...bundle} isLive={isLive} onStatusChange={handleStatusChange} />
      )}
    </AppShell>
  );
}
