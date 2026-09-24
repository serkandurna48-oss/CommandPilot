"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { useT } from "@/lib/i18n";
import { cn, daysSince } from "@/lib/utils";
import { PROJECT_STATUS_DOT } from "@/components/dashboard/HomeBriefing";
import type { Project, ProjectStatus } from "@/types";

// Baustein 1 MVP (24.09.2026) — "where does each active project stand"
// without a click, using only data already on Project (no GitHub, no new
// backend fields). Replaces the old row-2 "Active Projects" list, which
// showed name + priority only and required a click to learn anything else.
//
// Deliberately NOT showing an open-work-orders-per-project count: WorkOrder
// has no project_id (or any other project linkage) anywhere in the schema
// (checked supabase/migrations/006_work_orders.sql, 009_work_orders_target_repo.sql,
// backend/app/models/work_order.py) — `repo`/`target_repo_name` are free-text
// labels, not a foreign key to Project.id. Matching them by string would be a
// guess, not a real association, so this is left out rather than invented.

const STALE_AFTER_DAYS = 3;

const STATUS_BADGE_COLORS: Record<ProjectStatus, string> = {
  active:   "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
  waiting:  "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  paused:   "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  backlog:  "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  done:     "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  archived: "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-placeholder)]",
};

const PRIORITY_RANK: Record<Project["priority"], number> = { high: 0, medium: 1, low: 2 };

function updatedLabel(t: (key: string) => string, updatedAt: string): { text: string; isStale: boolean } {
  const days = daysSince(updatedAt);
  const isStale = days > STALE_AFTER_DAYS;
  if (days === 0) return { text: t("dashboard.project_cards.updated_today"), isStale };
  if (days === 1) return { text: t("dashboard.project_cards.updated_one_day"), isStale };
  return { text: t("dashboard.project_cards.updated_days").replace("{n}", String(days)), isStale };
}

function ProjectCard({ project }: { project: Project }) {
  const t = useT();
  const { text: updated, isStale } = updatedLabel(t, project.updated_at);

  return (
    <Link
      href={`/projects?project=${project.id}`}
      className={cn(
        "block rounded-xl border border-[var(--border-light)] px-4 py-3.5 motion-safe:transition-colors duration-150",
        "hover:border-[var(--interactive-bg-primary-default)] hover:bg-[var(--interactive-bg-secondary-hover)]",
        isStale && "opacity-70"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-[var(--text-primary)] truncate flex items-center gap-2 min-w-0">
          <span className={cn("h-2 w-2 rounded-full shrink-0", PROJECT_STATUS_DOT[project.status])} />
          <span className="truncate">{project.name}</span>
        </p>
        <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium whitespace-nowrap shrink-0", STATUS_BADGE_COLORS[project.status])}>
          {t(`projects.status.${project.status}`)}
        </span>
      </div>

      <div className="mt-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-0.5">
          {t("dashboard.project_cards.next_action_label")}
        </p>
        {project.next_action ? (
          <p className="text-sm text-[var(--text-secondary)] line-clamp-2">{project.next_action}</p>
        ) : (
          <p className="text-sm text-[var(--text-placeholder)]">
            {t("dashboard.project_cards.next_action_empty")}{" "}
            <span className="text-[var(--text-accent)] underline underline-offset-2">
              {t("dashboard.project_cards.set_now")}
            </span>
          </p>
        )}
      </div>

      {project.risk && (
        <div className="mt-2.5 rounded-lg bg-status-warning/10 border border-status-warning/30 px-2.5 py-2 flex items-start gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-status-warning shrink-0 mt-0.5" />
          <p className="text-status-warning text-xs leading-snug">{project.risk}</p>
        </div>
      )}

      <div className="mt-2.5 flex items-center gap-1.5">
        <p className="text-[11px] font-mono text-[var(--text-tertiary)]">{updated}</p>
        {isStale && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]">
            {t("dashboard.project_cards.stale_hint")}
          </span>
        )}
      </div>
    </Link>
  );
}

export function ProjectCards({ projects }: { projects: Project[] }) {
  const t = useT();
  const active = projects
    .filter((p) => p.status !== "done" && p.status !== "archived")
    .sort((a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]);

  if (active.length === 0) {
    return (
      <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] mb-4">
        <div className="px-4 py-2.5 border-b border-white/[0.06]">
          <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">
            {t("dashboard.section.active_projects")}
          </h2>
        </div>
        <p className="text-[var(--text-tertiary)] text-sm px-4 py-3">{t("projects.empty_desc")}</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] mb-4">
      <div className="px-4 py-2.5 border-b border-white/[0.06]">
        <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">
          {t("dashboard.section.active_projects")}
        </h2>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 p-4">
        {active.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </div>
  );
}
