import { useT } from "@/lib/i18n";
import type { WorkOrderStep, WorkOrderStepStatus } from "@/types";
import { cn } from "@/lib/utils";
import { ShieldAlert } from "lucide-react";

const STEP_STATUS_COLORS: Record<WorkOrderStepStatus, string> = {
  pending:   "bg-slate-800 border border-slate-700 text-slate-500",
  queued:    "bg-slate-800 border border-slate-600 text-slate-300",
  running:   "bg-slate-800 border border-brand-700/40 text-brand-400/80",
  blocked:   "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  completed: "bg-slate-800 border border-green-800/40 text-green-400/80",
  failed:    "bg-slate-800 border border-rose-800/40 text-rose-400/80",
  skipped:   "bg-slate-800 border border-slate-800 text-slate-600",
};

export function progressPercent(steps: WorkOrderStep[]): number {
  if (steps.length === 0) return 0;
  const done = steps.filter((s) => s.status === "completed" || s.status === "skipped").length;
  return Math.round((done / steps.length) * 100);
}

/**
 * The central "what is my background team doing right now" view: an
 * ordered ticket plan with per-step status, the currently running step
 * highlighted, and blocked steps called out with their reason.
 */
export function ExecutionPlan({ steps }: { steps: WorkOrderStep[] }) {
  const t = useT();

  if (steps.length === 0) {
    return <p className="text-slate-500 text-xs">{t("operator.section.no_steps")}</p>;
  }

  const pct = progressPercent(steps);
  const runningStepId = steps.find((s) => s.status === "running")?.id;

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
          <span>{t("operator.section.progress")}</span>
          <span className="font-mono">{pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div className="h-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="space-y-2">
        {steps.map((step, i) => (
          <div
            key={step.id}
            className={cn(
              "flex gap-3 items-start rounded-lg px-3 py-2 border",
              step.id === runningStepId ? "border-brand-600/60 bg-brand-950/10" : "border-slate-700/50"
            )}
          >
            <span className="text-slate-600 text-xs font-mono shrink-0 mt-0.5">{i + 1}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <p className="text-slate-200 text-sm font-medium">{step.title}</p>
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono", STEP_STATUS_COLORS[step.status])}>
                  {t(`operator.step_status.${step.status}`)}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">{t(`operator.role.${step.assignedRole}`)}</span>
              </div>

              {step.description && <p className="text-slate-400 text-xs mb-1">{step.description}</p>}

              {step.acceptanceCriteria.length > 0 && (
                <ul className="space-y-0.5 mb-1">
                  {step.acceptanceCriteria.map((c, ci) => (
                    <li key={ci} className="text-slate-500 text-[11px] flex items-start gap-1">
                      <span className="shrink-0">☐</span>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              )}

              {step.outputSummary && (
                <p className="text-slate-400 text-xs flex items-start gap-1.5">
                  <span className="text-brand-500/60 shrink-0">→</span>
                  <span>{step.outputSummary}</span>
                </p>
              )}

              {step.blockedReason && (
                <p className="text-amber-300/80 text-xs flex items-start gap-1.5 mt-1 bg-amber-950/20 border border-amber-900/30 rounded px-2 py-1">
                  <ShieldAlert className="h-3 w-3 shrink-0 mt-0.5" />
                  <span>{step.blockedReason}</span>
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
