"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import type { AgentRun, ReviewPackage, WorkOrder } from "@/types";
import { isExternalRepoWorkOrder } from "@/lib/workOrderMapper";
import { cn } from "@/lib/utils";
import { Copy, Check, AlertTriangle, Coins, ShieldCheck, FolderGit2, FolderOpen, Container, Loader2 } from "lucide-react";

// Which of these five mutually-exclusive phases we're in — never more than
// one at a time (OP-Workflow-UI-001: "keine widersprüchlichen Zustände").
// order.status alone can't tell "awaiting result" apart from "import
// failed": OP-Import-Integrity-001's atomic gate deliberately leaves
// order.status at "running" when an import's writes fail rather than
// writing a false review_ready, so a failed import looks identical to an
// in-progress one if you only look at order.status. The AgentRun record
// created in OP-Runner-Session-001 is what actually distinguishes them —
// its status reflects what really happened, not what was merely requested.
type RunnerPhase = "not_started" | "prompt_generated" | "awaiting_result" | "import_failed" | "review_ready";

const RUNNER_PHASE_COLORS: Record<RunnerPhase, string> = {
  not_started:      "bg-slate-800 border border-slate-700 text-slate-500",
  prompt_generated: "bg-slate-800 border border-slate-600 text-slate-300",
  awaiting_result:  "bg-slate-800 border border-brand-700/40 text-brand-400/80",
  import_failed:    "bg-slate-800 border border-status-danger/40 text-status-danger",
  review_ready:     "bg-slate-800 border border-status-info/40 text-status-info",
};

function deriveRunnerPhase(
  order: WorkOrder,
  agentRuns: AgentRun[],
  reviewPackage: ReviewPackage | null | undefined,
): RunnerPhase {
  // "Review bereit" nur mit Review Package (AC) — order.status alone saying
  // review_ready is not enough; a status/package mismatch is itself exactly
  // the kind of contradictory state this work order exists to avoid, so it
  // falls through to import_failed below rather than being trusted here.
  if (order.status === "review_ready" && reviewPackage) return "review_ready";

  // No createdAt on AgentRun, but startedAt is now always set at creation
  // time (OP-Runner-Session-001's backend fix) — sort on it to find the
  // actual latest run rather than trusting array order.
  const latestRun = [...agentRuns].sort((a, b) => (b.startedAt ?? "").localeCompare(a.startedAt ?? ""))[0];

  if (order.status === "review_ready" && !reviewPackage) return "import_failed";
  if (latestRun && (latestRun.status === "failed" || latestRun.status === "blocked")) return "import_failed";
  if (latestRun && latestRun.status === "running") return "awaiting_result";
  if (order.status === "running" || order.status === "needs_approval" || order.status === "blocked" || order.status === "rework_requested") {
    return "prompt_generated";
  }
  return "not_started";
}

function CreditBadge({ usesCredits }: { usesCredits: boolean }) {
  const t = useT();
  return usesCredits ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-status-warning/90 bg-status-warning/10 border border-status-warning/30 rounded px-1.5 py-0.5">
      <Coins className="h-3 w-3" /> {t("operator.runner.badge_uses_credits")}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-status-success/80 bg-status-success/10 border border-status-success/30 rounded px-1.5 py-0.5">
      <ShieldCheck className="h-3 w-3" /> {t("operator.runner.badge_no_credits")}
    </span>
  );
}

function CommandBlock({
  label,
  hint,
  command,
  usesCredits,
}: {
  label: string;
  hint?: string;
  command: string;
  usesCredits?: boolean;
}) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable — the <pre> below is still selectable.
    }
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
        {usesCredits !== undefined && <CreditBadge usesCredits={usesCredits} />}
      </div>
      {hint && <p className="text-[var(--text-tertiary)] text-xs">{hint}</p>}
      <div className="flex items-start gap-2">
        <pre className="flex-1 text-xs font-mono bg-[var(--bg-app)] border border-[var(--border-default)] rounded-lg p-2 overflow-x-auto text-[var(--text-secondary)] whitespace-pre-wrap break-all">
          {command}
        </pre>
        <Button size="sm" variant="secondary" onClick={handleCopy}>
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? t("operator.runner.copied") : t("operator.runner.copy")}
        </Button>
      </div>
    </div>
  );
}

function StepNote({ label, hint, usesCredits }: { label: string; hint: string; usesCredits?: boolean }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
        {usesCredits !== undefined && <CreditBadge usesCredits={usesCredits} />}
      </div>
      <p className="text-[var(--text-tertiary)] text-xs">{hint}</p>
    </div>
  );
}

/**
 * CommandPilot is the Control Plane; execution always happens on the
 * Execution Plane — today that's a human running scripts/run_work_order.py
 * on their own machine. This panel never runs anything itself, it just
 * makes the exact commands easy to copy.
 *
 * Every command is PowerShell ($env:VAR = "value", not $VAR) and every
 * placeholder that would otherwise appear bare (a token, an id) is either
 * substituted with a real value (order.id) or kept inside quotes — an
 * unquoted `<...>` in PowerShell is parsed as an input-redirection
 * operator and errors out, which is exactly the footgun a prior real test
 * run hit. See docs/background-dev-team-runbook.md.
 */
export function LocalRunnerPanel({
  order,
  agentRuns = [],
  reviewPackage,
}: {
  order: WorkOrder;
  agentRuns?: AgentRun[];
  reviewPackage?: ReviewPackage | null;
}) {
  const t = useT();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const isExternalRepo = isExternalRepoWorkOrder(order);
  const phase = deriveRunnerPhase(order, agentRuns, reviewPackage);
  // Deterministic — same formula as scripts/run_work_order.py's session_dir():
  // REPO_ROOT / "tmp" / "work-order-runs" / work_order_id. Pure display text,
  // never read from the filesystem here (this runs in the browser).
  const runFolder = `tmp/work-order-runs/${order.id}/`;
  // Applies to both the claude_code and claude_code_sandboxed commands below
  // — both adapters implement execute_step()/supports_step_execution, so the
  // flag is valid for either. Pure display toggle, no backend call.
  const [perStep, setPerStep] = useState(false);
  const perStepFlag = perStep ? " --per-step" : "";

  const setTokenCmd = `$env:COMMANDPILOT_API_TOKEN = "paste-your-token-here"`;
  const startCmd = `python scripts/run_work_order.py ${order.id} --mode prompt-file --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN`;
  // --max-budget-usd is REQUIRED here, not optional decoration: run_work_order.py
  // hard-refuses `--mode execute` with a credit-consuming adapter without an
  // explicit budget (flag or COMMANDPILOT_CLAUDE_MAX_BUDGET_USD) — no default
  // is ever assumed. 0.20 is shown as a starting-point suggestion to edit,
  // not a silently-safe default baked into the script itself. Applies to
  // both claude_code and claude_code_sandboxed — same budget gate either way.
  const executeClaudeCmd = `python scripts/run_work_order.py ${order.id} --mode execute --adapter claude_code --max-budget-usd 0.20 --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN${perStepFlag}`;
  const executeSandboxCmd = `python scripts/run_work_order.py ${order.id} --mode execute --adapter claude_code_sandboxed --max-budget-usd 0.20 --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN${perStepFlag}`;
  const importCmd = `python scripts/run_work_order.py ${order.id} --mode import-result --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN`;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono", RUNNER_PHASE_COLORS[phase])}>
          {t(`operator.runner.phase.${phase}`)}
        </span>
        <span className="text-[var(--text-tertiary)] text-xs">{t(`operator.runner.phase.${phase}_hint`)}</span>
      </div>

      {/* Pure derivation from already-loaded data (order.daemonRunRequestedAt +
          order.status) — no new polling. Disappears on its own once a local
          daemon (scripts/run_work_order_daemon.py) picks the request up and
          run_work_order.py flips status away from "queued" — the existing
          Realtime subscription on this page already re-renders on that. */}
      {order.status === "queued" && order.daemonRunRequestedAt && (
        <div className="rounded-lg bg-status-info/10 border border-status-info/30 px-3 py-2 flex items-start gap-2">
          <Loader2 className="h-3.5 w-3.5 text-status-info/90 shrink-0 mt-0.5 motion-safe:animate-spin" />
          <p className="text-status-info/90 text-xs">{t("operator.runner.waiting_for_daemon_hint")}</p>
        </div>
      )}

      <div className="flex items-center gap-2 text-xs">
        <FolderOpen className="h-3.5 w-3.5 text-[var(--text-tertiary)] shrink-0" />
        <span className="text-[var(--text-tertiary)]">{t("operator.runner.run_folder_label")}:</span>
        <code className="font-mono text-[var(--text-secondary)] bg-[var(--bg-app)] border border-[var(--border-default)] rounded px-1.5 py-0.5">{runFolder}</code>
      </div>

      <p className="text-[var(--text-tertiary)] text-xs">{t("operator.runner.note")}</p>
      <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-placeholder)]">{t("operator.runner.powershell_note")}</p>

      {isExternalRepo && (
        <div className="rounded-lg bg-status-info/10 border border-status-info/30 px-3 py-2 flex items-start gap-2">
          <FolderGit2 className="h-3.5 w-3.5 text-status-info/90 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <p className="text-status-info font-medium">{t("operator.runner.cross_repo_title")}</p>
            <p className="text-[var(--text-secondary)]">
              {t("operator.runner.cross_repo_control_plane")}
            </p>
            <p className="text-[var(--text-secondary)]">
              {t("operator.runner.cross_repo_target")}{" "}
              <span className="font-mono text-[var(--text-primary)]">
                {order.targetRepoName ?? order.targetRepoPath} {order.targetRepoPath ? `(${order.targetRepoPath})` : ""}
              </span>
            </p>
            <p className="text-[var(--text-secondary)]">{t("operator.runner.cross_repo_import")}</p>
          </div>
        </div>
      )}

      <CommandBlock
        label={t("operator.runner.step1_title")}
        hint={t("operator.runner.step1_hint")}
        command={setTokenCmd}
      />

      <div className="rounded-lg bg-status-warning/10 border border-status-warning/30 px-3 py-2 flex items-start gap-2">
        <AlertTriangle className="h-3.5 w-3.5 text-status-warning/90 shrink-0 mt-0.5" />
        <StepNote label={t("operator.runner.step2_title")} hint={t("operator.runner.step2_hint")} />
      </div>

      <CommandBlock label={t("operator.runner.step3_title")} command={startCmd} usesCredits={false} />

      <StepNote
        label={t("operator.runner.step4_manual_title")}
        hint={t("operator.runner.step4_manual_hint")}
        usesCredits={false}
      />

      <label className="flex items-start gap-2 text-xs cursor-pointer">
        <input
          type="checkbox"
          checked={perStep}
          onChange={(e) => setPerStep(e.target.checked)}
          className="mt-0.5 accent-brand-600"
        />
        <span>
          <span className="text-[var(--text-secondary)] font-medium">{t("operator.runner.per_step_toggle_label")}</span>
          <span className="block text-[var(--text-tertiary)]">{t("operator.runner.per_step_toggle_hint")}</span>
        </span>
      </label>

      <CommandBlock
        label={t("operator.runner.step4_auto_title")}
        hint={t("operator.runner.step4_auto_hint")}
        command={executeClaudeCmd}
        usesCredits={true}
      />
      <div className="rounded-lg bg-status-warning/10 border border-status-warning/30 px-3 py-2 flex items-start gap-2">
        <Coins className="h-3.5 w-3.5 text-status-warning/90 shrink-0 mt-0.5" />
        <p className="text-status-warning/90 text-xs">{t("operator.runner.budget_required_hint")}</p>
      </div>

      <CommandBlock
        label={t("operator.runner.step4_sandbox_title")}
        hint={t("operator.runner.step4_sandbox_hint")}
        command={executeSandboxCmd}
        usesCredits={true}
      />
      <div className="rounded-lg bg-status-info/10 border border-status-info/30 px-3 py-2 flex items-start gap-2">
        <Container className="h-3.5 w-3.5 text-status-info/90 shrink-0 mt-0.5" />
        <p className="text-status-info/90 text-xs">{t("operator.runner.sandbox_docker_required_hint")}</p>
      </div>

      <CommandBlock label={t("operator.runner.step5_title")} command={importCmd} />

      <p className="text-[var(--text-tertiary)] text-xs">{t("operator.runner.hint")}</p>
    </div>
  );
}
