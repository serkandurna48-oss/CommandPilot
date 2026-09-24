"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDateShort } from "@/lib/utils";
import type { DailyPlan } from "@/types";

// GET /api/plans/me has existed since the backend's first cut but was never
// called from the frontend — every daily plan a user ever generated was
// reachable only by already knowing its URL (e.g. from a stale bookmark or
// the dashboard's "open today's plan" link), never browsable. Same fix as
// CheckinHistory.tsx for the equivalent gap: pure read-surface, no backend
// change. Renders nothing while loading or once confirmed empty.
//
// Found live in production (24.09.2026), same bug as CheckinHistory.tsx: a
// failed fetch was treated as "confirmed empty" and rendered nothing — a
// real plan history could silently vanish with no indication of failure.
export function PlanHistory() {
  const t = useT();
  const [plans, setPlans] = useState<DailyPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    const currentRequest = ++requestId.current;
    setError(null);
    api.plans
      .listMine()
      .then((data) => {
        if (currentRequest === requestId.current) setPlans(data);
      })
      .catch((e: unknown) => {
        if (currentRequest === requestId.current) {
          setError(e instanceof Error ? e.message : String(e));
        }
      });
  }, []);

  useEffect(() => {
    load();
    // Ignore responses from an earlier request or a cleaned-up effect.
    return () => { requestId.current += 1; };
  }, [load]);

  if (error !== null) {
    return (
      <div className="mt-8 flex items-center justify-between gap-3 rounded-2xl border border-status-danger/30 bg-status-danger/10 px-4 py-3">
        <p className="text-status-danger text-sm">{t("error.load_failed")} {error}</p>
        <Button size="sm" variant="outline-accent" onClick={load}>
          {t("button.retry")}
        </Button>
      </div>
    );
  }

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
