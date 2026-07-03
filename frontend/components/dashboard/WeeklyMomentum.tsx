"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";
import { formatDateShort } from "@/lib/utils";
import type { DailyPlan } from "@/types";

export function WeeklyMomentum({ recentPlans }: { recentPlans: DailyPlan[] }) {
  const t = useT();

  if (recentPlans.length < 2) return null;

  return (
    <div className="border-t border-slate-800/70 pt-5">
      <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-600 mb-3">
        {t("dashboard.momentum.title")}
      </p>
      <div className="flex flex-wrap gap-2">
        {recentPlans.map((plan) => (
          <Link
            key={plan.id}
            href={`/plans/${plan.id}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-slate-800/80 bg-slate-900 hover:border-slate-700/60 hover:bg-slate-800/60 transition-colors group"
          >
            <span className="text-[10px] font-mono text-slate-600 group-hover:text-slate-400 transition-colors">
              {formatDateShort(plan.plan_date)}
            </span>
            {plan.day_mode && (
              <span className="text-[9px] text-slate-700 group-hover:text-slate-600 transition-colors truncate max-w-[72px]">
                · {plan.day_mode}
              </span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
