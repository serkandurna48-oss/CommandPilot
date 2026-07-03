"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { Input, Textarea, Select } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Project, ProjectStatus, ProjectPriority } from "@/types";
import { Archive, Pencil, Plus, X, RefreshCw, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS: ProjectStatus[] = ["active", "waiting", "paused", "backlog", "done"];
const PRIORITY_OPTIONS: ProjectPriority[] = ["high", "medium", "low"];

// Restrained status badges
const STATUS_COLORS: Record<ProjectStatus, string> = {
  active:   "bg-slate-800 border border-green-800/40 text-green-400/80",
  waiting:  "bg-slate-800 border border-slate-600 text-slate-300",
  paused:   "bg-slate-800 border border-slate-700 text-slate-500",
  backlog:  "bg-slate-800 border border-slate-700 text-slate-600",
  done:     "bg-slate-800 border border-slate-700 text-slate-400",
  archived: "bg-slate-800 border border-slate-800 text-slate-700",
};

// Priority text color (restrained)
const PRIORITY_COLORS: Record<ProjectPriority, string> = {
  high:   "text-rose-400/80",
  medium: "text-slate-400",
  low:    "text-slate-600",
};

// Left accent border per priority
const PRIORITY_BORDER: Record<ProjectPriority, string> = {
  high:   "border-l-4 border-rose-500/50",
  medium: "border-l-4 border-slate-600/50",
  low:    "border-l-4 border-slate-700/50",
};

const EMPTY_FORM = {
  name: "",
  description: "",
  status: "active" as ProjectStatus,
  priority: "medium" as ProjectPriority,
  next_action: "",
  risk: "",
};

export function ProjectsManager() {
  const t = useT();
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
    } catch {
      alert(t("error.save_failed"));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1.5 flex-wrap">
          {[
            { key: "active", count: projects.filter(p => p.status === "active").length },
            { key: "waiting", count: projects.filter(p => p.status === "waiting").length },
            { key: "backlog", count: projects.filter(p => p.status === "backlog").length },
          ].map(({ key, count }) => (
            <span key={key} className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-500">
              {count} {key}
            </span>
          ))}
        </div>
        <Button size="sm" onClick={() => { setShowForm((v) => !v); setFormError(null); setEditingId(null); }}>
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
              {formError && (
                <p className="text-red-400 text-xs">{formError}</p>
              )}
              <Button type="submit" loading={saving} size="sm">{t("projects.save")}</Button>
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
          <p className="text-slate-400 text-sm">{t("error.load_failed")}</p>
          <Button size="sm" variant="secondary" onClick={loadProjects}>
            <RefreshCw className="h-4 w-4" />
            {t("button.retry")}
          </Button>
        </div>
      ) : projects.length === 0 ? (
        <EmptyState title={t("projects.empty_title")} description={t("projects.empty_desc")} />
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardContent className="py-3">
                {editingId === project.id ? (
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
                    {editError && (
                      <p className="text-red-400 text-xs">{editError}</p>
                    )}
                    <div className="flex gap-2">
                      <Button type="submit" loading={saving} size="sm">{t("projects.save_changes")}</Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditingId(null)}
                      >
                        <X className="h-4 w-4" />
                        {t("common.cancel")}
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className={cn("flex gap-3 items-start -mx-5 -my-3 px-5 py-3 rounded-lg", PRIORITY_BORDER[project.priority])}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1.5">
                        <p className="text-slate-200 text-sm font-medium">{project.name}</p>
                        <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono", STATUS_COLORS[project.status])}>
                          {t(`projects.status.${project.status}`)}
                        </span>
                        <span className={cn("text-[10px] font-mono", PRIORITY_COLORS[project.priority])}>
                          {t(`projects.priority.${project.priority}`)}
                        </span>
                      </div>
                      {project.next_action && (
                        <p className="text-slate-300 text-xs mb-1 flex items-start gap-1.5">
                          <span className="text-brand-500/60 shrink-0 mt-px">→</span>
                          <span>{project.next_action}</span>
                        </p>
                      )}
                      {project.description && (
                        <p className="text-slate-500 text-xs mb-0.5">{project.description}</p>
                      )}
                      {project.risk && (
                        <p className="text-amber-400/70 text-xs flex items-center gap-1.5 mt-0.5">
                          <AlertTriangle className="h-3 w-3 shrink-0" />
                          {project.risk}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={() => startEdit(project)}
                        className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                        title={t("projects.edit")}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => archiveProject(project.id)}
                        className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-400 transition-colors"
                        title={t("projects.archive")}
                      >
                        <Archive className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
