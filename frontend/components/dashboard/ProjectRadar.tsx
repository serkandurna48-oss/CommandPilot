"use client";

import Link from "next/link";
import { ArrowRight, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import type { Project, ProjectPriority, ProjectStatus } from "@/types";

const STATUS_CHIP: Partial<Record<ProjectStatus, string>> = {
  active:  "border-green-800/40 text-green-400/70",
  waiting: "border-slate-700 text-slate-500",
};

const PRIORITY_DOT: Record<ProjectPriority, string> = {
  high:   "bg-rose-400/60",
  medium: "bg-slate-500/50",
  low:    "bg-slate-700",
};

const PRIORITY_BORDER: Record<ProjectPriority, string> = {
  high:   "border-l-2 border-l-rose-500/30",
  medium: "border-l-2 border-l-slate-700/60",
  low:    "border-l-2 border-l-slate-800",
};

export function ProjectRadar({
  projects,
  totalCount,
}: {
  projects: Project[];
  totalCount: number;
}) {
  const t = useT();
  const relevant = projects.filter(
    (p) => p.status === "active" || p.status === "waiting"
  );

  if (!relevant.length) return null;

  const overflow = totalCount - relevant.length;

  return (
    <div className="h-full flex flex-col">
      <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-600 mb-3 border-t border-slate-800/80 pt-5">
        {t("dashboard.radar.title")}
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1">
        {relevant.map((p, i) => (
          <div
            key={p.id}
            className={cn(
              "relative rounded-lg border border-slate-800/70 bg-gradient-to-br from-slate-950 to-slate-900/50 pt-6 px-3 pb-3",
              PRIORITY_BORDER[p.priority]
            )}
          >
            {/* TARGET label */}
            <span className="absolute top-2 right-2.5 text-[8px] font-mono text-slate-700 tracking-wider">
              TARGET {String(i + 1).padStart(2, "0")}
            </span>

            <div className="flex items-start gap-2 mb-1.5">
              <div className={cn(
                "w-1.5 h-1.5 rounded-full shrink-0 mt-[5px]",
                PRIORITY_DOT[p.priority]
              )} />
              <p className="text-slate-200 text-xs font-medium leading-snug flex-1 min-w-0" title={p.name}>
                {p.name}
              </p>
              {STATUS_CHIP[p.status] && (
                <span className={cn(
                  "text-[9px] font-mono px-1 py-0.5 rounded border shrink-0",
                  STATUS_CHIP[p.status]
                )}>
                  {p.status}
                </span>
              )}
            </div>
            {p.next_action && (
              <p className="text-slate-500 text-[10px] line-clamp-2 pl-3.5 leading-relaxed" title={p.next_action}>
                → {p.next_action}
              </p>
            )}
            {p.risk && (
              <p className="text-amber-400/50 text-[10px] flex items-center gap-1 pl-3.5 mt-1">
                <AlertTriangle className="h-2.5 w-2.5 shrink-0" />
                <span className="line-clamp-1" title={p.risk}>{p.risk}</span>
              </p>
            )}
          </div>
        ))}
      </div>

      {/* System footer link */}
      {overflow > 0 && (
        <Link
          href="/projects"
          className="mt-3 inline-flex items-center gap-2 text-[9px] font-mono uppercase tracking-widest text-slate-700 hover:text-slate-500 transition-colors group"
        >
          <span>→ {overflow} more active {overflow === 1 ? "system" : "systems"}</span>
          <ArrowRight className="h-2.5 w-2.5 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      )}
    </div>
  );
}
