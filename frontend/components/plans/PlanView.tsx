"use client";

import { DailyPlan } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn, BLOCK_TYPE_COLORS, formatDate } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { Target, Zap, Ban, HelpCircle, Trophy, Clock } from "lucide-react";

// Left accent strip color per block type (restrained, no neon)
const BLOCK_ACCENT_BG: Record<string, string> = {
  deep_work: "bg-brand-500",
  admin:     "bg-slate-500",
  sport:     "bg-amber-500/70",
  break:     "bg-slate-600",
  social:    "bg-pink-500/60",
  learning:  "bg-violet-500/60",
  personal:  "bg-indigo-400/60",
  other:     "bg-slate-500",
};

// Priority badge styles: 1st = prominent, 2nd/3rd = subdued
const PRIORITY_BADGE = [
  "bg-brand-600/30 border-brand-500/40 text-brand-400",
  "bg-slate-700/60 border-slate-600/40 text-slate-300",
  "bg-slate-800/60 border-slate-700/40 text-slate-500",
];

interface PlanViewProps {
  plan: DailyPlan;
}

export function PlanView({ plan }: PlanViewProps) {
  const t = useT();
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl bg-gradient-to-br from-brand-600/15 to-slate-900/80 border border-brand-500/20 p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-mono mb-2">
              {formatDate(plan.plan_date)}
            </p>
            {plan.day_mode && (
              <span className="inline-block text-xs font-semibold uppercase tracking-wide px-2.5 py-1 rounded-md bg-brand-600/20 text-brand-400 border border-brand-500/20">
                {plan.day_mode}
              </span>
            )}
          </div>
          <div className="flex flex-col items-end gap-1.5">
            {plan.review_context_used && (
              <span className="inline-flex items-center gap-1.5 text-xs text-brand-400 bg-brand-600/10 border border-brand-500/20 rounded px-2 py-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-400 shrink-0" />
                {t("plan.based_on_review")}
              </span>
            )}
            {plan.model_used && (
              <span className="text-[10px] text-slate-700 font-mono">{plan.model_used}</span>
            )}
          </div>
        </div>

        {plan.status_summary && (
          <p className="mt-4 text-slate-300 text-sm leading-relaxed border-t border-slate-700/40 pt-4">
            {plan.status_summary}
          </p>
        )}

        {plan.main_win && (
          <div className="mt-4 flex items-start gap-3 rounded-lg bg-amber-950/20 border border-amber-800/20 px-4 py-3">
            <Trophy className="h-4 w-4 text-amber-400/80 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] text-amber-400/70 font-mono uppercase tracking-widest mb-0.5">
                {t("plan.main_win")}
              </p>
              <p className="text-slate-100 font-medium text-sm leading-snug">{plan.main_win}</p>
            </div>
          </div>
        )}
      </div>

      {/* Top 3 Priorities */}
      {plan.top_priorities.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-brand-400" />
              {t("plan.top_priorities")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {plan.top_priorities.map((p, i) => (
              <div key={i} className="flex gap-3">
                <div className={cn(
                  "flex-shrink-0 w-6 h-6 rounded-full border flex items-center justify-center",
                  PRIORITY_BADGE[i] ?? PRIORITY_BADGE[2]
                )}>
                  <span className="text-xs font-bold">{i + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-slate-200 font-medium text-sm">{p.title}</p>
                    {p.life_area && <Badge label={p.life_area} lifeArea={p.life_area} />}
                  </div>
                  {p.description && (
                    <p className="text-slate-400 text-xs mt-0.5 leading-relaxed">{p.description}</p>
                  )}
                  {p.why && (
                    <p className="text-slate-600 text-xs mt-1 italic">→ {p.why}</p>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Time Blocks — Command Timeline */}
      {plan.time_blocks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-brand-400" />
              {t("plan.schedule")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {plan.time_blocks.map((block, i) => (
              <div key={i} className="flex gap-3 group">
                {/* Time column */}
                <div className="w-20 flex-shrink-0 pt-2.5">
                  <p className="text-xs text-slate-500 font-mono leading-none">
                    {block.start_time}
                  </p>
                  <p className="text-[10px] text-slate-700 font-mono mt-0.5">
                    {block.end_time}
                  </p>
                </div>

                {/* Block card with accent strip */}
                <div className="min-w-0 flex-1 flex rounded-lg overflow-hidden border border-slate-700/50 group-hover:border-slate-600/70 transition-colors bg-slate-800/50">
                  <div className={cn(
                    "w-[3px] shrink-0",
                    BLOCK_ACCENT_BG[block.block_type ?? "other"] ?? "bg-slate-500"
                  )} />
                  <div className="flex-1 px-4 py-2.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-slate-200 text-sm font-medium">{block.title}</p>
                      {block.block_type && (
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-medium",
                          BLOCK_TYPE_COLORS[block.block_type] ?? "bg-slate-700 text-slate-300"
                        )}>
                          {t(`block.${block.block_type}`)}
                        </span>
                      )}
                      {block.life_area && (
                        <Badge label={block.life_area} lifeArea={block.life_area} />
                      )}
                    </div>
                    {block.description && (
                      <p className="text-slate-400 text-xs mt-1 leading-relaxed">{block.description}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Energy Strategy */}
      {plan.energy_strategy && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-400/80" />
              {t("plan.energy_strategy")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-slate-300 text-sm leading-relaxed">{plan.energy_strategy}</p>
          </CardContent>
        </Card>
      )}

      {/* Not Today — full width, prominent */}
      {plan.not_today_list.length > 0 && (
        <div className="flex rounded-lg overflow-hidden border border-slate-700/50">
          <div className="w-[3px] shrink-0 bg-slate-600" />
          <div className="flex-1 px-5 py-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              <Ban className="h-3.5 w-3.5 text-slate-500" />
              {t("plan.not_today")}
            </p>
            <ul className="space-y-1.5">
              {plan.not_today_list.map((item, i) => (
                <li key={i} className="text-slate-500 text-sm flex items-start gap-2">
                  <span className="text-slate-700 mt-0.5 shrink-0">×</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Evening Review Questions */}
      {plan.evening_review_questions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-violet-400/80" />
              {t("plan.eve_questions")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2">
              {plan.evening_review_questions.map((q, i) => (
                <li key={i} className="text-slate-300 text-sm flex gap-3">
                  <span className="text-slate-600 font-mono text-xs mt-0.5 shrink-0">{i + 1}.</span>
                  {q}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Closing */}
      {plan.motivational_closing && (
        <div className="text-center py-6 border-t border-slate-800">
          <p className="text-slate-500 text-sm italic">{plan.motivational_closing}</p>
        </div>
      )}
    </div>
  );
}
