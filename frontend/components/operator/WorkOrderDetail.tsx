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
import { Clock, ShieldCheck, ShieldAlert, ShieldX, FolderTree, Info, AlertTriangle, RotateCcw, XOctagon } from "lucide-react";

// CP-OP02's harness-side reason codes for why work_orders.status was set to
// 'failed' by the auto-retry loop (scripts/run_work_order.py) — these are
// the values transition_work_order() stores in the status_transition
// activity log's metadata.reason. Anything not in this map (e.g. a human
// didn't give a reason, or a future code this UI doesn't know yet) falls
// back to a generic message rather than showing a raw machine code.
const KNOWN_FAILURE_REASON_KEYS: Record<string, string> = {
  technical_failure_with_worktree_changes: "operator.failure_reason.technical_failure_with_worktree_changes",
  technical_failure_retries_exhausted: "operator.failure_reason.technical_failure_retries_exhausted",
  technical_failure_budget_exhausted: "operator.failure_reason.technical_failure_budget_exhausted",
};

// retryReason on an AgentRun (CP-OP02) is a short code, either
// "technical_failure_attempt_{N}" (set by the harness's own retry loop) or
// undefined (attempt 1, or a run not created by the retry loop at all).
// This never needs a fallback-to-generic path the way work-order failure
// reasons do, because the harness is the only writer of this field.
function attemptFailureLabel(retryReason: string | undefined, t: (key: string) => string): string | null {
  if (!retryReason) return null;
  const match = /^technical_failure_attempt_(\d+)$/.exec(retryReason);
  if (!match) return retryReason;
  return `${t("operator.agent_run.retry_reason_prefix")} ${match[1]}`;
}

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

  // The most recent transition_work_order() (CP-OP01) audit-log entry that
  // landed the work order on its CURRENT status, if any — used below only
  // to explain a 'failed' status. Every transition writes exactly one
  // status_transition entry (see supabase/migrations/010_..._function.sql),
  // so scanning newest-first and taking the first match with
  // metadata.to_status === order.status is always the transition that
  // actually produced the status we're looking at, not some earlier one.
  const latestTransitionToCurrentStatus = order.status === "failed"
    ? [...log].reverse().find(
        (entry) => entry.eventType === "status_transition" && entry.metadata?.to_status === order.status
      )
    : undefined;
  const failureReasonCode = latestTransitionToCurrentStatus?.metadata?.reason;
  const failureReasonKey = failureReasonCode && typeof failureReasonCode === "string"
    ? KNOWN_FAILURE_REASON_KEYS[failureReasonCode]
    : undefined;

  return (
    <div className="space-y-4">
      {/* ── Data source banner — mirrors OperatorManager's list-page banner
          so /operator and /operator/[id] never let API failures look like
          real data (OP-UX-001) ──────────────────────────────────────────── */}
      <div className="text-[11px] font-mono text-amber-400/70 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2">
        {isLive ? t("operator.live_banner") : t("operator.mock_banner")}
      </div>

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

      {/* ── Failed banner — makes "retries exhausted"/other harness-driven
          failures immediately visible instead of only a status badge
          (CP-OP04) ───────────────────────────────────────────────────────── */}
      {order.status === "failed" && (
        <div className="rounded-lg bg-rose-950/20 border border-rose-900/30 px-3 py-2 flex items-start gap-2">
          <XOctagon className="h-4 w-4 shrink-0 mt-0.5 text-rose-400/80" />
          <div className="text-xs">
            <p className="text-rose-300/90 font-medium">{t("operator.failure_banner.title")}</p>
            <p className="text-rose-300/70 mt-0.5">
              {failureReasonKey ? t(failureReasonKey) : t("operator.failure_reason.generic")}
            </p>
          </div>
        </div>
      )}

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
            {runs.map((run) => {
              // Attempt 1 is the normal case (a human-triggered run, or the
              // first attempt of an auto-executed one) — attemptNumber > 1
              // only ever comes from CP-OP02's harness retry loop. Indenting
              // retries and connecting them with a small icon is what makes
              // "these attempts belong to the same run sequence" visible
              // without introducing any new grouping data structure — the
              // existing attemptNumber ordering already carries that
              // information, this just renders it.
              const isRetry = (run.attemptNumber ?? 1) > 1;
              const retryLabel = attemptFailureLabel(run.retryReason, t);
              return (
                <div key={run.id} className={cn("flex items-start gap-3 py-1.5", isRetry && "ml-4 pl-3 border-l border-slate-700/50")}>
                  {isRetry && <RotateCcw className="h-3.5 w-3.5 text-amber-500/70 shrink-0 mt-0.5" />}
                  <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0", AGENT_RUN_STATUS_COLORS[run.status])}>
                    {t(`operator.run_status.${run.status}`)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-slate-200 text-xs font-medium">{t(`operator.role.${run.role}`)}</p>
                      {/* run.model doubles as "which runner, which mode" (e.g. "claude_code
                          (prompt-file)") — no dedicated column for either exists yet, see
                          OP-Runner-Session-001's reviewPackage.risks. */}
                      {run.model && <span className="text-[10px] font-mono text-slate-500">{run.model}</span>}
                      <span className="text-[10px] font-mono text-slate-600">
                        {t("operator.agent_run.attempt_label")} {run.attemptNumber ?? 1}
                      </span>
                      {run.startedAt && (
                        <span className="text-[10px] font-mono text-slate-600">{new Date(run.startedAt).toLocaleString()}</span>
                      )}
                    </div>
                    <p className="text-slate-400 text-xs">{run.inputSummary}</p>
                    {run.outputSummary && <p className="text-slate-500 text-xs mt-0.5">→ {run.outputSummary}</p>}
                    {retryLabel && (
                      <p className="text-amber-500/70 text-[11px] mt-0.5 flex items-center gap-1">
                        <RotateCcw className="h-3 w-3 shrink-0" /> {retryLabel}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
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
      <LocalRunnerPanel order={order} agentRuns={runs} reviewPackage={reviewPackage} />

      {/* ── Generate Runner Prompt (manual fallback) ─────────────────────── */}
      {scope && <RunnerPromptPanel order={order} scope={scope} steps={steps} />}

      {/* ── Safety rules (always visible, order-independent) ─────────────── */}
      <SafetyRulesPanel />
    </div>
  );
}
