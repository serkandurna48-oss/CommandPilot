"use client";

import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import type { Project, ProjectPriority } from "@/types";

const PRIORITY_ACCENT: Record<ProjectPriority, string> = {
  high:   "border-l-2 border-rose-500/50",
  medium: "border-l-2 border-brand-500/40",
  low:    "border-l-2 border-slate-700",
};

export function SignalNoisePanel({
  focusProject,
  secondaryProjects,
  noiseItems,
}: {
  focusProject: Project | null;
  secondaryProjects: Project[];
  noiseItems: string[];
}) {
  const t = useT();

  const hasContent = focusProject || secondaryProjects.length > 0 || noiseItems.length > 0;
  if (!hasContent) return null;

  return (
    <div className="h-full rounded-xl border border-slate-800/70 bg-slate-950/60 overflow-hidden flex flex-col">

      {/* Main Signal — full row, dominant */}
      {focusProject && (
        <div className={cn(
          "px-5 py-5 border-b border-slate-800/50",
          PRIORITY_ACCENT[focusProject.priority]
        )}>
          <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-600 mb-3">
            {t("dashboard.signal.main")}
          </p>
          <p className="text-slate-100 text-base font-medium leading-snug mb-1.5">
            {focusProject.name}
          </p>
          {focusProject.next_action && (
            <p className="text-slate-500 text-xs flex items-start gap-1.5 leading-relaxed">
              <span className="text-brand-500/40 shrink-0 mt-px">→</span>
              <span className="line-clamp-2">{focusProject.next_action}</span>
            </p>
          )}
        </div>
      )}

      {/* Secondary Targets — compact rows */}
      {secondaryProjects.length > 0 && (
        <div className="px-5 py-4 border-b border-slate-800/50 flex-1">
          <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-700 mb-3">
            {t("dashboard.signal.secondary")}
          </p>
          <div>
            {secondaryProjects.map((p, i) => (
              <div
                key={p.id}
                className={cn(
                  "py-2.5",
                  i < secondaryProjects.length - 1 && "border-b border-slate-800/40"
                )}
              >
                <p className="text-slate-500 text-xs font-medium leading-snug">{p.name}</p>
                {p.next_action && (
                  <p className="text-slate-700 text-[10px] line-clamp-1 mt-0.5">{p.next_action}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Noise Suppressed — very quiet block */}
      {noiseItems.length > 0 && (
        <div className="px-5 py-4 opacity-40">
          <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-600 mb-2">
            {t("dashboard.signal.noise")}
          </p>
          <div className="space-y-1">
            {noiseItems.slice(0, 4).map((item, i) => (
              <p key={i} className="text-slate-600 text-[10px] flex items-start gap-1.5">
                <span className="text-slate-600 shrink-0">×</span>
                <span className="line-clamp-1" title={item}>{item}</span>
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
