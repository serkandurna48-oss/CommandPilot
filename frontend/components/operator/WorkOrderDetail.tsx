import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { StatusFlowStrip } from "@/components/operator/StatusFlowStrip";
import { ExecutionPlan } from "@/components/operator/ExecutionPlan";
import { LifecycleControls } from "@/components/operator/LifecycleControls";
import { RunnerPromptPanel } from "@/components/operator/RunnerPromptPanel";
import { LocalRunnerPanel } from "@/components/operator/LocalRunnerPanel";
import { SafetyRulesPanel } from "@/components/operator/SafetyRulesPanel";
import { useT } from "@/lib/i18n";
import {
  WORK_ORDER_STATUS_COLORS,
  AGENT_RUN_STATUS_COLORS,
  LOG_LEVEL_COLORS,
  VERDICT_COLORS,
} from "@/lib/operatorStyles";
import type { WorkOrderDetailBundle } from "@/lib/workOrderMapper";
import type { WorkOrderStatus } from "@/types";
import { cn } from "@/lib/utils";
import { Clock, ShieldCheck, ShieldAlert, ShieldX, FolderTree, Info, AlertTriangle } from "lucide-react";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

interface WorkOrderDetailProps extends WorkOrderDetailBundle {
  isLive?: boolean;
  onStatusChange?: (status: WorkOrderStatus) => Promise<void> | void;
}

/**
 * Renders one work order's full command-center view. Takes an already
 * data-source-agnostic bundle — the caller (app/operator/[id]/page.tsx)
 * decides whether that bundle came from the real API or the mock fallback,
 * so this component doesn't need to know or care. `isLive`/`onStatusChange`
 * are optional so this component still renders standalone (e.g. future
 * previews/tests) without lifecycle controls wired up.
 */
export function WorkOrderDetail({
  order,
  approvalScope: scope,
  steps,
  agentRuns: runs,
  activityLog: log,
  artifacts,
  reviewPackage,
  isLive = false,
  onStatusChange,
}: WorkOrderDetailProps) {
  const t = useT();

  return (
    <div className="space-y-4">
      {/* ── Header: goal, status, timing ─────────────────────────────────── */}
      <Card variant="elevated">
        <CardContent className="space-y-3 pt-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <p className="text-slate-200 text-base font-semibold mb-1">{order.title}</p>
              <p className="text-slate-400 text-sm">{order.goal}</p>
            </div>
            <span className={cn("text-xs px-2 py-1 rounded font-mono shrink-0", WORK_ORDER_STATUS_COLORS[order.status])}>
              {t(`operator.status.${order.status}`)}
            </span>
          </div>

          <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <FolderTree className="h-3.5 w-3.5" /> {order.repo}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" /> {order.timeLimitMinutes} {t("operator.section.minutes")}
            </span>
            <span>{t("operator.section.created_by")}: {order.createdBy}</span>
          </div>

          <StatusFlowStrip current={order.status} />
        </CardContent>
      </Card>

      {/* ── Lifecycle controls ────────────────────────────────────────────── */}
      {onStatusChange && (
        <LifecycleControls status={order.status} isLive={isLive} onStatusChange={onStatusChange} />
      )}

      {/* ── Execution Plan — the central "what is my team doing" view ────── */}
      <Section title={t("operator.section.execution_plan")}>
        <ExecutionPlan steps={steps} />
      </Section>

      {/* ── Acceptance criteria ──────────────────────────────────────────── */}
      <Section title={t("operator.section.acceptance_criteria")}>
        <ul className="space-y-1">
          {order.acceptanceCriteria.map((c, i) => (
            <li key={i} className="text-slate-300 text-sm flex items-start gap-2">
              <span className="text-slate-600 shrink-0 mt-0.5">☐</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>

        {order.missingContext && order.missingContext.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700/50">
            <p className="text-[10px] font-mono uppercase tracking-wider text-amber-500/70 mb-1.5">
              {t("operator.missing_context")}
            </p>
            <ul className="space-y-0.5">
              {order.missingContext.map((m, i) => (
                <li key={i} className="text-slate-400 text-xs flex items-center gap-1.5">
                  <span className="text-amber-500/60 shrink-0">?</span>
                  <span>{m.label}</span>
                  <span className="text-[10px] text-slate-600">
                    ({m.required ? t("operator.required") : t("operator.optional")})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      {/* ── Approval scope ───────────────────────────────────────────────── */}
      {!scope && (
        <div className="text-xs text-amber-300/90 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{t("operator.section.no_scope_warning")}</span>
        </div>
      )}
      {scope && (
        <Section title={t("operator.section.approval_scope")}>
          {scope.blockedActions.length === 0 && (
            <div className="text-xs text-amber-300/90 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2 mb-3 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{t("operator.section.no_blocked_actions_warning")}</span>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-wider text-green-500/70 mb-1.5 flex items-center gap-1">
                <ShieldCheck className="h-3 w-3" /> {t("operator.section.allowed_actions")}
              </p>
              <ul className="space-y-0.5">
                {scope.allowedActions.map((a, i) => (
                  <li key={i} className="text-slate-300 text-xs">{a}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-wider text-amber-500/70 mb-1.5 flex items-center gap-1">
                <ShieldAlert className="h-3 w-3" /> {t("operator.section.requires_approval")}
              </p>
              <ul className="space-y-0.5">
                {scope.requiresApproval.map((a, i) => (
                  <li key={i} className="text-slate-300 text-xs">{a}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-wider text-rose-500/70 mb-1.5 flex items-center gap-1">
                <ShieldX className="h-3 w-3" /> {t("operator.section.blocked_actions")}
              </p>
              <ul className="space-y-0.5">
                {scope.blockedActions.map((a, i) => (
                  <li key={i} className="text-slate-300 text-xs">{a}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500 pt-2 border-t border-slate-700/50">
            {scope.allowedPaths?.length ? (
              <span>{t("operator.section.allowed_paths")}: {scope.allowedPaths.join(", ")}</span>
            ) : null}
            {scope.blockedPaths?.length ? (
              <span>{t("operator.section.blocked_paths")}: {scope.blockedPaths.join(", ")}</span>
            ) : null}
            <span>{t("operator.section.time_limit")}: {scope.maxRuntimeMinutes} {t("operator.section.minutes")}</span>
            {scope.maxCostUsd != null && (
              <span>{t("operator.section.max_cost")}: ${scope.maxCostUsd}</span>
            )}
          </div>
        </Section>
      )}

      {/* ── Agent runs ───────────────────────────────────────────────────── */}
      <Section title={t("operator.section.agent_runs")}>
        {runs.length === 0 ? (
          <p className="text-slate-500 text-xs">{t("operator.section.no_runs")}</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <div key={run.id} className="flex items-start gap-3 py-1.5">
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0", AGENT_RUN_STATUS_COLORS[run.status])}>
                  {t(`operator.run_status.${run.status}`)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-slate-200 text-xs font-medium">{t(`operator.role.${run.role}`)}</p>
                  <p className="text-slate-400 text-xs">{run.inputSummary}</p>
                  {run.outputSummary && <p className="text-slate-500 text-xs mt-0.5">→ {run.outputSummary}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── Activity log ─────────────────────────────────────────────────── */}
      <Section title={t("operator.section.activity_log")}>
        {log.length === 0 ? (
          <p className="text-slate-500 text-xs">{t("operator.section.no_activity")}</p>
        ) : (
          <ul className="space-y-1.5 font-mono">
            {log.map((entry) => (
              <li key={entry.id} className="text-xs flex items-start gap-2">
                <span className="text-slate-600 shrink-0">{new Date(entry.createdAt).toLocaleString()}</span>
                <span className={cn("shrink-0 uppercase", LOG_LEVEL_COLORS[entry.level])}>
                  {t(`operator.log.${entry.level}`)}
                </span>
                <span className="text-slate-400">{entry.message}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* ── Artifacts ────────────────────────────────────────────────────── */}
      <Section title={t("operator.section.artifacts")}>
        {artifacts.length === 0 ? (
          <p className="text-slate-500 text-xs">{t("operator.section.no_artifacts")}</p>
        ) : (
          <div className="space-y-3">
            {artifacts.map((artifact) => (
              <div key={artifact.id} className="border border-slate-700/50 rounded-lg px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-slate-800 border border-slate-700 text-slate-400">
                    {t(`operator.artifact.${artifact.type}`)}
                  </span>
                  <p className="text-slate-200 text-xs font-medium">{artifact.title}</p>
                </div>
                {artifact.content && (
                  <pre className="text-slate-400 text-xs whitespace-pre-wrap font-mono">{artifact.content}</pre>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── Review package ───────────────────────────────────────────────── */}
      <Section title={t("operator.section.review_package")}>
        {!reviewPackage ? (
          <p className="text-slate-500 text-xs flex items-center gap-1.5">
            <Info className="h-3.5 w-3.5 shrink-0" /> {t("operator.section.no_review_package")}
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono", VERDICT_COLORS[reviewPackage.verdict])}>
                {t(`operator.verdict.${reviewPackage.verdict}`)}
              </span>
              {reviewPackage.needsHumanReview && (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-amber-950/30 border border-amber-900/40 text-amber-400/80">
                  {t("operator.section.needs_human_review")}
                </span>
              )}
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">{t("operator.section.summary")}</p>
              <p className="text-slate-300 text-xs">{reviewPackage.summary}</p>
            </div>
            {reviewPackage.filesChanged.length > 0 && (
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">{t("operator.section.files_changed")}</p>
                <ul className="space-y-0.5 font-mono">
                  {reviewPackage.filesChanged.map((f, i) => (
                    <li key={i} className="text-slate-400 text-xs">{f}</li>
                  ))}
                </ul>
              </div>
            )}
            {reviewPackage.testsRun.length > 0 && (
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">{t("operator.section.tests_run")}</p>
                <p className="text-slate-400 text-xs">{reviewPackage.testsRun.join(", ")}</p>
              </div>
            )}
            {reviewPackage.risks.length > 0 && (
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-amber-500/70 mb-1">{t("operator.section.risks")}</p>
                <ul className="space-y-0.5">
                  {reviewPackage.risks.map((r, i) => (
                    <li key={i} className="text-amber-300/80 text-xs">{r}</li>
                  ))}
                </ul>
              </div>
            )}
            {reviewPackage.openQuestions.length > 0 && (
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">{t("operator.section.open_questions")}</p>
                <ul className="space-y-0.5">
                  {reviewPackage.openQuestions.map((q, i) => (
                    <li key={i} className="text-slate-400 text-xs">{q}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Section>

      {/* ── Recommended next step ────────────────────────────────────────── */}
      {order.recommendedNextStep && (
        <Section title={t("operator.section.recommended_next_step")}>
          <p className="text-slate-300 text-sm flex items-start gap-2">
            <span className="text-brand-500/60 shrink-0">→</span>
            <span>{order.recommendedNextStep}</span>
          </p>
        </Section>
      )}

      {/* ── Local Runner (recommended path) ──────────────────────────────── */}
      <LocalRunnerPanel order={order} />

      {/* ── Generate Runner Prompt (manual fallback) ─────────────────────── */}
      {scope && <RunnerPromptPanel order={order} scope={scope} steps={steps} />}

      {/* ── Safety rules (always visible, order-independent) ─────────────── */}
      <SafetyRulesPanel />
    </div>
  );
}
