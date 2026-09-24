"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input, Textarea, Select } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useSetJarvisContext, useJarvisPanelControl } from "@/lib/jarvisContext";
import type { Project, ProjectStatus, ProjectPriority } from "@/types";
import { Archive, Pencil, Plus, X, RefreshCw, AlertTriangle, ChevronRight, Sparkles, Globe } from "lucide-react";

const STATUS_OPTIONS: ProjectStatus[] = ["active", "waiting", "paused", "backlog", "done"];
const PRIORITY_OPTIONS: ProjectPriority[] = ["high", "medium", "low"];

// Restrained status badges — Focus Deck tokens (23.09.2026, was raw slate/
// green/rose Tailwind, same debt as operatorStyles.ts had).
const STATUS_COLORS: Record<ProjectStatus, string> = {
  active:   "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
  waiting:  "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  paused:   "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  backlog:  "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  done:     "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  archived: "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-placeholder)]",
};

// Priority text color (restrained)
const PRIORITY_COLORS: Record<ProjectPriority, string> = {
  high:   "text-status-danger",
  medium: "text-[var(--text-tertiary)]",
  low:    "text-[var(--text-placeholder)]",
};

const STATUS_DOT: Record<ProjectStatus, string> = {
  active:   "bg-status-success",
  waiting:  "bg-status-warning",
  paused:   "bg-[var(--text-tertiary)]",
  backlog:  "bg-[var(--text-placeholder)]",
  done:     "bg-status-info",
  archived: "bg-[var(--text-placeholder)]",
};

const EMPTY_FORM = {
  name: "",
  description: "",
  status: "active" as ProjectStatus,
  priority: "medium" as ProjectPriority,
  next_action: "",
  risk: "",
  website_url: "",
};

// Interactive Operating System pass — Projects becomes a control surface:
// a scannable list (title/status/priority/next-move/risk) on the left,
// selecting a row reveals a richer detail panel on the right instead of
// cramming everything into every row. Selecting a project also pushes it
// into JarvisContext, so "Ask Jarvis about this project" opens the panel
// already contextualized — no fabricated data, just the same fields this
// page already renders.
export function ProjectsManager() {
  const t = useT();
  const searchParams = useSearchParams();
  const { openPanel } = useJarvisPanelControl();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadError, setHasLoadError] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editForm, setEditForm] = useState({ ...EMPTY_FORM });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setHasLoadError(false);
    try {
      const data = await api.projects.listMine();
      setProjects(data);
    } catch {
      setHasLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []); // stable — no t dependency to avoid render-loop

  useEffect(() => { loadProjects(); }, [loadProjects]);

  // Deep-link from Home's "Active Projects" rows (?project=<id>) — selects
  // once the real project is loaded, never before (no phantom selection).
  useEffect(() => {
    const qid = searchParams.get("project");
    if (qid && projects.some((p) => p.id === qid)) setSelectedId(qid);
  }, [searchParams, projects]);

  const selectedProject = useMemo(() => projects.find((p) => p.id === selectedId) ?? null, [projects, selectedId]);

  const jarvisCtx = useMemo(() => {
    if (!selectedProject) return null;
    const p = selectedProject;
    const statusLabel = t(`projects.status.${p.status}`);
    const priorityLabel = t(`projects.priority.${p.priority}`);

    // Contextual Intelligence Workspace pass: every field here is real
    // project data already rendered on this page — nothing summarized or
    // invented. Fields without real data (next_action, risk) are simply
    // omitted rather than shown as empty/placeholder rows.
    const snapshot = [
      { label: t("jarvis.snapshot.status"), value: statusLabel },
      { label: t("jarvis.snapshot.priority"), value: priorityLabel },
      ...(p.next_action ? [{ label: t("jarvis.snapshot.next_move"), value: p.next_action }] : []),
      ...(p.risk ? [{ label: t("jarvis.snapshot.risk"), value: p.risk }] : []),
    ];

    return {
      route: "projects",
      entityType: "project" as const,
      entityId: p.id,
      kicker: t("jarvis.kicker.project_selected"),
      title: p.name,
      summary: `Working with: ${p.name}`,
      snapshot,
      quickActions: [
        {
          label: t("jarvis.qa.analyze_risks"),
          description: t("jarvis.qa.analyze_risks_desc"),
          icon: "risk" as const,
          workingLabel: t("jarvis.qa.analyze_risks_working"),
          resultLabel: t("jarvis.qa.analyze_risks_result"),
          prompt:
            `What risks or blockers should I watch for on "${p.name}"?` +
            (p.risk ? ` Currently noted: ${p.risk}.` : " No risk is currently on file.") +
            (p.description ? ` Description: ${p.description}.` : ""),
        },
        {
          label: t("jarvis.qa.review_progress"),
          description: t("jarvis.qa.review_progress_desc"),
          icon: "progress" as const,
          workingLabel: t("jarvis.qa.review_progress_working"),
          resultLabel: t("jarvis.qa.review_progress_result"),
          prompt:
            `Review the current state of the project "${p.name}". Status: ${statusLabel}, priority: ${priorityLabel}.` +
            (p.next_action ? ` Next action on file: ${p.next_action}.` : "") +
            (p.description ? ` Description: ${p.description}.` : ""),
        },
        {
          label: t("jarvis.qa.define_next_move"),
          description: t("jarvis.qa.define_next_move_desc"),
          icon: "next_move" as const,
          workingLabel: t("jarvis.qa.define_next_move_working"),
          resultLabel: t("jarvis.qa.define_next_move_result"),
          prompt:
            `What should the next concrete step be for "${p.name}"?` +
            (p.next_action ? ` Current next action on file: ${p.next_action}.` : ""),
        },
        {
          label: t("jarvis.qa.create_action"),
          description: t("jarvis.qa.create_action_desc"),
          icon: "action" as const,
          workingLabel: t("jarvis.qa.create_action_working"),
          resultLabel: t("jarvis.qa.create_action_result"),
          prompt: `Help me turn the next step for "${p.name}" into a work order for the background dev team.`,
        },
      ],
    };
  }, [selectedProject, t]);

  useSetJarvisContext(jarvisCtx);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      await api.projects.create({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        status: form.status,
        priority: form.priority,
        next_action: form.next_action.trim() || undefined,
        risk: form.risk.trim() || undefined,
        website_url: form.website_url.trim() || undefined,
      });
      setForm({ ...EMPTY_FORM });
      setShowForm(false);
      await loadProjects();
    } catch {
      setFormError(t("error.save_failed"));
    } finally {
      setSaving(false);
    }
  }

  function startEdit(project: Project) {
    setEditingId(project.id);
    setEditError(null);
    setEditForm({
      name: project.name,
      description: project.description ?? "",
      status: project.status,
      priority: project.priority,
      next_action: project.next_action ?? "",
      risk: project.risk ?? "",
      website_url: project.website_url ?? "",
    });
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId || !editForm.name.trim()) return;
    setSaving(true);
    setEditError(null);
    try {
      await api.projects.update(editingId, {
        name: editForm.name.trim(),
        description: editForm.description.trim() || undefined,
        status: editForm.status,
        priority: editForm.priority,
        next_action: editForm.next_action.trim() || undefined,
        risk: editForm.risk.trim() || undefined,
        website_url: editForm.website_url.trim() || undefined,
      });
      setEditingId(null);
      await loadProjects();
    } catch {
      setEditError(t("error.save_failed"));
    } finally {
      setSaving(false);
    }
  }

  async function archiveProject(id: string) {
    if (!confirm(t("projects.confirm_archive"))) return;
    try {
      await api.projects.update(id, { status: "archived" });
      setProjects((prev) => prev.filter((p) => p.id !== id));
      if (selectedId === id) setSelectedId(null);
    } catch {
      alert(t("error.save_failed"));
    }
  }

  const activeCount = projects.filter((p) => p.status === "active").length;
  const waitingCount = projects.filter((p) => p.status === "waiting").length;
  const atRiskCount = projects.filter((p) => !!p.risk).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1.5 flex-wrap">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]">
            {activeCount} {t("projects.status.active")}
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]">
            {waitingCount} {t("projects.status.waiting")}
          </span>
          <span className={cn(
            "text-[10px] font-mono px-2 py-0.5 rounded-md border",
            atRiskCount > 0
              ? "bg-status-warning/10 border-status-warning/30 text-status-warning/90"
              : "bg-[var(--bg-elevated)] border-[var(--border-default)] text-[var(--text-tertiary)]"
          )}>
            {atRiskCount} {t("projects.summary.at_risk")}
          </span>
        </div>
        <Button size="sm" className="rounded-xl" onClick={() => { setShowForm((v) => !v); setFormError(null); setEditingId(null); }}>
          <Plus className="h-4 w-4" />
          {showForm ? t("common.cancel") : t("projects.add")}
        </Button>
      </div>

      {showForm && (
        <Card variant="elevated">
          <CardContent className="pt-4">
            <form onSubmit={handleCreate} className="space-y-3">
              <Input
                label={t("projects.field_name")}
                placeholder="e.g. Launch Q3 Campaign"
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
              <Input
                label={t("projects.field_next_action")}
                placeholder={t("projects.field_next_action_ph")}
                value={form.next_action}
                onChange={(e) => setForm((f) => ({ ...f, next_action: e.target.value }))}
              />
              <div className="grid grid-cols-2 gap-3">
                <Select
                  label={t("projects.field_status")}
                  value={form.status}
                  onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as ProjectStatus }))}
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{t(`projects.status.${s}`)}</option>
                  ))}
                </Select>
                <Select
                  label={t("projects.field_priority")}
                  value={form.priority}
                  onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as ProjectPriority }))}
                >
                  {PRIORITY_OPTIONS.map((p) => (
                    <option key={p} value={p}>{t(`projects.priority.${p}`)}</option>
                  ))}
                </Select>
              </div>
              <Textarea
                label={t("projects.field_description")}
                rows={2}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
              <Input
                label={t("projects.field_risk")}
                placeholder={t("projects.field_risk_ph")}
                value={form.risk}
                onChange={(e) => setForm((f) => ({ ...f, risk: e.target.value }))}
              />
              <Input
                label={t("projects.field_website_url")}
                placeholder={t("projects.field_website_url_ph")}
                type="url"
                value={form.website_url}
                onChange={(e) => setForm((f) => ({ ...f, website_url: e.target.value }))}
              />
              {formError && (
                <p className="text-status-danger text-xs">{formError}</p>
              )}
              <Button type="submit" loading={saving} size="sm" className="rounded-xl">{t("projects.save")}</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="py-8 flex justify-center">
          <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        </div>
      ) : hasLoadError ? (
        <div className="py-8 flex flex-col items-center gap-3 text-center">
          <p className="text-[var(--text-secondary)] text-sm">{t("error.load_failed")}</p>
          <Button size="sm" variant="secondary" className="rounded-xl" onClick={loadProjects}>
            <RefreshCw className="h-4 w-4" />
            {t("button.retry")}
          </Button>
        </div>
      ) : projects.length === 0 ? (
        <EmptyState title={t("projects.empty_title")} description={t("projects.empty_desc")} />
      ) : (
        // List = scan, detail = understand: selecting a row reveals the
        // richer panel instead of every row carrying its full description.
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px] gap-4 items-start">
          <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] divide-y divide-white/[0.05] overflow-hidden">
            {projects.map((project) => {
              const isSelected = project.id === selectedId;
              return (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => setSelectedId(isSelected ? null : project.id)}
                  aria-pressed={isSelected}
                  className={cn(
                    "w-full flex items-center gap-3 px-5 py-3 text-left motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)] focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[-1px] focus-visible:outline-[var(--interactive-border-focus)]",
                    isSelected && "bg-[var(--bg-elevated)]"
                  )}
                >
                  <span className={cn("h-2 w-2 rounded-full shrink-0", STATUS_DOT[project.status])} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-[var(--text-primary)] truncate">{project.name}</p>
                      <span className={cn("text-[10px] px-1.5 py-0.5 rounded-md font-mono shrink-0", STATUS_COLORS[project.status])}>
                        {t(`projects.status.${project.status}`)}
                      </span>
                    </div>
                    {project.next_action && (
                      <p className="text-[var(--text-tertiary)] text-xs truncate mt-0.5">{project.next_action}</p>
                    )}
                  </div>
                  {project.website_url && <Globe className="h-3.5 w-3.5 text-[var(--text-accent)] shrink-0" />}
                  {project.risk && <AlertTriangle className="h-3.5 w-3.5 text-status-warning/80 shrink-0" />}
                  <span className={cn("text-[10px] font-mono shrink-0 hidden sm:inline", PRIORITY_COLORS[project.priority])}>
                    {t(`projects.priority.${project.priority}`)}
                  </span>
                  <ChevronRight className={cn("h-4 w-4 shrink-0 motion-safe:transition-colors duration-150", isSelected ? "text-[var(--text-accent)]" : "text-[var(--text-tertiary)]")} />
                </button>
              );
            })}
          </div>

          <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] overflow-hidden xl:sticky xl:top-8">
            {!selectedProject ? (
              <div className="px-6 py-10 text-center">
                <p className="text-sm font-medium text-[var(--text-secondary)]">{t("projects.detail.empty_title")}</p>
                <p className="text-xs text-[var(--text-tertiary)] mt-1">{t("projects.detail.select_hint")}</p>
              </div>
            ) : editingId === selectedProject.id ? (
              <div className="p-5">
                <form onSubmit={handleUpdate} className="space-y-3">
                  <Input
                    label={t("projects.field_name")}
                    required
                    value={editForm.name}
                    onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                  />
                  <Input
                    label={t("projects.field_next_action")}
                    placeholder={t("projects.field_next_action_ph")}
                    value={editForm.next_action}
                    onChange={(e) => setEditForm((f) => ({ ...f, next_action: e.target.value }))}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <Select
                      label={t("projects.field_status")}
                      value={editForm.status}
                      onChange={(e) => setEditForm((f) => ({ ...f, status: e.target.value as ProjectStatus }))}
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>{t(`projects.status.${s}`)}</option>
                      ))}
                    </Select>
                    <Select
                      label={t("projects.field_priority")}
                      value={editForm.priority}
                      onChange={(e) => setEditForm((f) => ({ ...f, priority: e.target.value as ProjectPriority }))}
                    >
                      {PRIORITY_OPTIONS.map((p) => (
                        <option key={p} value={p}>{t(`projects.priority.${p}`)}</option>
                      ))}
                    </Select>
                  </div>
                  <Textarea
                    label={t("projects.field_description")}
                    rows={2}
                    value={editForm.description}
                    onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                  />
                  <Input
                    label={t("projects.field_risk")}
                    placeholder={t("projects.field_risk_ph")}
                    value={editForm.risk}
                    onChange={(e) => setEditForm((f) => ({ ...f, risk: e.target.value }))}
                  />
                  <Input
                    label={t("projects.field_website_url")}
                    placeholder={t("projects.field_website_url_ph")}
                    type="url"
                    value={editForm.website_url}
                    onChange={(e) => setEditForm((f) => ({ ...f, website_url: e.target.value }))}
                  />
                  {editError && (
                    <p className="text-status-danger text-xs">{editError}</p>
                  )}
                  <div className="flex gap-2">
                    <Button type="submit" loading={saving} size="sm" className="rounded-xl">{t("projects.save_changes")}</Button>
                    <Button type="button" variant="ghost" size="sm" className="rounded-xl" onClick={() => setEditingId(null)}>
                      <X className="h-4 w-4" />
                      {t("common.cancel")}
                    </Button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="p-5 space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-serif text-lg text-[var(--text-primary)] truncate">{selectedProject.name}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className={cn("text-[10px] px-1.5 py-0.5 rounded-md font-mono", STATUS_COLORS[selectedProject.status])}>
                        {t(`projects.status.${selectedProject.status}`)}
                      </span>
                      <span className={cn("text-[10px] font-mono", PRIORITY_COLORS[selectedProject.priority])}>
                        {t(`projects.priority.${selectedProject.priority}`)}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => startEdit(selectedProject)}
                      className="p-1.5 rounded-lg hover:bg-[var(--bg-hover-surface)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] motion-safe:transition-colors duration-150"
                      title={t("projects.edit")}
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => archiveProject(selectedProject.id)}
                      className="p-1.5 rounded-lg hover:bg-[var(--bg-hover-surface)] text-[var(--text-tertiary)] hover:text-status-warning motion-safe:transition-colors duration-150"
                      title={t("projects.archive")}
                    >
                      <Archive className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {selectedProject.next_action && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">{t("projects.field_next_action")}</p>
                    <p className="text-sm text-[var(--text-secondary)] flex items-start gap-1.5">
                      <span className="text-[var(--text-accent)] shrink-0 mt-px">→</span>
                      <span>{selectedProject.next_action}</span>
                    </p>
                  </div>
                )}

                {selectedProject.description && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">{t("projects.field_description")}</p>
                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{selectedProject.description}</p>
                  </div>
                )}

                {selectedProject.risk && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">{t("projects.field_risk")}</p>
                    <p className="text-status-warning/80 text-sm flex items-start gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                      <span>{selectedProject.risk}</span>
                    </p>
                  </div>
                )}

                {selectedProject.website_url && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">{t("projects.field_website_url")}</p>
                    <a
                      href={selectedProject.website_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-[var(--text-accent)] hover:underline flex items-center gap-1.5 break-all"
                    >
                      <Globe className="h-3.5 w-3.5 shrink-0" />
                      <span>{selectedProject.website_url}</span>
                    </a>
                  </div>
                )}

                <button
                  type="button"
                  onClick={openPanel}
                  className="w-full flex items-center gap-2 rounded-xl border border-[var(--border-default)] px-4 py-2.5 text-sm text-[var(--text-primary)] hover:bg-[var(--interactive-bg-secondary-hover)] hover:border-[var(--interactive-bg-primary-default)] motion-safe:transition-colors duration-150"
                >
                  <Sparkles className="h-4 w-4 text-[var(--text-accent)]" />
                  {t("projects.detail.ask_jarvis")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
