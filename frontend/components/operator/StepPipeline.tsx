"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import type { WorkOrderStep, WorkOrderStepStatus } from "@/types";
import { cn } from "@/lib/utils";
import { progressPercent } from "@/components/operator/ExecutionPlan";
import { Check, Loader2, AlertTriangle, X, Minus } from "lucide-react";

// Forces a re-render on an interval so the active step's elapsed-time
// readout ticks live without its own per-step timer/state.
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

const NODE_STYLES: Record<WorkOrderStepStatus, { circle: string; icon: JSX.Element | null }> = {
  completed: { circle: "bg-status-success border-status-success text-[var(--bg-app)]", icon: <Check className="h-4 w-4" strokeWidth={3} /> },
  running: { circle: "bg-[var(--bg-app)] border-brand-400 text-brand-400", icon: <Loader2 className="h-4 w-4 motion-safe:animate-spin" /> },
  blocked: { circle: "bg-[var(--bg-app)] border-status-warning text-status-warning", icon: <AlertTriangle className="h-4 w-4" /> },
  failed: { circle: "bg-[var(--bg-app)] border-status-danger text-status-danger", icon: <X className="h-4 w-4" strokeWidth={3} /> },
  skipped: { circle: "bg-[var(--bg-app)] border-[var(--border-default)] text-[var(--text-tertiary)]", icon: <Minus className="h-4 w-4" /> },
  pending: { circle: "bg-[var(--bg-app)] border-[var(--border-light)] text-[var(--text-placeholder)]", icon: null },
  queued: { circle: "bg-[var(--bg-app)] border-[var(--border-default)] text-[var(--text-tertiary)]", icon: null },
};

/**
 * The permanent, always-visible "what is my background team doing" node
 * graph — a connected pipeline of ticketplan steps, not a stacked list.
 * Generalized from the earlier running-only LiveExecutionView: renders
 * every step status (pending/queued/completed/blocked/failed/skipped), not
 * only the running one, so it works as the default view for a work order
 * in ANY state, not just mid-execution. `isLive` (order.status ===
 * "running") toggles the live-only chrome (pulsing glow on the active
 * node, ticking elapsed timer, scanline) — a completed/blocked order still
 * shows the exact same pipeline shape, just without the "something is
 * happening right now" animation.
 *
 * Focus Deck tokens (23.09.2026) — this surface used to deliberately break
 * from the design system ("Mission Control" terminal look); Serkan reversed
 * that decision and asked for it to be unified with the rest of the app.
 * Every value here is real data already in `steps` — progressPercent() is
 * the one canonical calculation, no separate/invented number.
 */
export function StepPipeline({ steps, isLive }: { steps: WorkOrderStep[]; isLive: boolean }) {
  const t = useT();
  useTick(1000);

  if (steps.length === 0) {
    return <p className="text-[var(--text-tertiary)] text-xs font-mono">{t("operator.section.no_steps")}</p>;
  }

  const pct = progressPercent(steps);
  const runningStep = steps.find((s) => s.status === "running");

  return (
    <div className="space-y-5">
      <style>{`
        @keyframes cp-live-pulse-ring {
          0%, 100% { box-shadow: 0 0 0 0 rgba(156, 94, 51, 0.35), 0 0 20px 3px rgba(156, 94, 51, 0.25); }
          50% { box-shadow: 0 0 0 4px rgba(156, 94, 51, 0), 0 0 28px 7px rgba(156, 94, 51, 0.4); }
        }
      `}</style>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isLive && (
            <span className="relative flex h-2 w-2">
              <span className="motion-safe:animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-400" />
            </span>
          )}
          <span className={cn("text-[11px] font-mono uppercase tracking-[0.2em]", isLive ? "text-brand-400" : "text-[var(--text-tertiary)]")}>
            {isLive ? t("operator.live.badge") : t("operator.section.execution_plan")}
          </span>
        </div>
        <span className="text-[var(--text-secondary)] text-xs font-mono tabular-nums">{pct}%</span>
      </div>

      <div className="relative">
        {/* Track: one continuous line behind every node, progress overlay on top —
            avoids per-segment connector math entirely. Positioned to bisect the
            32px (h-8) node circles below (top-4 = 16px = half of 32px). Horizontal
            track only makes sense once the pipeline is actually a horizontal row
            (sm: and up, see the grid below) — a vertical mobile stack has no single
            row to bisect, so the track is hidden below that breakpoint rather than
            drawn across a column of stacked nodes where it wouldn't align to
            anything. */}
        <div className="hidden sm:block absolute top-4 left-4 right-4 h-0.5 bg-[var(--border-default)]" />
        <div
          className="hidden sm:block absolute top-4 left-4 h-0.5 bg-gradient-to-r from-brand-600 to-brand-400 motion-safe:transition-all motion-safe:duration-700"
          style={{ width: steps.length > 1 ? `calc(${pct}% * (100% - 2rem) / 100%)` : 0 }}
        />

        {/*
          Mobile (<sm): one column, nodes stacked vertically — grid-cols-1 is a
          real Tailwind class so it participates normally in the cascade.
          Desktop (sm:+): N equal-width columns via a CSS custom property read
          through an arbitrary-value utility. This is NOT the same as setting
          gridTemplateColumns via the style prop directly — an inline style
          always wins over every class regardless of breakpoint, which would
          force N columns unconditionally and defeat grid-cols-1 on mobile.
          Routing the dynamic value through a --step-cols custom property (set
          via style, read via a class) keeps it subject to normal Tailwind
          media-query cascade instead.
        */}
        <div
          className="relative grid grid-cols-1 gap-4 sm:gap-1 sm:[grid-template-columns:var(--step-cols)]"
          style={{ "--step-cols": `repeat(${steps.length}, minmax(0, 1fr))` } as React.CSSProperties}
        >
          {steps.map((step, i) => {
            const isRunning = isLive && step.id === runningStep?.id;
            const style = NODE_STYLES[step.status];
            return (
              <div key={step.id} className="flex flex-col items-center text-center px-1 sm:px-1">
                <div
                  className={cn("h-8 w-8 rounded-full border-2 flex items-center justify-center font-mono text-xs shrink-0", style.circle)}
                  style={isRunning ? { animation: "cp-live-pulse-ring 2.2s ease-in-out infinite" } : undefined}
                >
                  {style.icon ?? i + 1}
                </div>
                <p className={cn("mt-2 text-xs font-medium line-clamp-2", isRunning ? "text-[var(--text-primary)]" : step.status === "pending" ? "text-[var(--text-placeholder)]" : "text-[var(--text-secondary)]")}>
                  {step.title}
                </p>
                <span className="mt-1 text-[10px] font-mono text-[var(--text-tertiary)] uppercase tracking-wide">{t(`operator.role.${step.assignedRole}`)}</span>
                {isRunning && step.startedAt && (
                  <span className="mt-1 text-[10px] text-brand-400 font-mono tabular-nums">{formatElapsed(step.startedAt)}</span>
                )}
                <span
                  className={cn(
                    "mt-1 text-[9px] px-1.5 py-0.5 rounded uppercase tracking-wider",
                    isRunning
                      ? "bg-brand-500/15 text-brand-400 border border-brand-500/30"
                      : "bg-[var(--bg-elevated)] text-[var(--text-tertiary)] border border-[var(--border-default)]"
                  )}
                >
                  {t(`operator.step_status.${step.status}`)}
                </span>
                {step.blockedReason && (
                  <p className="mt-1.5 text-[10px] text-status-warning line-clamp-3">{step.blockedReason}</p>
                )}
                {!step.blockedReason && step.outputSummary && (
                  <p className="mt-1.5 text-[10px] text-[var(--text-tertiary)] line-clamp-3">{step.outputSummary}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
