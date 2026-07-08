"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import type { WorkOrder } from "@/types";
import { isExternalRepoWorkOrder } from "@/lib/workOrderMapper";
import { Copy, Check, AlertTriangle, Coins, ShieldCheck, FolderGit2 } from "lucide-react";

function CreditBadge({ usesCredits }: { usesCredits: boolean }) {
  const t = useT();
  return usesCredits ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-amber-400/90 bg-amber-950/30 border border-amber-900/40 rounded px-1.5 py-0.5">
      <Coins className="h-3 w-3" /> {t("operator.runner.badge_uses_credits")}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-emerald-400/80 bg-emerald-950/20 border border-emerald-900/30 rounded px-1.5 py-0.5">
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
        <p className="text-xs font-medium text-slate-300">{label}</p>
        {usesCredits !== undefined && <CreditBadge usesCredits={usesCredits} />}
      </div>
      {hint && <p className="text-slate-500 text-xs">{hint}</p>}
      <div className="flex items-start gap-2">
        <pre className="flex-1 text-xs font-mono bg-slate-950 border border-slate-700 rounded-lg p-2 overflow-x-auto text-slate-300 whitespace-pre-wrap break-all">
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
        <p className="text-xs font-medium text-slate-300">{label}</p>
        {usesCredits !== undefined && <CreditBadge usesCredits={usesCredits} />}
      </div>
      <p className="text-slate-500 text-xs">{hint}</p>
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
export function LocalRunnerPanel({ order }: { order: WorkOrder }) {
  const t = useT();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const isExternalRepo = isExternalRepoWorkOrder(order);

  const setTokenCmd = `$env:COMMANDPILOT_API_TOKEN = "paste-your-token-here"`;
  const startCmd = `python scripts/run_work_order.py ${order.id} --mode prompt-file --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN`;
  // --max-budget-usd is REQUIRED here, not optional decoration: run_work_order.py
  // hard-refuses `--mode execute --adapter claude_code` without an explicit
  // budget (flag or COMMANDPILOT_CLAUDE_MAX_BUDGET_USD) — no default is ever
  // assumed. 0.20 is shown as a starting-point suggestion to edit, not a
  // silently-safe default baked into the script itself.
  const executeClaudeCmd = `python scripts/run_work_order.py ${order.id} --mode execute --adapter claude_code --max-budget-usd 0.20 --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN`;
  const importCmd = `python scripts/run_work_order.py ${order.id} --mode import-result --api-url ${apiUrl} --token $env:COMMANDPILOT_API_TOKEN`;

  return (
    <Card variant="bordered">
      <CardHeader>
        <CardTitle>{t("operator.runner.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-slate-500 text-xs">{t("operator.runner.note")}</p>
        <p className="text-[10px] font-mono uppercase tracking-wider text-slate-600">{t("operator.runner.powershell_note")}</p>

        {isExternalRepo && (
          <div className="rounded-lg bg-sky-950/20 border border-sky-900/30 px-3 py-2 flex items-start gap-2">
            <FolderGit2 className="h-3.5 w-3.5 text-sky-400/80 shrink-0 mt-0.5" />
            <div className="space-y-1 text-xs">
              <p className="text-sky-300/90 font-medium">{t("operator.runner.cross_repo_title")}</p>
              <p className="text-slate-400">
                {t("operator.runner.cross_repo_control_plane")}
              </p>
              <p className="text-slate-400">
                {t("operator.runner.cross_repo_target")}{" "}
                <span className="font-mono text-slate-300">
                  {order.targetRepoName ?? order.targetRepoPath} {order.targetRepoPath ? `(${order.targetRepoPath})` : ""}
                </span>
              </p>
              <p className="text-slate-400">{t("operator.runner.cross_repo_import")}</p>
            </div>
          </div>
        )}

        <CommandBlock
          label={t("operator.runner.step1_title")}
          hint={t("operator.runner.step1_hint")}
          command={setTokenCmd}
        />

        <div className="rounded-lg bg-amber-950/20 border border-amber-900/30 px-3 py-2 flex items-start gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400/80 shrink-0 mt-0.5" />
          <StepNote label={t("operator.runner.step2_title")} hint={t("operator.runner.step2_hint")} />
        </div>

        <CommandBlock label={t("operator.runner.step3_title")} command={startCmd} usesCredits={false} />

        <StepNote
          label={t("operator.runner.step4_manual_title")}
          hint={t("operator.runner.step4_manual_hint")}
          usesCredits={false}
        />
        <CommandBlock
          label={t("operator.runner.step4_auto_title")}
          hint={t("operator.runner.step4_auto_hint")}
          command={executeClaudeCmd}
          usesCredits={true}
        />
        <div className="rounded-lg bg-amber-950/20 border border-amber-900/30 px-3 py-2 flex items-start gap-2">
          <Coins className="h-3.5 w-3.5 text-amber-400/80 shrink-0 mt-0.5" />
          <p className="text-amber-300/90 text-xs">{t("operator.runner.budget_required_hint")}</p>
        </div>

        <CommandBlock label={t("operator.runner.step5_title")} command={importCmd} />

        <p className="text-slate-500 text-xs">{t("operator.runner.hint")}</p>
      </CardContent>
    </Card>
  );
}
