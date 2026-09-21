"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import { cn, formatDate, formatDateShort, getUserLanguage } from "@/lib/utils";
import { WORK_ORDER_STATUS_COLORS } from "@/lib/operatorStyles";
import { ProductWebsites } from "@/components/dashboard/ProductWebsites";
import type { DailyPlan, Project, ProjectStatus, WorkOrder } from "@/types";
import { ChevronRight } from "lucide-react";

export function getGreetingKey(): string {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return "greeting.morning";
  if (h >= 12 && h < 17) return "greeting.afternoon";
  if (h >= 17 && h < 22) return "greeting.evening";
  return "greeting.night";
}

// Same-day events read as a clock time (matches the reference); anything
// older falls back to a short date so the feed stays legible after a gap.
export function formatClock(iso: string): string {
  const d = new Date(iso);
  if (d.toDateString() === new Date().toDateString()) {
    const locale = getUserLanguage() === "de" ? "de-DE" : "en-US";
    return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  }
  return formatDateShort(iso);
}

export interface ActivityEvent {
  key: string;
  workOrderId: string;
  title: string;
  verbKey: string;
  at: string;
  status: WorkOrder["status"];
}

// Derived, not fabricated: every event below reuses a timestamp the work
// order already carries (created_at/started_at/completed_at) — there is no
// dedicated cross-work-order activity endpoint yet (see CLAUDE.md).
export function buildActivity(orders: WorkOrder[]): ActivityEvent[] {
  const events: ActivityEvent[] = [];
  for (const o of orders) {
    events.push({ key: `${o.id}-created`, workOrderId: o.id, title: o.title, verbKey: "dashboard.activity.created", at: o.createdAt, status: o.status });
    if (o.startedAt) {
      events.push({ key: `${o.id}-started`, workOrderId: o.id, title: o.title, verbKey: "dashboard.activity.started", at: o.startedAt, status: o.status });
    }
    if (o.completedAt) {
      events.push({ key: `${o.id}-completed`, workOrderId: o.id, title: o.title, verbKey: "dashboard.activity.completed", at: o.completedAt, status: o.status });
    }
  }
  return events.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
}

// HOME V2 — compact, content-sized section. No icon (bronze is scarce now —
// see globals), no forced height. A section with little content is allowed
// to be short; equal height is not automatically good composition.
function Section({
  title,
  action,
  className,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)]", className)}>
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-white/[0.06]">
        <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}

// One muted sentence, nothing more — an empty state should communicate
// "nothing here" and then get out of the way, not dominate the card.
function InlineEmpty({ text }: { text: string }) {
  return <p className="text-[var(--text-tertiary)] text-sm px-4 py-3">{text}</p>;
}

function StatusBadge({ status }: { status: WorkOrder["status"] }) {
  const t = useT();
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium whitespace-nowrap", WORK_ORDER_STATUS_COLORS[status])}>
      {t(`operator.status.${status}`)}
    </span>
  );
}

function ViewAllLink({ href }: { href: string }) {
  const t = useT();
  return (
    <Link href={href} className="text-xs font-medium text-[var(--text-accent)] hover:underline shrink-0 flex items-center gap-0.5">
      {t("dashboard.view_all")}
      <ChevronRight className="h-3.5 w-3.5" />
    </Link>
  );
}

const PROJECT_STATUS_DOT: Record<ProjectStatus, string> = {
  active:   "bg-status-success",
  waiting:  "bg-status-warning",
  paused:   "bg-[var(--text-tertiary)]",
  backlog:  "bg-[var(--text-placeholder)]",
  done:     "bg-status-info",
  archived: "bg-[var(--text-placeholder)]",
};

const WORK_ORDER_STATUS_DOT: Record<WorkOrder["status"], string> = {
  draft:            "bg-[var(--text-placeholder)]",
  approved:         "bg-status-success",
  queued:           "bg-[var(--text-tertiary)]",
  running:          "bg-brand-400",
  needs_approval:   "bg-status-warning",
  blocked:          "bg-status-warning",
  failed:           "bg-status-danger",
  review_ready:     "bg-status-info",
  accepted:         "bg-status-success",
  rework_requested: "bg-status-warning",
  cancelled:        "bg-[var(--text-placeholder)]",
};

export interface HomeBriefingProps {
  plan: DailyPlan | null;
  needsDecision: WorkOrder[];
  inProgress: WorkOrder[];
  activity: ActivityEvent[];
  projects: Project[];
  pendingId: string | null;
  onRequeue: (id: string) => void;
}

export function HomeBriefing({ plan, needsDecision, inProgress, activity, projects, pendingId, onRequeue }: HomeBriefingProps) {
  const t = useT();
  const priority = plan?.top_priorities?.[0];
  const activeProjects = projects.filter((p) => p.status !== "archived" && p.status !== "done").slice(0, 7);

  return (
    <div>
      {/* Compact masthead: one line, greeting sets tone, date/wordmark
          belongs on the same baseline instead of floating in a corner. */}
      <div className="flex items-baseline justify-between gap-4 mb-5 pb-4 border-b border-white/[0.06]">
        <h1 className="font-serif text-[22px] md:text-[26px] font-semibold text-[var(--text-primary)]">
          {t(getGreetingKey())}
        </h1>
        <div className="hidden md:flex items-baseline gap-2 text-xs font-mono text-[var(--text-tertiary)] whitespace-nowrap">
          <span>{formatDate(new Date().toISOString())}</span>
          <span className="text-[var(--border-heavy)]">·</span>
          <span className="font-serif text-[13px] not-italic">CommandPilot</span>
        </div>
      </div>

      {/* ROW 1 — TODAY stays the dominant editorial moment, now alongside
          (not above) the operational rail: the recovered width goes to
          putting Needs Decision + In Progress beside it, not to stretching
          the headline further. Below xl, the rail drops beneath. */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-4 items-start mb-5">
        {plan?.main_win ? (
          <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-elevated)] shadow-[var(--shadow-card)] px-7 py-6">
            {priority?.life_area && (
              <p className="text-[11px] font-mono uppercase tracking-wide text-[var(--text-tertiary)] mb-2">
                {priority.life_area}
              </p>
            )}
            {/* Card stays wide; the prose column inside it does not — a
                readable line length, with the extra width left as
                intentional space rather than stretched further. */}
            <h2 className="relative inline-block max-w-2xl font-serif text-[26px] md:text-[32px] leading-[1.2] tracking-tight font-semibold text-[var(--text-primary)] pb-2">
              {plan.main_win}
              <span className="absolute left-0 bottom-0 h-[2px] w-8 bg-[var(--interactive-bg-primary-default)]" />
            </h2>
            {(plan.status_summary || priority?.description) && (
              <p className="text-[var(--text-secondary)] text-sm leading-relaxed mt-3 max-w-xl">
                {plan.status_summary || priority?.description}
              </p>
            )}
            {/* Same control family, different emphasis: primary fill vs. a
                real (bordered) secondary — not a filled button next to
                unweighted text. */}
            <div className="flex flex-wrap items-center gap-2.5 mt-5">
              <Link href={`/plans/${plan.id}`}>
                <Button size="sm" className="rounded-xl">
                  {t("dashboard.view_plan")}
                </Button>
              </Link>
              <Link href="/morning">
                <Button size="sm" variant="secondary" className="rounded-xl">
                  {t("dashboard.new_checkin")}
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-elevated)] shadow-[var(--shadow-card)] px-7 py-5 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="font-serif text-[20px] text-[var(--text-primary)]">{t("dashboard.hero.standby")}</p>
              <p className="text-[var(--text-tertiary)] text-sm mt-1">{t("dashboard.no_plan_sub")}</p>
            </div>
            <Link href="/morning">
              <Button size="sm" className="rounded-xl">{t("dashboard.start_checkin")}</Button>
            </Link>
          </div>
        )}

        {/* Operational rail — compact operational blocks, content-sized
            (no h-full, no forced equal height). */}
        <div className="flex flex-col gap-4">
          <Section
            title={t("dashboard.section.needs_decision")}
            action={needsDecision.length > 0 ? <ViewAllLink href="/operator" /> : undefined}
          >
            {needsDecision.length === 0 ? (
              <InlineEmpty text={t("dashboard.decision.empty_desc")} />
            ) : (
              <div className="divide-y divide-white/[0.05]">
                {/* The row's informational body is itself the "open" affordance
                    (Interactive Operating System pass) — Requeue stays a
                    separate sibling control since it's a mutation, not
                    navigation, and can't live inside the same link. */}
                {needsDecision.slice(0, 3).map((o) => (
                  <div key={o.id}>
                    <Link
                      href={`/operator/${o.id}`}
                      className="block px-4 pt-2.5 hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors duration-150 focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[-1px] focus-visible:outline-[var(--interactive-border-focus)]"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2 min-w-0">
                          <span className={cn("h-2 w-2 rounded-full shrink-0", WORK_ORDER_STATUS_DOT[o.status])} />
                          <span className="truncate">{o.title}</span>
                        </p>
                        <StatusBadge status={o.status} />
                      </div>
                      <p className="text-[var(--text-secondary)] text-xs mt-1 line-clamp-1 pl-4">{o.goal}</p>
                    </Link>
                    <div className="flex flex-wrap gap-2 px-4 pt-2 pb-2.5 pl-4">
                      <Button size="sm" className="rounded-xl" loading={pendingId === o.id} disabled={pendingId !== null} onClick={() => onRequeue(o.id)}>
                        {t("operator.lifecycle.requeue")}
                      </Button>
                      <Link href={`/operator/${o.id}`}>
                        <Button size="sm" variant="secondary" className="rounded-xl">
                          {t("dashboard.open")}
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section
            title={t("dashboard.section.in_progress")}
            action={inProgress.length > 0 ? <ViewAllLink href="/operator" /> : undefined}
          >
            {inProgress.length === 0 ? (
              <InlineEmpty text={t("dashboard.progress.empty_desc")} />
            ) : (
              <div className="divide-y divide-white/[0.05]">
                {inProgress.slice(0, 4).map((o) => (
                  <Link
                    key={o.id}
                    href={`/operator/${o.id}`}
                    className="flex items-center gap-3 px-4 py-2.5 motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)]"
                  >
                    <span className={cn("h-2 w-2 rounded-full shrink-0", WORK_ORDER_STATUS_DOT[o.status])} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--text-primary)] truncate">{o.title}</p>
                      <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-0.5 truncate">
                        {o.teamType} · {formatClock(o.startedAt ?? o.createdAt)}
                      </p>
                    </div>
                    <StatusBadge status={o.status} />
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </div>
      </div>

      <ProductWebsites projects={projects} />

      {/* ROW 2 — Recent activity + active projects: supporting context,
          clearly subordinate, densest rows, last in the flow. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title={t("dashboard.section.recent_activity")}>
          {activity.length === 0 ? (
            <InlineEmpty text={t("dashboard.activity.empty_desc")} />
          ) : (
            <div className="divide-y divide-white/[0.05]">
              {activity.slice(0, 6).map((e) => (
                <Link
                  key={e.key}
                  href={`/operator/${e.workOrderId}`}
                  className="flex items-center gap-3 px-4 py-2.5 motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)]"
                >
                  <span className={cn("h-2 w-2 rounded-full shrink-0", WORK_ORDER_STATUS_DOT[e.status])} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[var(--text-primary)] truncate">{e.title}</p>
                    <p className="text-[var(--text-tertiary)] text-[11px] mt-0.5">{t(e.verbKey)}</p>
                  </div>
                  <p className="text-[var(--text-tertiary)] text-[11px] font-mono whitespace-nowrap shrink-0">{formatClock(e.at)}</p>
                </Link>
              ))}
            </div>
          )}
        </Section>

        <Section title={t("dashboard.section.active_projects")} action={activeProjects.length > 0 ? <ViewAllLink href="/projects" /> : undefined}>
          {activeProjects.length === 0 ? (
            <InlineEmpty text={t("projects.empty_desc")} />
          ) : (
            <div className="divide-y divide-white/[0.05]">
              {activeProjects.map((p) => (
                <Link
                  key={p.id}
                  href={`/projects?project=${p.id}`}
                  className="flex items-center gap-3 px-4 py-2.5 motion-safe:transition-colors duration-150 hover:bg-[var(--interactive-bg-secondary-hover)]"
                >
                  <span className={cn("h-2 w-2 rounded-full shrink-0", PROJECT_STATUS_DOT[p.status])} />
                  <p className="text-sm font-medium text-[var(--text-primary)] truncate flex-1">{p.name}</p>
                  <p className="text-[var(--text-tertiary)] text-[11px] font-mono whitespace-nowrap shrink-0">
                    {t(`projects.priority.${p.priority}`)}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
