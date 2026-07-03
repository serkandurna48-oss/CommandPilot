"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn, formatDate } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import type { DailyPlan, Project } from "@/types";

function getGreetingKey(): string {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return "greeting.morning";
  if (h >= 12 && h < 17) return "greeting.afternoon";
  if (h >= 17 && h < 22) return "greeting.evening";
  return "greeting.night";
}

function SystemChip({
  label,
  value,
  dim,
  highlight,
}: {
  label: string;
  value: string;
  dim?: boolean;
  highlight?: boolean;
}) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 text-[9px] font-mono px-2 py-0.5 rounded border uppercase tracking-widest",
      highlight && "bg-brand-600/10 border-brand-500/20 text-brand-400/70",
      !highlight && !dim && "bg-slate-900/60 border-slate-800 text-slate-500",
      dim && "bg-slate-950 border-slate-900 text-slate-700",
    )}>
      <span className={cn("font-light", dim && "opacity-50")}>{label}</span>
      <span className="opacity-40 px-0.5">·</span>
      <span>{value}</span>
    </span>
  );
}

export function CommandHero({
  plan,
  focusProject,
  online,
  activeCount,
  noiseCount,
}: {
  plan: DailyPlan | null;
  focusProject: Project | null;
  online: boolean;
  activeCount: number;
  noiseCount: number;
}) {
  const t = useT();
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-slate-800/60 bg-slate-950 px-6 py-10 md:px-10 md:py-14"
      style={{
        backgroundImage:
          "radial-gradient(ellipse at 85% 15%, rgba(79,70,229,0.1) 0%, transparent 55%)",
      }}
    >
      {/* Atmosphere rings — absolute positioned, cut off by overflow-hidden */}
      <div className="pointer-events-none absolute -right-24 -top-24 h-[380px] w-[380px] rounded-full border border-brand-500/6" />
      <div className="pointer-events-none absolute -right-10 -top-10 h-[240px] w-[240px] rounded-full border border-brand-500/10" />
      <div className="pointer-events-none absolute right-2 top-2 h-[140px] w-[140px] rounded-full border border-brand-500/16 bg-brand-600/4" />

      {/* Content */}
      <div className="relative z-10 max-w-3xl">

        {/* Meta row */}
        <div className="flex items-center gap-3 flex-wrap mb-5">
          <p className="text-[10px] font-mono text-slate-600 uppercase tracking-[0.2em]">
            {t(getGreetingKey())}
          </p>
          <span className="text-slate-600 text-[10px]">·</span>
          <p className="text-[10px] font-mono text-slate-600 uppercase tracking-widest">
            {formatDate(plan?.plan_date ?? today)}
          </p>
        </div>

        {/* System status chips */}
        <div className="flex flex-wrap gap-1.5 mb-6">
          {plan?.day_mode && (
            <SystemChip label="MODE" value={plan.day_mode} highlight />
          )}
          {activeCount > 0 && (
            <SystemChip label="SIGNAL" value={`${activeCount} ACTIVE`} />
          )}
          {noiseCount > 0 && (
            <SystemChip label="NOISE" value={`${noiseCount} SUPPRESSED`} dim />
          )}
          {!plan && (
            <SystemChip label="STATUS" value="STANDBY" dim />
          )}
        </div>

        {/* Main content */}
        {plan ? (
          <div>
            {plan.main_win ? (
              <h1 className="text-3xl md:text-4xl lg:text-5xl font-light leading-[1.15] tracking-tight text-slate-50 mb-4">
                {plan.main_win}
              </h1>
            ) : (
              <h1 className="text-3xl md:text-4xl font-light leading-tight text-slate-400 mb-4">
                {t("dashboard.hero.standby")}
              </h1>
            )}
            {plan.status_summary && (
              <p className="text-slate-500 text-sm leading-relaxed line-clamp-2 max-w-2xl mb-6">
                {plan.status_summary}
              </p>
            )}
          </div>
        ) : (
          <div className="mb-6">
            <h1 className="text-3xl md:text-4xl font-light leading-tight text-slate-600 mb-3">
              {t("dashboard.hero.standby")}
            </h1>
            <p className="text-slate-700 text-sm leading-relaxed max-w-md">
              {t("dashboard.no_plan_sub")}
            </p>
          </div>
        )}

        {/* CTAs — quiet, minimal */}
        <div className="flex flex-wrap gap-2">
          {plan ? (
            <>
              <Link href={`/plans/${plan.id}`}>
                <Button variant="secondary" size="sm">
                  {t("dashboard.view_plan")} <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
              <Link href="/morning">
                <Button variant="ghost" size="sm">{t("dashboard.new_checkin")}</Button>
              </Link>
            </>
          ) : (
            <Link href="/morning">
              <Button size="md">
                {t("dashboard.start_checkin")} <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
