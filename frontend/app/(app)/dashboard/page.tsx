"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageLoader } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { mapWorkOrderFromApi } from "@/lib/workOrderMapper";
import { useSetJarvisContext } from "@/lib/jarvisContext";
import { HomeBriefing, buildActivity } from "@/components/dashboard/HomeBriefing";
import type { DailyPlan, Project, WorkOrder } from "@/types";

export default function DashboardPage() {
  const t = useT();
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  // Confirmed against e8c2b02: a rejected projectsResult left `projects` at
  // its initial [], and ProjectCards.tsx cannot tell "you have zero
  // projects" from "the fetch failed" — the section either rendered its
  // normal empty state or nothing at all, silently. Same anti-pattern
  // CLAUDE.md already flags for mockWorkOrders.ts: an API failure must
  // never look identical to "nothing here."
  const [projectsError, setProjectsError] = useState<string | null>(null);
  // Confirmed live in production (24.09.2026): unlike the projects fetch
  // above, a rejected plans/work-orders call was never surfaced at all —
  // "Kein Tagesplan bisher" and empty Needs-Decision/In-Progress/Activity
  // sections are also this page's genuine empty states, so a failure here
  // was completely indistinguishable from "nothing pending today." Same
  // anti-pattern, same fix, just not carried over to these two fetches
  // when projectsError was first added.
  const [plansError, setPlansError] = useState<string | null>(null);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [plansResult, ordersResult, projectsResult] = await Promise.allSettled([
      api.plans.listMine(),
      api.workOrders.listMine(),
      api.projects.listMine(),
    ]);
    if (plansResult.status === "fulfilled") {
      setPlan(plansResult.value[0] ?? null);
      setPlansError(null);
    } else {
      const err = plansResult.reason;
      setPlansError(err instanceof Error ? err.message : String(err));
    }
    if (ordersResult.status === "fulfilled") {
      setOrders(ordersResult.value.map(mapWorkOrderFromApi));
      setOrdersError(null);
    } else {
      const err = ordersResult.reason;
      setOrdersError(err instanceof Error ? err.message : String(err));
    }
    if (projectsResult.status === "fulfilled") {
      setProjects(projectsResult.value);
      setProjectsError(null);
    } else {
      // No t() here — a fresh function reference every render would make
      // this callback (and the effect depending on it) re-run on every
      // render, refetching in a loop. Same "stable — no t dependency"
      // convention as ProjectsManager.tsx's loadProjects(); the fallback
      // is translated at render time instead (see JSX below).
      const err = projectsResult.reason;
      setProjectsError(err instanceof Error ? err.message : String(err));
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

  // Contextual Intelligence Workspace pass: Home pushes its own real
  // snapshot (today's plan, approval count, in-progress count) instead of
  // relying on the generic per-route fallback in jarvisContext.tsx — same
  // pattern as ProjectsManager's selected-project context. No new visual
  // section on Home itself; this only feeds the Jarvis panel/page.
  const jarvisCtx = useMemo(
    () => ({
      route: "home",
      kicker: t("jarvis.kicker.home"),
      title: t("jarvis.context.home.title"),
      summary: t("jarvis.context.home.summary"),
      snapshot: [
        {
          label: t("jarvis.snapshot.today"),
          value: plan
            ? plan.main_win || plan.status_summary || `${t("jarvis.snapshot.plan_for")}: ${plan.plan_date}`
            : t("jarvis.snapshot.no_plan"),
        },
        { label: t("jarvis.snapshot.decisions"), value: `${needsDecision.length} ${t("jarvis.snapshot.awaiting_approval")}` },
        { label: t("jarvis.snapshot.running"), value: `${inProgress.length} ${t("jarvis.snapshot.in_progress_suffix")}` },
      ],
      quickActions: [
        {
          label: t("jarvis.qa.review_today"),
          description: t("jarvis.qa.review_today_desc"),
          icon: "review" as const,
          workingLabel: t("jarvis.qa.review_today_working"),
          resultLabel: t("jarvis.qa.review_today_result"),
          prompt:
            `Review today's plan.` +
            (plan?.main_win ? ` Main win on file: ${plan.main_win}.` : "") +
            (plan?.status_summary ? ` Status: ${plan.status_summary}.` : "") +
            (!plan ? " No plan has been generated yet." : ""),
        },
        {
          label: t("jarvis.qa.check_blocked"),
          description: t("jarvis.qa.check_blocked_desc"),
          icon: "blocked" as const,
          workingLabel: t("jarvis.qa.check_blocked_working"),
          resultLabel: t("jarvis.qa.check_blocked_result"),
          prompt: `Check blocked work. ${needsDecision.length} work order(s) currently need my approval.`,
        },
        {
          label: t("jarvis.qa.prioritize_projects"),
          description: t("jarvis.qa.prioritize_projects_desc"),
          icon: "priority" as const,
          workingLabel: t("jarvis.qa.prioritize_projects_working"),
          resultLabel: t("jarvis.qa.prioritize_projects_result"),
          prompt: `Help me prioritize my projects. I currently have ${projects.length} project(s) on file.`,
        },
        {
          label: t("jarvis.suggestion.3"),
          description: t("jarvis.qa.plan_day_desc"),
          icon: "next_move" as const,
          workingLabel: t("jarvis.qa.plan_day_working"),
          resultLabel: t("jarvis.qa.plan_day_result"),
          prompt: t("jarvis.suggestion.3"),
        },
      ],
    }),
    [t, plan, needsDecision.length, inProgress.length, projects.length]
  );

  useSetJarvisContext(jarvisCtx);

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
      planError={plansError}
      needsDecision={needsDecision}
      inProgress={inProgress}
      ordersError={ordersError}
      activity={activity}
      projects={projects}
      projectsError={projectsError}
      onRetryProjects={load}
      onRetryOrders={load}
      onRetryPlan={load}
      pendingId={pendingId}
      onRequeue={requeue}
    />
  );
}
