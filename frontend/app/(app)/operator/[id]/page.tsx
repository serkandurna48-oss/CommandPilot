"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { PageLoader } from "@/components/ui/Spinner";
import { WorkOrderDetail } from "@/components/operator/WorkOrderDetail";
import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
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
  // A genuine 404 (this id really doesn't exist for this user) still falls
  // back to the mock/demo lookup below. Anything else — expired token,
  // network error, a transient 503 — is a real, distinguishable failure and
  // must show up as one. Found live 23.09.2026: this page used to fall back
  // to mock data (and, since the real id isn't in the mock seed set, render
  // the generic "no work orders" empty state) on ANY fetch failure including
  // a transient 503 — a real backend hiccup was indistinguishable from "this
  // work order doesn't exist," with only a console.error nobody sees. Same
  // anti-pattern CLAUDE.md already flags for mockWorkOrders.ts in general;
  // this route just hadn't been fixed yet. See RunnerConnections.tsx's
  // loadError for the established pattern this mirrors.
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const raw = await api.workOrders.get(id);
      setBundle(mapWorkOrderDetailFromApi(raw));
      setIsLive(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        // Genuinely unknown id — demo/seed data is the honest fallback here.
        setBundle(mockBundle(id));
        setIsLive(false);
      } else {
        console.error(`Operator: failed to load work order ${id}:`, err);
        setBundle(null);
        setLoadError(err instanceof Error ? err.message : "error");
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // Live view (CP live-execution feature): while a work order is actually
  // running, subscribe to Realtime postgres_changes on the three tables the
  // run touches and re-run the same load() the initial fetch already uses —
  // reusing load() (rather than hand-merging raw Realtime row shapes into
  // state) means every field this page ever renders always goes through the
  // same trusted mapWorkOrderDetailFromApi() path, with no risk of a
  // partial/incorrectly-shaped Realtime payload silently clobbering a field
  // (e.g. order.approvalScopeId, which the API computes but isn't a literal
  // column on the `work_orders` row Realtime would otherwise hand us).
  // Debounced: a single harness action (e.g. a step PATCH alongside an
  // activity-log POST) can fire multiple change events almost
  // simultaneously — coalesce them into one reload instead of one per event.
  // Only subscribed for a real (isLive), currently-running order; a
  // completed/demo view has nothing left to watch.
  const reloadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isRunning = isLive && bundle?.order.status === "running";
  useEffect(() => {
    if (!isRunning) return;

    const scheduleReload = () => {
      if (reloadTimerRef.current) clearTimeout(reloadTimerRef.current);
      reloadTimerRef.current = setTimeout(() => { load(); }, 400);
    };

    // Topic name includes a per-mount-instance random suffix, not just id —
    // in React 18 dev Strict Mode (mount -> cleanup -> mount), removeChannel()
    // below tears the previous channel down asynchronously, so a same-named
    // channel() call from the second mount can otherwise race and return the
    // still-subscribed first instance, which then throws on .on() ("cannot
    // add postgres_changes callbacks ... after subscribe()") — reproduced
    // live during verification of this feature. A unique topic per instance
    // sidesteps the race entirely rather than depending on teardown timing.
    const channel = supabase
      .channel(`work-order-${id}-${Math.random().toString(36).slice(2)}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "work_orders", filter: `id=eq.${id}` }, scheduleReload)
      .on("postgres_changes", { event: "*", schema: "public", table: "work_order_steps", filter: `work_order_id=eq.${id}` }, scheduleReload)
      .on("postgres_changes", { event: "*", schema: "public", table: "activity_logs", filter: `work_order_id=eq.${id}` }, scheduleReload)
      .subscribe();

    return () => {
      if (reloadTimerRef.current) clearTimeout(reloadTimerRef.current);
      supabase.removeChannel(channel);
    };
  }, [isRunning, id, load]);

  async function handleStatusChange(status: WorkOrderStatus) {
    if (!isLive) return; // lifecycle controls are display-only against seed data
    await api.workOrders.update(id, { status });
    await load();
  }

  // "Autonom starten" — not a status transition, sets the trigger signal
  // scripts/run_work_order_daemon.py polls for (see LifecycleControls.tsx's
  // onRequestAutonomousStart docstring). Status stays "queued" until the
  // daemon's own run_work_order.py invocation flips it to "running", at
  // which point the Realtime subscription above already picks it up live.
  async function handleRequestAutonomousStart() {
    if (!isLive) return;
    await api.workOrders.update(id, { daemon_run_requested_at: new Date().toISOString() });
    await load();
  }

  return (
    <>
      <div className="mb-6">
        <Link href="/operator">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> {t("operator.back")}
          </Button>
        </Link>
      </div>

      {loading ? (
        <PageLoader />
      ) : loadError ? (
        <div className="rounded-lg bg-status-danger/10 border border-status-danger/30 px-4 py-3 flex items-center justify-between gap-3">
          <p className="text-status-danger text-sm">
            {t("operator.load_error")} {loadError}
          </p>
          <Button size="sm" variant="outline-accent" onClick={load}>
            {t("button.retry")}
          </Button>
        </div>
      ) : !bundle ? (
        <p className="text-[var(--text-tertiary)] text-sm">{t("operator.empty_title")}</p>
      ) : (
        <WorkOrderDetail
          {...bundle}
          isLive={isLive}
          onStatusChange={handleStatusChange}
          onRequestAutonomousStart={handleRequestAutonomousStart}
        />
      )}
    </>
  );
}
