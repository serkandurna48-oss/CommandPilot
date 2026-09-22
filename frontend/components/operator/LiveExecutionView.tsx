"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import type { WorkOrderStep, ActivityLogEntry } from "@/types";
import { cn } from "@/lib/utils";
import { progressPercent } from "@/components/operator/ExecutionPlan";
import { LOG_LEVEL_COLORS } from "@/lib/operatorStyles";
import { Loader2, Terminal } from "lucide-react";

// Forces a re-render on an interval so the elapsed-time readouts below tick
// live without needing their own per-step timers/state.
function useTick(intervalMs: number) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}

function formatElapsed(startedAt: string): string {
  const totalSeconds = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * The "watch your background team work, in real time" view (Work Orders
 * live-execution feature) — swapped in for the calm ExecutionPlan only
 * while a work order's status is 'running' (see WorkOrderDetail.tsx).
 * Deliberately breaks from the Focus Deck system for this one surface —
 * a console/terminal aesthetic, a glowing/pulsing active step, and a
 * streaming activity feed — Serkan's explicit choice for exactly this
 * state, nowhere else in the app. Every value rendered here is real data
 * already in `steps`/`activityLog` (kept fresh by the Realtime subscription
 * in app/(app)/operator/[id]/page.tsx); progressPercent() is the exact same
 * calculation ExecutionPlan uses elsewhere, not a separate/invented number.
 */
export function LiveExecutionView({ steps, activityLog }: { steps: WorkOrderStep[]; activityLog: ActivityLogEntry[] }) {
  const t = useT();
  useTick(1000);

  if (steps.length === 0) {
    return <p className="text-slate-500 text-xs">{t("operator.section.no_steps")}</p>;
  }

  const pct = progressPercent(steps);
  const runningStep = steps.find((s) => s.status === "running");
  const recentLog = [...activityLog].slice(-12).reverse();

  return (
    <div className="space-y-4">
      <style>{`
        @keyframes cp-live-pulse-ring {
          0%, 100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.3), 0 0 22px 2px rgba(52, 211, 153, 0.22); }
          50% { box-shadow: 0 0 0 5px rgba(52, 211, 153, 0), 0 0 30px 6px rgba(52, 211, 153, 0.38); }
        }
        @keyframes cp-live-scanline {
          0% { transform: translateX(-120%); }
          100% { transform: translateX(220%); }
        }
      `}</style>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="motion-safe:animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
          </span>
          <span className="text-emerald-400 text-[11px] font-mono uppercase tracking-[0.2em]">{t("operator.live.badge")}</span>
        </div>
        <span className="text-emerald-300/80 text-xs font-mono tabular-nums">{pct}%</span>
      </div>

      <div className="h-1.5 rounded-full bg-black/40 overflow-hidden border border-emerald-900/40">
        <div
          className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 motion-safe:transition-all motion-safe:duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="space-y-2">
        {steps.map((step, i) => {
          const isRunning = step.id === runningStep?.id;
          return (
            <div
              key={step.id}
              className={cn(
                "relative overflow-hidden flex gap-3 items-start rounded-lg px-3 py-2.5 border font-mono",
                isRunning ? "border-emerald-500/50 bg-black/50" : "border-slate-800 bg-black/20"
              )}
              style={isRunning ? { animation: "cp-live-pulse-ring 2.2s ease-in-out infinite" } : undefined}
            >
              {isRunning && (
                <div
                  className="pointer-events-none absolute inset-y-0 left-0 w-1/4 bg-gradient-to-r from-transparent via-emerald-400/10 to-transparent motion-safe:animate-none"
                  style={{ animation: "cp-live-scanline 2.6s linear infinite" }}
                />
              )}
              <span className={cn("text-xs shrink-0 mt-0.5", isRunning ? "text-emerald-400" : "text-slate-600")}>
                {isRunning ? <Loader2 className="h-3.5 w-3.5 motion-safe:animate-spin" /> : i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <p className={cn("text-sm font-medium", isRunning ? "text-emerald-100" : "text-slate-300")}>{step.title}</p>
                  <span
                    className={cn(
                      "text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider",
                      isRunning
                        ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                        : "bg-slate-800 text-slate-500 border border-slate-700"
                    )}
                  >
                    {t(`operator.step_status.${step.status}`)}
                  </span>
                  {isRunning && step.startedAt && (
                    <span className="text-[10px] text-emerald-400/80 tabular-nums">{formatElapsed(step.startedAt)}</span>
                  )}
                </div>
                {step.outputSummary && <p className="text-slate-500 text-xs">{step.outputSummary}</p>}
                {step.blockedReason && <p className="text-amber-400/80 text-xs">{step.blockedReason}</p>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="rounded-lg border border-emerald-900/40 bg-black/60 overflow-hidden">
        <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-emerald-900/40 text-emerald-400/70 text-[10px] font-mono uppercase tracking-widest">
          <Terminal className="h-3 w-3" /> {t("operator.live.stream_title")}
        </div>
        <div className="px-3 py-2 max-h-56 overflow-y-auto space-y-1">
          {recentLog.length === 0 ? (
            <p className="text-slate-600 text-xs font-mono">{t("operator.section.no_activity")}</p>
          ) : (
            recentLog.map((entry) => (
              <div key={entry.id} className="text-xs font-mono flex items-start gap-2">
                <span className="text-slate-600 shrink-0">{new Date(entry.createdAt).toLocaleTimeString()}</span>
                <span className={cn("shrink-0 uppercase", LOG_LEVEL_COLORS[entry.level])}>{t(`operator.log.${entry.level}`)}</span>
                <span className="text-emerald-200/70">{entry.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
