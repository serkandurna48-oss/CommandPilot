"use client";

import { DailyPlan } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn, BLOCK_TYPE_COLORS, formatDate } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { Target, Zap, Ban, HelpCircle, Trophy, Clock } from "lucide-react";

interface PlanViewProps {
  plan: DailyPlan;
}

export function PlanView({ plan }: PlanViewProps) {
  const t = useT();
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl bg-gradient-to-br from-brand-600/20 to-slate-800/60 border border-brand-500/20 p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-widest mb-1">
              {formatDate(plan.plan_date)}
            </p>
            <p className="text-brand-400 text-sm font-semibold uppercase tracking-wide">
              {plan.day_mode ?? "—"}
            </p>
          </div>
            <div className="flex flex-col items-end gap-1.5">
            {plan.review_context_used && (
              <span className="inline-flex items-center gap-1.5 text-xs text-brand-400 bg-brand-600/10 border border-brand-500/20 rounded px-2 py-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-400 shrink-0" />
                {t("plan.based_on_review")}
              </span>
            )}
            {plan.model_used && (
              <span className="text-xs text-slate-600 font-mono">{plan.model_used}</span>
            )}
          </div>
        </div>

        {plan.status_summary && (
          <p className="mt-3 text-slate-300 text-sm leading-relaxed">{plan.status_summary}</p>
        )}

        {plan.main_win && (
          <div className="mt-4 flex items-start gap-2">
            <Trophy className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-amber-400 font-medium uppercase tracking-wide mb-0.5">{t("plan.main_win")}</p>
              <p className="text-slate-100 font-medium">{plan.main_win}</p>
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
          <CardContent className="space-y-3">
            {plan.top_priorities.map((p, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-600/20 border border-brand-500/30 flex items-center justify-center">
                  <span className="text-brand-400 text-xs font-bold">{i + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-slate-200 font-medium text-sm">{p.title}</p>
                    {p.life_area && <Badge label={p.life_area} lifeArea={p.life_area} />}
                  </div>
                  {p.description && (
                    <p className="text-slate-400 text-xs mt-0.5">{p.description}</p>
                  )}
                  {p.why && (
                    <p className="text-slate-500 text-xs mt-0.5 italic">→ {p.why}</p>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Time Blocks */}
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
                <div className="w-24 flex-shrink-0 pt-0.5">
                  <p className="text-xs text-slate-500 font-mono">
                    {block.start_time}
                  </p>
                  <p className="text-xs text-slate-600 font-mono">
                    {block.end_time}
                  </p>
                </div>

                {/* Block */}
                <div className="flex-1 rounded-lg bg-slate-800/50 border border-slate-700/50 px-4 py-3 group-hover:border-slate-600 transition-colors">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-slate-200 text-sm font-medium">{block.title}</p>
                    {block.block_type && (
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          BLOCK_TYPE_COLORS[block.block_type] ?? "bg-slate-700 text-slate-300"
                        )}
                      >
                          {t(`block.${block.block_type}`)}
                      </span>
                    )}
                    {block.life_area && (
                      <Badge label={block.life_area} lifeArea={block.life_area} />
                    )}
                  </div>
                  {block.description && (
                    <p className="text-slate-400 text-xs mt-1">{block.description}</p>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Bottom row: Energy + Not Today */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {plan.energy_strategy && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" />
                {t("plan.energy_strategy")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-slate-300 text-sm leading-relaxed">{plan.energy_strategy}</p>
            </CardContent>
          </Card>
        )}

        {plan.not_today_list.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Ban className="h-4 w-4 text-red-400" />
                {t("plan.not_today")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1.5">
                {plan.not_today_list.map((item, i) => (
                  <li key={i} className="text-slate-400 text-sm flex items-start gap-2">
                    <span className="text-red-500 mt-0.5">×</span>
                    {item}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Evening Review Questions */}
      {plan.evening_review_questions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-violet-400" />
              {t("plan.eve_questions")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2">
              {plan.evening_review_questions.map((q, i) => (
                <li key={i} className="text-slate-300 text-sm flex gap-3">
                  <span className="text-slate-600 font-mono text-xs mt-0.5">{i + 1}.</span>
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
          <p className="text-slate-400 text-sm italic">{plan.motivational_closing}</p>
        </div>
      )}
    </div>
  );
}
