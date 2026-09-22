import { ExecutionPlan } from "@/components/operator/ExecutionPlan";
import { LiveExecutionView } from "@/components/operator/LiveExecutionView";
import { LifecycleControls } from "@/components/operator/LifecycleControls";
import { RunnerPromptPanel } from "@/components/operator/RunnerPromptPanel";
import { LocalRunnerPanel } from "@/components/operator/LocalRunnerPanel";
import { SafetyRulesPanel } from "@/components/operator/SafetyRulesPanel";
import { SurfaceSection } from "@/components/layout/SurfaceSection";
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
import { Clock, ShieldCheck, ShieldAlert, ShieldX, FolderTree, Info, RotateCcw, XOctagon } from "lucide-react";

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
 *
 * Structured as one divided surface (Focus-Deck-Kompositions-Pass), not a
 * stack of independently bordered cards — human-relevant content (goal,
 * status, what to do next, the review verdict) comes first; the technical
 * record (execution plan, agent runs, activity log) follows behind a single
 * "Technical details" divider. Nothing here is hidden — see LifecycleControls,
 * ExecutionPlan, etc. below the divider for the full audit trail.
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
      <div className="text-[11px] font-mono text-status-warning/80 bg-status-warning/10 border border-status-warning/30 rounded-lg px-3 py-2">
        {isLive ? t("operator.live_banner") : t("operator.mock_banner")}
      </div>

      <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]/60 divide-y divide-[var(--border-light)]">
        {/* ── Human tier: what is this, what's its state, what do I do ────── */}
        <div className="px-5 py-5">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <p className="text-[var(--text-primary)] text-base font-semibold mb-1">{order.title}</p>
              <p className="text-[var(--text-secondary)] text-sm">{order.goal}</p>
            </div>
            <span className={cn("text-xs px-2 py-1 rounded font-mono shrink-0", WORK_ORDER_STATUS_COLORS[order.status])}>
              {t(`operator.status.${order.status}`)}
            </span>
          </div>

          <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-[var(--text-tertiary)] mt-3">
            <span className="flex items-center gap-1.5">
              <FolderTree className="h-3.5 w-3.5" /> {order.repo}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" /> {order.timeLimitMinutes} {t("operator.section.minutes")}
            </span>
            <span>{t("operator.section.created_by")}: {order.createdBy}</span>
          </div>

          {order.status === "failed" && (
            <div className="mt-4 rounded-lg bg-status-danger/10 border border-status-danger/30 px-3 py-2 flex items-start gap-2">
              <XOctagon className="h-4 w-4 shrink-0 mt-0.5 text-status-danger" />
              <div className="text-xs">
                <p className="text-status-danger font-medium">{t("operator.failure_banner.title")}</p>
                <p className="text-status-danger/80 mt-0.5">
                  {failureReasonKey ? t(failureReasonKey) : t("operator.failure_reason.generic")}
                </p>
              </div>
            </div>
          )}

          {order.recommendedNextStep && (
            <p className="text-[var(--text-primary)] text-sm flex items-start gap-2 mt-4">
              <span className="text-[var(--text-accent)] shrink-0">→</span>
              <span>{order.recommendedNextStep}</span>
            </p>
          )}

          {onStatusChange && (
            <div className="mt-4">
              <LifecycleControls status={order.status} isLive={isLive} onStatusChange={onStatusChange} />
            </div>
          )}
        </div>

        {/* ── Review package — the verdict a human is here to act on ──────── */}
        {reviewPackage && (
          <SurfaceSection title={t("operator.section.review_package")}>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono", VERDICT_COLORS[reviewPackage.verdict])}>
                  {t(`operator.verdict.${reviewPackage.verdict}`)}
                </span>
                {reviewPackage.needsHumanReview && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-status-warning/10 border border-status-warning/30 text-status-warning/90">
                    {t("operator.section.needs_human_review")}
                  </span>
                )}
              </div>
              <p className="text-[var(--text-secondary)] text-sm">{reviewPackage.summary}</p>

              {reviewPackage.risks.length > 0 && (
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-wider text-status-warning/80 mb-1">{t("operator.section.risks")}</p>
                  <ul className="space-y-0.5">
                    {reviewPackage.risks.map((r, i) => (
                      <li key={i} className="text-status-warning/90 text-xs">{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {reviewPackage.openQuestions.length > 0 && (
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-tertiary)] mb-1">{t("operator.section.open_questions")}</p>
                  <ul className="space-y-0.5">
                    {reviewPackage.openQuestions.map((q, i) => (
                      <li key={i} className="text-[var(--text-secondary)] text-xs">{q}</li>
                    ))}
                  </ul>
                </div>
              )}

              <details className="group pt-1">
                <summary className="text-xs text-[var(--text-tertiary)] cursor-pointer hover:text-[var(--text-secondary)] motion-safe:transition-colors list-none flex items-center gap-1.5">
                  <span className="group-open:rotate-90 motion-safe:transition-transform text-[10px]">▸</span>
                  {t("operator.section.files_changed")} · {t("operator.section.tests_run")}
                </summary>
                <div className="mt-2 space-y-3 pl-4">
                  {reviewPackage.filesChanged.length > 0 && (
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-tertiary)] mb-1">{t("operator.section.files_changed")}</p>
                      <ul className="space-y-0.5 font-mono">
                        {reviewPackage.filesChanged.map((f, i) => (
                          <li key={i} className="text-[var(--text-secondary)] text-xs">{f}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {reviewPackage.testsRun.length > 0 && (
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-tertiary)] mb-1">{t("operator.section.tests_run")}</p>
                      <p className="text-[var(--text-secondary)] text-xs">{reviewPackage.testsRun.join(", ")}</p>
                    </div>
                  )}
                </div>
              </details>
            </div>
          </SurfaceSection>
        )}

        {/* ── Technical details — the full audit trail, collapsed by default
            composition (not hidden — a divider, not a toggle, since this is
            exactly the auditability the brief says must never be hidden) ── */}
        <div className="px-5 pt-4 pb-1">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-tertiary)]">
            {t("operator.section.technical_details")}
          </p>
        </div>

        <SurfaceSection title={t("operator.section.execution_plan")}>
          {order.status === "running" ? (
            <LiveExecutionView steps={steps} activityLog={log} />
          ) : (
            <ExecutionPlan steps={steps} />
          )}
        </SurfaceSection>

        <SurfaceSection title={t("operator.section.acceptance_criteria")}>
          <ul className="space-y-1">
            {order.acceptanceCriteria.map((c, i) => (
              <li key={i} className="text-[var(--text-secondary)] text-sm flex items-start gap-2">
                <span className="text-[var(--text-tertiary)] shrink-0 mt-0.5">☐</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>

          {order.missingContext && order.missingContext.length > 0 && (
            <div className="mt-3 pt-3 border-t border-[var(--border-light)]">
              <p className="text-[10px] font-mono uppercase tracking-wider text-status-warning/80 mb-1.5">
                {t("operator.missing_context")}
              </p>
              <ul className="space-y-0.5">
                {order.missingContext.map((m, i) => (
                  <li key={i} className="text-[var(--text-secondary)] text-xs flex items-center gap-1.5">
                    <span className="text-status-warning/70 shrink-0">?</span>
                    <span>{m.label}</span>
                    <span className="text-[10px] text-[var(--text-tertiary)]">
                      ({m.required ? t("operator.required") : t("operator.optional")})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </SurfaceSection>

        {!scope && (
          <div className="px-5 py-4">
            <div className="text-xs text-status-warning/90 bg-status-warning/10 border border-status-warning/30 rounded-lg px-3 py-2 flex items-start gap-2">
              <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{t("operator.section.no_scope_warning")}</span>
            </div>
          </div>
        )}
        {scope && (
          <SurfaceSection title={t("operator.section.approval_scope")}>
            {scope.blockedActions.length === 0 && (
              <div className="text-xs text-status-warning/90 bg-status-warning/10 border border-status-warning/30 rounded-lg px-3 py-2 mb-3 flex items-start gap-2">
                <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{t("operator.section.no_blocked_actions_warning")}</span>
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-status-success/80 mb-1.5 flex items-center gap-1">
                  <ShieldCheck className="h-3 w-3" /> {t("operator.section.allowed_actions")}
                </p>
                <ul className="space-y-0.5">
                  {scope.allowedActions.map((a, i) => (
                    <li key={i} className="text-[var(--text-secondary)] text-xs">{a}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-status-warning/80 mb-1.5 flex items-center gap-1">
                  <ShieldAlert className="h-3 w-3" /> {t("operator.section.requires_approval")}
                </p>
                <ul className="space-y-0.5">
                  {scope.requiresApproval.map((a, i) => (
                    <li key={i} className="text-[var(--text-secondary)] text-xs">{a}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-status-danger/80 mb-1.5 flex items-center gap-1">
                  <ShieldX className="h-3 w-3" /> {t("operator.section.blocked_actions")}
                </p>
                <ul className="space-y-0.5">
                  {scope.blockedActions.map((a, i) => (
                    <li key={i} className="text-[var(--text-secondary)] text-xs">{a}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--text-tertiary)] pt-2 border-t border-[var(--border-light)]">
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
          </SurfaceSection>
        )}

        <SurfaceSection title={t("operator.section.agent_runs")}>
          {runs.length === 0 ? (
            <p className="text-[var(--text-tertiary)] text-xs">{t("operator.section.no_runs")}</p>
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
                  <div key={run.id} className={cn("flex items-start gap-3 py-1.5", isRetry && "ml-4 pl-3 border-l border-[var(--border-light)]")}>
                    {isRetry && <RotateCcw className="h-3.5 w-3.5 text-status-warning/80 shrink-0 mt-0.5" />}
                    <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0", AGENT_RUN_STATUS_COLORS[run.status])}>
                      {t(`operator.run_status.${run.status}`)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-[var(--text-primary)] text-xs font-medium">{t(`operator.role.${run.role}`)}</p>
                        {/* run.model doubles as "which runner, which mode" (e.g. "claude_code
                            (prompt-file)") — no dedicated column for either exists yet, see
                            OP-Runner-Session-001's reviewPackage.risks. */}
                        {run.model && <span className="text-[10px] font-mono text-[var(--text-tertiary)]">{run.model}</span>}
                        <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
                          {t("operator.agent_run.attempt_label")} {run.attemptNumber ?? 1}
                        </span>
                        {run.startedAt && (
                          <span className="text-[10px] font-mono text-[var(--text-tertiary)]">{new Date(run.startedAt).toLocaleString()}</span>
                        )}
                      </div>
                      <p className="text-[var(--text-secondary)] text-xs">{run.inputSummary}</p>
                      {run.outputSummary && <p className="text-[var(--text-tertiary)] text-xs mt-0.5">→ {run.outputSummary}</p>}
                      {retryLabel && (
                        <p className="text-status-warning/80 text-[11px] mt-0.5 flex items-center gap-1">
                          <RotateCcw className="h-3 w-3 shrink-0" /> {retryLabel}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </SurfaceSection>

        <SurfaceSection title={t("operator.section.activity_log")}>
          {log.length === 0 ? (
            <p className="text-[var(--text-tertiary)] text-xs">{t("operator.section.no_activity")}</p>
          ) : (
            <ul className="space-y-1.5 font-mono">
              {log.map((entry) => (
                <li key={entry.id} className="text-xs flex items-start gap-2">
                  <span className="text-[var(--text-tertiary)] shrink-0">{new Date(entry.createdAt).toLocaleString()}</span>
                  <span className={cn("shrink-0 uppercase", LOG_LEVEL_COLORS[entry.level])}>
                    {t(`operator.log.${entry.level}`)}
                  </span>
                  <span className="text-[var(--text-secondary)]">{entry.message}</span>
                </li>
              ))}
            </ul>
          )}
        </SurfaceSection>

        <SurfaceSection title={t("operator.section.artifacts")}>
          {artifacts.length === 0 ? (
            <p className="text-[var(--text-tertiary)] text-xs">{t("operator.section.no_artifacts")}</p>
          ) : (
            <div className="space-y-3">
              {artifacts.map((artifact) => (
                <div key={artifact.id} className="border border-[var(--border-light)] rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]">
                      {t(`operator.artifact.${artifact.type}`)}
                    </span>
                    <p className="text-[var(--text-primary)] text-xs font-medium">{artifact.title}</p>
                  </div>
                  {artifact.content && (
                    <pre className="text-[var(--text-tertiary)] text-xs whitespace-pre-wrap font-mono">{artifact.content}</pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </SurfaceSection>

        {/* ── Local Runner (recommended path) ──────────────────────────────── */}
        <SurfaceSection title={t("operator.runner.title")}>
          <LocalRunnerPanel order={order} agentRuns={runs} reviewPackage={reviewPackage} />
        </SurfaceSection>

        {/* ── Generate Runner Prompt (manual fallback) — renders its own
            header row (title + action), see component for why ──────────── */}
        {scope && <RunnerPromptPanel order={order} scope={scope} steps={steps} />}

        {/* ── Safety rules (always visible, order-independent) ─────────────── */}
        <SurfaceSection title={t("operator.section.safety_rules")} className="rounded-b-lg">
          <SafetyRulesPanel />
        </SurfaceSection>
      </div>

      {!reviewPackage && (
        <p className="text-[var(--text-tertiary)] text-xs flex items-center gap-1.5 px-1">
          <Info className="h-3.5 w-3.5 shrink-0" /> {t("operator.section.no_review_package")}
        </p>
      )}
    </div>
  );
}
