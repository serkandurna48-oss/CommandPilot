"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FormSection } from "@/components/layout/FormSection";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { useT } from "@/lib/i18n";
import { api, ApiError } from "@/lib/api";
import type { WorkOrderCreateInput, WorkOrderStepInput } from "@/lib/workOrderMapper";
import type { AgentRole } from "@/types";
import { AlertTriangle } from "lucide-react";

// ─── Defaults for the Background Dev Team (the first, not the only, team type) ─
const DEFAULT_ALLOWED = [
  "repo_read", "plan_create", "code_edit_within_scope",
  "test_lint_typecheck", "local_artifacts", "review_package_write",
];
const DEFAULT_REQUIRES_APPROVAL = [
  "dependency_install", "external_service_change", "migration_execute",
  "push_or_pr_create", "runtime_or_cost_increase", "major_architecture_change",
];
const DEFAULT_BLOCKED = [
  "deploy", "production_data_write", "secrets_read_or_log", "email_send",
  "payment_action", "destructive_git", "direct_main_change", "user_data_export",
];

// Default path scope for a "development" work order against this repo.
// Deliberately conservative — a work order can always widen these by
// editing the fields below, but a new work order should never start out
// with no path boundary at all when it's allowed to change code (see
// run_work_order.py's check_execute_path_safety, which blocks auto-
// execution outright if allowed_paths is empty and code changes are allowed).
const DEFAULT_ALLOWED_PATHS = [
  "frontend/**", "backend/**", "scripts/**", "docs/**", "supabase/migrations/**",
];
const DEFAULT_BLOCKED_PATHS = [
  ".env", ".env.*", "**/node_modules/**", "**/.git/**",
  "**/secrets/**", "**/*key*", "**/*token*",
];

const DEFAULT_STEPS: { title: string; description: string; assignedRole: AgentRole; acceptanceCriteria: string[] }[] = [
  { title: "Product Agent", description: "Ziel, Nutzerflow und Akzeptanzkriterien schärfen.", assignedRole: "product", acceptanceCriteria: ["Ziel und Akzeptanzkriterien sind eindeutig formuliert."] },
  { title: "Architect Agent", description: "Technische Umsetzung, Risiken und Architekturentscheidungen klären.", assignedRole: "architect", acceptanceCriteria: ["Technischer Ansatz und Risiken sind dokumentiert."] },
  { title: "Coder Agent", description: "Implementierung innerhalb des Approval Scope.", assignedRole: "coder", acceptanceCriteria: ["Umsetzung liegt innerhalb des Approval Scope."] },
  { title: "QA Agent", description: "Tests, Checks und Edge Cases prüfen.", assignedRole: "qa", acceptanceCriteria: ["Tests/Checks wurden ausgeführt und dokumentiert."] },
  { title: "Reviewer Agent", description: "Bugs, Security und Scope-Verletzungen prüfen.", assignedRole: "reviewer", acceptanceCriteria: ["Keine Scope-Verletzung, Ergebnis geprüft."] },
  { title: "Reporter Agent", description: "Review Package, Artifacts und nächsten Schritt erstellen.", assignedRole: "reporter", acceptanceCriteria: ["Review Package vollständig, nächster Schritt klar."] },
];

function splitLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

// Mirrors scripts/run_work_order.py's _mentions_code_change() /
// check_execute_path_safety() — same signal, shown here before submission
// instead of only at runner-start time.
const CODE_CHANGE_KEYWORDS = ["ändern", "aendern", "change", "edit", "code", "implement"];

function mentionsCodeChange(allowedActions: string[]): boolean {
  return allowedActions.some((a) => CODE_CHANGE_KEYWORDS.some((kw) => a.toLowerCase().includes(kw)));
}

const EMPTY_FORM = {
  title: "",
  goal: "",
  repo: "commandpilot",
  teamType: "development",
  timeLimitMinutes: 90,
  acceptanceCriteria: "",
  allowedActions: DEFAULT_ALLOWED.join("\n"),
  requiresApproval: DEFAULT_REQUIRES_APPROVAL.join("\n"),
  blockedActions: DEFAULT_BLOCKED.join("\n"),
  allowedPaths: DEFAULT_ALLOWED_PATHS.join("\n"),
  blockedPaths: DEFAULT_BLOCKED_PATHS.join("\n"),
  // Optional (OP-Runner-RepoPath-001) — left blank, a work order targets
  // CommandPilot itself, same as before this existed. See
  // frontend/lib/workOrderMapper.ts's isExternalRepoWorkOrder().
  targetRepoName: "",
  targetRepoPath: "",
};

type FormErrors = Partial<Record<keyof typeof EMPTY_FORM, string>>;

export function CreateWorkOrderForm() {
  const t = useT();
  const router = useRouter();
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function set<K extends keyof typeof EMPTY_FORM>(key: K, value: (typeof EMPTY_FORM)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function validate(): FormErrors {
    const next: FormErrors = {};
    if (!form.title.trim()) next.title = t("operator.create.error_required");
    if (!form.goal.trim()) next.goal = t("operator.create.error_required");
    if (!form.repo.trim()) next.repo = t("operator.create.error_required");
    if (!(form.timeLimitMinutes > 0)) next.timeLimitMinutes = t("operator.create.error_time_limit");
    if (splitLines(form.blockedActions).length === 0) next.blockedActions = t("operator.create.error_blocked_required");
    if (splitLines(form.acceptanceCriteria).length === 0) next.acceptanceCriteria = t("operator.create.error_criteria_required");
    return next;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    setSaving(true);
    try {
      const steps: WorkOrderStepInput[] = DEFAULT_STEPS.map((s, i) => ({
        title: s.title,
        description: s.description,
        assignedRole: s.assignedRole,
        orderIndex: i,
        acceptanceCriteria: s.acceptanceCriteria,
      }));

      const input: WorkOrderCreateInput = {
        title: form.title.trim(),
        goal: form.goal.trim(),
        repo: form.repo.trim(),
        teamType: form.teamType.trim() || "development",
        timeLimitMinutes: form.timeLimitMinutes,
        acceptanceCriteria: splitLines(form.acceptanceCriteria),
        steps,
        targetRepoName: form.targetRepoName.trim() || undefined,
        targetRepoPath: form.targetRepoPath.trim() || undefined,
        approvalScope: {
          allowedActions: splitLines(form.allowedActions),
          requiresApproval: splitLines(form.requiresApproval),
          blockedActions: splitLines(form.blockedActions),
          allowedPaths: splitLines(form.allowedPaths).length ? splitLines(form.allowedPaths) : undefined,
          blockedPaths: splitLines(form.blockedPaths).length ? splitLines(form.blockedPaths) : undefined,
          maxRuntimeMinutes: form.timeLimitMinutes,
        },
      };

      const created = await api.workOrders.create(input);
      router.push(`/operator/${created.id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Unknown error";
      setSubmitError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {submitError && (
        <div className="rounded-lg bg-status-danger/10 border border-status-danger/30 px-4 py-3 text-sm text-status-danger">
          <p className="font-medium">{t("operator.create.error_banner")}</p>
          <p className="mt-1 text-status-danger/90">{submitError}</p>
        </div>
      )}

      <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]/60 divide-y divide-[var(--border-light)]">
        <FormSection title={t("operator.create.section_basics")}>
          <Input
            label={t("operator.create.field_title")}
            placeholder={t("operator.create.field_title_ph")}
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
            error={errors.title}
          />
          <Textarea
            label={t("operator.create.field_goal")}
            placeholder={t("operator.create.field_goal_ph")}
            rows={3}
            value={form.goal}
            onChange={(e) => set("goal", e.target.value)}
            error={errors.goal}
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input
              label={t("operator.create.field_repo")}
              value={form.repo}
              onChange={(e) => set("repo", e.target.value)}
              error={errors.repo}
            />
            <Input
              label={t("operator.create.field_time_limit")}
              type="number"
              min={1}
              value={form.timeLimitMinutes}
              onChange={(e) => set("timeLimitMinutes", Number(e.target.value))}
              error={errors.timeLimitMinutes}
            />
            <Input
              label={t("operator.create.field_team_type")}
              value={form.teamType}
              onChange={(e) => set("teamType", e.target.value)}
            />
          </div>
          <p className="text-[var(--text-tertiary)] text-xs">{t("operator.create.field_team_type_hint")}</p>
        </FormSection>

        <FormSection title={t("operator.create.section_target_repo")} description={t("operator.create.section_target_repo_hint")}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Input
              label={t("operator.create.field_target_repo_name")}
              placeholder={t("operator.create.field_target_repo_name_ph")}
              value={form.targetRepoName}
              onChange={(e) => set("targetRepoName", e.target.value)}
            />
            <Input
              label={t("operator.create.field_target_repo_path")}
              placeholder={t("operator.create.field_target_repo_path_ph")}
              value={form.targetRepoPath}
              onChange={(e) => set("targetRepoPath", e.target.value)}
            />
          </div>
          <p className="text-[var(--text-tertiary)] text-xs">{t("operator.create.field_target_repo_path_safety")}</p>
        </FormSection>

        <FormSection title={t("operator.create.section_criteria")}>
          <Textarea
            label={t("operator.create.field_criteria")}
            rows={4}
            value={form.acceptanceCriteria}
            onChange={(e) => set("acceptanceCriteria", e.target.value)}
            error={errors.acceptanceCriteria}
          />
        </FormSection>

        <FormSection title={t("operator.create.section_scope")} description={t("operator.create.defaults_hint")}>
          <Textarea
            label={t("operator.create.field_allowed")}
            rows={4}
            value={form.allowedActions}
            onChange={(e) => set("allowedActions", e.target.value)}
          />
          <Textarea
            label={t("operator.create.field_requires_approval")}
            rows={4}
            value={form.requiresApproval}
            onChange={(e) => set("requiresApproval", e.target.value)}
          />
          <Textarea
            label={t("operator.create.field_blocked")}
            rows={4}
            value={form.blockedActions}
            onChange={(e) => set("blockedActions", e.target.value)}
            error={errors.blockedActions}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Textarea
              label={t("operator.create.field_allowed_paths")}
              rows={3}
              value={form.allowedPaths}
              onChange={(e) => set("allowedPaths", e.target.value)}
            />
            <Textarea
              label={t("operator.create.field_blocked_paths")}
              rows={3}
              value={form.blockedPaths}
              onChange={(e) => set("blockedPaths", e.target.value)}
            />
          </div>
          {mentionsCodeChange(splitLines(form.allowedActions)) && splitLines(form.allowedPaths).length === 0 && (
            <div className="rounded-lg bg-status-warning/10 border border-status-warning/30 px-3 py-2 flex items-start gap-2">
              <AlertTriangle className="h-3.5 w-3.5 text-status-warning/80 shrink-0 mt-0.5" />
              <p className="text-status-warning/90 text-xs">{t("operator.create.warning_no_allowed_paths")}</p>
            </div>
          )}
        </FormSection>
      </div>

      <p className="text-[var(--text-tertiary)] text-xs">{t("operator.create.steps_hint")}</p>

      <div className="flex gap-2">
        <Button type="submit" loading={saving}>
          {saving ? t("operator.create.submitting") : t("operator.create.submit")}
        </Button>
        <Button type="button" variant="ghost" onClick={() => router.push("/operator")}>
          {t("operator.create.cancel")}
        </Button>
      </div>
    </form>
  );
}
