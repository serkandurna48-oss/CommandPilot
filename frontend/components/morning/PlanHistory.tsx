"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDateShort } from "@/lib/utils";
import type { DailyPlan } from "@/types";

// GET /api/plans/me has existed since the backend's first cut but was never
// called from the frontend — every daily plan a user ever generated was
// reachable only by already knowing its URL (e.g. from a stale bookmark or
// the dashboard's "open today's plan" link), never browsable. Same fix as
// CheckinHistory.tsx for the equivalent gap: pure read-surface, no backend
// change. Renders nothing until at least one plan exists.
export function PlanHistory() {
  const t = useT();
  const [plans, setPlans] = useState<DailyPlan[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.plans
      .listMine()
      .then((res) => {
        if (!cancelled) setPlans(res);
      })
      .catch(() => {
        if (!cancelled) setPlans([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!plans || plans.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-3">
        {t("morning.plan_history.title")}
      </h2>
      <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] divide-y divide-white/[0.05] overflow-hidden">
        {plans.slice(0, 14).map((p) => (
          <Link
            key={p.id}
            href={`/plans/${p.id}`}
            className="flex items-center gap-3 px-4 py-2.5 text-sm motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)]"
          >
            <span className="text-[var(--text-tertiary)] text-xs font-mono w-20 shrink-0">
              {formatDateShort(p.plan_date)}
            </span>
            <span className="text-[var(--text-secondary)] flex-1 truncate">
              {p.main_win || t("morning.plan_history.untitled")}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
