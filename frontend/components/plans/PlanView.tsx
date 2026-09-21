"use client";

import { DailyPlan } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { SurfaceSection } from "@/components/layout/SurfaceSection";
import { cn, BLOCK_TYPE_COLORS, formatDate } from "@/lib/utils";
import { useT } from "@/lib/i18n";

// Left accent strip color per block type (restrained, no neon) — a category
// encoding, not a status color, kept as-is from the prior implementation.
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
  "bg-[var(--bg-elevated)] border-[var(--border-default)] text-[var(--text-secondary)]",
  "bg-[var(--bg-elevated)] border-[var(--border-light)] text-[var(--text-tertiary)]",
];

interface PlanViewProps {
  plan: DailyPlan;
}

export function PlanView({ plan }: PlanViewProps) {
  const t = useT();
  return (
    <div className="space-y-6">
      {/* Hero — the plan's one serif headline moment (Home/Settings
          pattern), reused here for the day's actual Main Win instead of a
          generic greeting. Importance comes from scale/serif/whitespace,
          not a gradient box or a trophy icon (Focus-Deck-Kompositions-Pass). */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-tertiary)] mb-3">
          <span>{formatDate(plan.plan_date)}</span>
          {plan.day_mode && (
            <>
              <span>·</span>
              <span className="text-[var(--text-accent)] uppercase tracking-wide">{plan.day_mode}</span>
            </>
          )}
        </div>

        {plan.main_win ? (
          <h1 className="relative inline-block font-serif text-[28px] md:text-[36px] leading-[1.2] font-semibold text-[var(--text-primary)] pb-2.5">
            {plan.main_win}
            <span className="absolute left-0 bottom-0 h-[2px] w-10 bg-[var(--interactive-bg-primary-default)]" />
          </h1>
        ) : null}

        {plan.status_summary && (
          <p className="text-[var(--text-secondary)] text-sm mt-3 max-w-2xl leading-relaxed">
            {plan.status_summary}
          </p>
        )}

        {plan.review_context_used && (
          <p className="text-xs text-[var(--text-tertiary)] mt-3 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--text-accent)] shrink-0" />
            {t("plan.based_on_review")}
          </p>
        )}
      </div>

      <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]/60 divide-y divide-[var(--border-light)]">
        {plan.top_priorities.length > 0 && (
          <SurfaceSection title={t("plan.top_priorities")}>
            <div className="space-y-4">
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
                      <p className="text-[var(--text-primary)] font-medium text-sm">{p.title}</p>
                      {p.life_area && <Badge label={p.life_area} lifeArea={p.life_area} />}
                    </div>
                    {p.description && (
                      <p className="text-[var(--text-secondary)] text-xs mt-0.5 leading-relaxed">{p.description}</p>
                    )}
                    {p.why && (
                      <p className="text-[var(--text-tertiary)] text-xs mt-1 italic">→ {p.why}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </SurfaceSection>
        )}

        {plan.time_blocks.length > 0 && (
          <SurfaceSection title={t("plan.schedule")}>
            <div className="space-y-2">
              {plan.time_blocks.map((block, i) => (
                <div key={i} className="flex gap-3 group">
                  <div className="w-20 flex-shrink-0 pt-2.5">
                    <p className="text-xs text-[var(--text-tertiary)] font-mono leading-none">
                      {block.start_time}
                    </p>
                    <p className="text-[10px] text-[var(--text-placeholder)] font-mono mt-0.5">
                      {block.end_time}
                    </p>
                  </div>

                  <div className="min-w-0 flex-1 flex rounded-lg overflow-hidden border border-[var(--border-light)] group-hover:border-[var(--border-default)] motion-safe:transition-colors bg-[var(--bg-elevated)]/50">
                    <div className={cn(
                      "w-[3px] shrink-0",
                      BLOCK_ACCENT_BG[block.block_type ?? "other"] ?? "bg-slate-500"
                    )} />
                    <div className="flex-1 px-4 py-2.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-[var(--text-primary)] text-sm font-medium">{block.title}</p>
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
                        <p className="text-[var(--text-secondary)] text-xs mt-1 leading-relaxed">{block.description}</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </SurfaceSection>
        )}

        {plan.energy_strategy && (
          <SurfaceSection title={t("plan.energy_strategy")}>
            <p className="text-[var(--text-secondary)] text-sm leading-relaxed">{plan.energy_strategy}</p>
          </SurfaceSection>
        )}

        {plan.not_today_list.length > 0 && (
          <SurfaceSection title={t("plan.not_today")}>
            <ul className="space-y-1.5">
              {plan.not_today_list.map((item, i) => (
                <li key={i} className="text-[var(--text-tertiary)] text-sm flex items-start gap-2">
                  <span className="text-[var(--text-placeholder)] mt-0.5 shrink-0">×</span>
                  {item}
                </li>
              ))}
            </ul>
          </SurfaceSection>
        )}

        {plan.evening_review_questions.length > 0 && (
          <SurfaceSection title={t("plan.eve_questions")} className="rounded-b-lg">
            <ol className="space-y-2">
              {plan.evening_review_questions.map((q, i) => (
                <li key={i} className="text-[var(--text-secondary)] text-sm flex gap-3">
                  <span className="text-[var(--text-tertiary)] font-mono text-xs mt-0.5 shrink-0">{i + 1}.</span>
                  {q}
                </li>
              ))}
            </ol>
          </SurfaceSection>
        )}
      </div>

      {plan.motivational_closing && (
        <div className="text-center py-6 border-t border-[var(--border-light)]">
          <p className="text-[var(--text-tertiary)] text-sm italic">{plan.motivational_closing}</p>
        </div>
      )}
    </div>
  );
}
