"use client";

import Link from "next/link";
import { AlertTriangle, Clock } from "lucide-react";
import { useT } from "@/lib/i18n";
import { cn, daysSince } from "@/lib/utils";
import { PROJECT_STATUS_DOT } from "@/components/dashboard/HomeBriefing";
import type { Project, ProjectStatus } from "@/types";

// Baustein 1 MVP (24.09.2026, revised same day) — "where does each active
// project stand" without a click, using only data already on Project (no
// GitHub, no new backend fields). Two tiers, not one flat list:
//   - "active" only -> compact cards (name, status, next_action, blocker,
//     space-saving recency marker).
//   - everything else that isn't done/archived ("waiting", "paused",
//     "backlog") -> one simple list below, de-emphasized, own status badge
//     per row so a "waiting" project never reads as "paused".
// Real data at the time of writing only has active/waiting/paused rows (no
// backlog) — waiting/backlog are folded into the second tier because the
// brief only named active/paused explicitly, and a real, high-priority
// "waiting" project would otherwise silently vanish from Home.
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
  waiting:  "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  paused:   "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  backlog:  "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  done:     "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  archived: "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-placeholder)]",
};

const PRIORITY_RANK: Record<Project["priority"], number> = { high: 0, medium: 1, low: 2 };

function byPriority(a: Project, b: Project): number {
  return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
}

// Space-saving on purpose (no "Stand: vor ..." sentence) — a short duration
// plus, once stale, a small clock icon carries the same information in far
// less width. STALE_AFTER_DAYS still governs recognizability either way.
function Recency({ updatedAt }: { updatedAt: string }) {
  const t = useT();
  const days = daysSince(updatedAt);
  const isStale = days > STALE_AFTER_DAYS;
  const text =
    days === 0 ? t("dashboard.project_cards.compact_today") :
    days === 1 ? t("dashboard.project_cards.compact_one_day") :
    t("dashboard.project_cards.compact_days").replace("{n}", String(days));

  return (
    <span
      className={cn("inline-flex items-center gap-1 text-[10px] font-mono", isStale ? "text-status-warning" : "text-[var(--text-tertiary)]")}
      title={isStale ? t("dashboard.project_cards.stale_hint") : undefined}
    >
      {isStale && <Clock className="h-3 w-3" />}
      {text}
    </span>
  );
}

function ActiveProjectCard({ project }: { project: Project }) {
  const t = useT();
  const isStale = daysSince(project.updated_at) > STALE_AFTER_DAYS;

  return (
    <Link
      href={`/projects?project=${project.id}`}
      className={cn(
        "block rounded-lg border border-[var(--border-light)] px-3 py-2.5 motion-safe:transition-colors duration-150",
        "hover:border-[var(--interactive-bg-primary-default)] hover:bg-[var(--interactive-bg-secondary-hover)]",
        isStale && "opacity-80"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 min-w-0">
          <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", PROJECT_STATUS_DOT[project.status])} />
          <span className="text-sm font-medium text-[var(--text-primary)] truncate">{project.name}</span>
        </span>
        <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap shrink-0", STATUS_BADGE_COLORS[project.status])}>
          {t(`projects.status.${project.status}`)}
        </span>
      </div>

      {project.next_action ? (
        <p className="text-xs text-[var(--text-secondary)] truncate mt-1">{project.next_action}</p>
      ) : (
        <p className="text-xs text-[var(--text-placeholder)] truncate mt-1">
          {t("dashboard.project_cards.next_action_empty")}{" "}
          <span className="text-[var(--text-accent)] underline underline-offset-2">
            {t("dashboard.project_cards.set_now")}
          </span>
        </p>
      )}

      {project.risk && (
        <p className="flex items-center gap-1 text-[11px] text-status-warning truncate mt-1">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          <span className="truncate">{project.risk}</span>
        </p>
      )}

      <div className="mt-1.5">
        <Recency updatedAt={project.updated_at} />
      </div>
    </Link>
  );
}

function OtherProjectRow({ project }: { project: Project }) {
  const t = useT();
  return (
    <Link
      href={`/projects?project=${project.id}`}
      className="flex items-center gap-3 px-4 py-2 motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)]"
    >
      <span className={cn("h-2 w-2 rounded-full shrink-0", PROJECT_STATUS_DOT[project.status])} />
      <p className="text-sm text-[var(--text-secondary)] truncate flex-1">{project.name}</p>
      <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap shrink-0", STATUS_BADGE_COLORS[project.status])}>
        {t(`projects.status.${project.status}`)}
      </span>
    </Link>
  );
}

export function ProjectCards({ projects }: { projects: Project[] }) {
  const t = useT();
  const active = projects.filter((p) => p.status === "active").sort(byPriority);
  const other = projects
    .filter((p) => p.status === "waiting" || p.status === "paused" || p.status === "backlog")
    .sort(byPriority);

  if (active.length === 0 && other.length === 0) return null;

  return (
    <div className="space-y-4 mb-4">
      {active.length > 0 && (
        <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)]">
          <div className="px-4 py-2.5 border-b border-white/[0.06]">
            <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">
              {t("dashboard.section.active_projects")}
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2.5 p-3">
            {active.map((p) => (
              <ActiveProjectCard key={p.id} project={p} />
            ))}
          </div>
        </div>
      )}

      {other.length > 0 && (
        <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)]">
          <div className="px-4 py-2.5 border-b border-white/[0.06]">
            <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">
              {t("dashboard.project_cards.other_projects")}
            </h2>
          </div>
          <div className="divide-y divide-white/[0.05]">
            {other.map((p) => (
              <OtherProjectRow key={p.id} project={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
