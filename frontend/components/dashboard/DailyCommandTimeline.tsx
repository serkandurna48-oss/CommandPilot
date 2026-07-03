"use client";

import { cn, BLOCK_TYPE_COLORS } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import type { DailyPlan } from "@/types";

const BLOCK_DOT_COLOR: Record<string, string> = {
  deep_work: "bg-brand-500",
  admin:     "bg-slate-500",
  sport:     "bg-amber-500/80",
  break:     "bg-slate-600",
  social:    "bg-pink-500/70",
  learning:  "bg-violet-500/70",
  personal:  "bg-indigo-400/70",
  other:     "bg-slate-500",
};

const MAX_BLOCKS = 8;

export function DailyCommandTimeline({ plan }: { plan: DailyPlan | null }) {
  const t = useT();

  if (!plan || !plan.time_blocks.length) return null;

  const blocks = plan.time_blocks.slice(0, MAX_BLOCKS);
  const overflow = plan.time_blocks.length - MAX_BLOCKS;

  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/80 px-5 py-4">
      <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-600 mb-5">
        {t("dashboard.timeline.title")}
      </p>

      {/* Mission log with vertical connecting line */}
      <div className="relative">
        {/* Vertical line behind dots */}
        <div className="absolute left-[3px] top-2 bottom-2 w-px bg-slate-800/80" />

        <div className="space-y-5">
          {blocks.map((block, i) => (
            <div key={i} className="flex items-start gap-4">
              {/* Dot — sits over the vertical line */}
              <div className={cn(
                "relative z-10 w-[7px] h-[7px] rounded-full shrink-0 mt-[5px]",
                "ring-2 ring-slate-950",
                BLOCK_DOT_COLOR[block.block_type ?? "other"] ?? "bg-slate-500"
              )} />

              {/* Entry content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-0.5">
                  <span className="text-[10px] font-mono text-slate-600 shrink-0">
                    {block.start_time}
                  </span>
                  <span
                    className="text-slate-300 text-xs font-medium truncate"
                    title={block.title}
                  >
                    {block.title}
                  </span>
                  {block.block_type && (
                    <span className={cn(
                      "text-[9px] px-1.5 py-0.5 rounded shrink-0",
                      BLOCK_TYPE_COLORS[block.block_type] ?? "bg-slate-700 text-slate-300"
                    )}>
                      {t(`block.${block.block_type}`)}
                    </span>
                  )}
                </div>
                {block.description && (
                  <p
                    className="text-slate-600 text-[10px] line-clamp-2 leading-relaxed"
                    title={block.description}
                  >
                    {block.description}
                  </p>
                )}
              </div>
            </div>
          ))}

          {overflow > 0 && (
            <div className="flex items-center gap-4">
              <div className="w-[7px] h-[7px] rounded-full bg-slate-800 relative z-10 ring-2 ring-slate-950 shrink-0" />
              <p className="text-slate-700 text-[10px] font-mono">+{overflow} more</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
