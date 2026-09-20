"use client";

import Link from "next/link";
import { EmptyState } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import { cn, formatDate, formatDateShort, getUserLanguage } from "@/lib/utils";
import { WORK_ORDER_STATUS_COLORS } from "@/lib/operatorStyles";
import type { DailyPlan, WorkOrder } from "@/types";

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

// One coherent surface per section (Settings visual-fidelity reference):
// a single light border + label, list rows separated by hairlines — no
// per-section icon, circle, or chevron decoration.
function Panel({
  label,
  action,
  children,
}: {
  label: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]/40 h-full">
      <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[var(--border-light)]">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{label}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}

function StatusBadge({ status }: { status: WorkOrder["status"] }) {
  const t = useT();
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap", WORK_ORDER_STATUS_COLORS[status])}>
      {t(`operator.status.${status}`)}
    </span>
  );
}

function ViewAllLink({ href }: { href: string }) {
  const t = useT();
  return (
    <Link href={href} className="text-xs font-medium text-[var(--text-accent)] hover:underline shrink-0">
      {t("dashboard.view_all")}
    </Link>
  );
}

export interface HomeBriefingProps {
  plan: DailyPlan | null;
  needsDecision: WorkOrder[];
  inProgress: WorkOrder[];
  activity: ActivityEvent[];
  pendingId: string | null;
  onRequeue: (id: string) => void;
}

export function HomeBriefing({ plan, needsDecision, inProgress, activity, pendingId, onRequeue }: HomeBriefingProps) {
  const t = useT();
  const priority = plan?.top_priorities?.[0];

  return (
    <div className="max-w-6xl">
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <h1 className="relative inline-block font-serif text-[32px] md:text-[40px] leading-[1.15] font-semibold text-[var(--text-primary)] pb-2.5">
            {t(getGreetingKey())}
            <span className="absolute left-0 bottom-0 h-[2px] w-10 bg-[var(--interactive-bg-primary-default)]" />
          </h1>
          <p className="hidden md:block text-xs font-mono text-[var(--text-tertiary)] whitespace-nowrap mt-2">
            {formatDate(new Date().toISOString())}
          </p>
        </div>
        <p className="text-[var(--text-secondary)] text-sm mt-3">{t("dashboard.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-6 items-start">
        {/* TODAY — the one dominant piece of information, reused from the
            existing daily-plan data (no new AI generation for this screen). */}
        <Panel
          label={t("dashboard.section.today")}
          action={
            plan?.main_win ? (
              <Link href={`/plans/${plan.id}`} className="text-xs font-medium text-[var(--text-accent)] hover:underline shrink-0">
                {t("dashboard.view_plan")}
              </Link>
            ) : undefined
          }
        >
          {plan?.main_win ? (
            <div className="px-6 py-6">
              {priority?.life_area && (
                <p className="text-[11px] font-mono font-semibold uppercase tracking-widest text-[var(--text-accent)] mb-2">
                  {t("dashboard.today.priority_label")} · {priority.life_area}
                </p>
              )}
              <h3 className="text-[26px] md:text-[32px] leading-[1.2] md:leading-[40px] font-semibold text-[var(--text-primary)] mb-3">
                {plan.main_win}
              </h3>
              {(plan.status_summary || priority?.description) && (
                <p className="text-[var(--text-secondary)] text-sm leading-relaxed mb-5">
                  {plan.status_summary || priority?.description}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Link href={`/plans/${plan.id}`}>
                  <Button size="sm">{t("dashboard.view_plan")}</Button>
                </Link>
                <Link href="/morning">
                  <Button size="sm" variant="ghost">
                    {t("dashboard.new_checkin")}
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <EmptyState
              title={t("dashboard.hero.standby")}
              description={t("dashboard.no_plan_sub")}
              action={
                <Link href="/morning">
                  <Button size="sm">{t("dashboard.start_checkin")}</Button>
                </Link>
              }
            />
          )}
        </Panel>

        {/* NEEDS YOUR DECISION — real needs_approval work orders. Jarvis
            suggested_actions live only in chat-session state (never a
            persisted, globally-queryable list), so they cannot appear here;
            see CLAUDE.md's Jarvis section. */}
        <Panel
          label={t("dashboard.section.needs_decision")}
          action={needsDecision.length > 0 ? <ViewAllLink href="/operator" /> : undefined}
        >
          {needsDecision.length === 0 ? (
            <EmptyState title={t("dashboard.decision.empty_title")} description={t("dashboard.decision.empty_desc")} />
          ) : (
            <div className="divide-y divide-[var(--border-light)]">
              {needsDecision.slice(0, 3).map((o) => (
                <div key={o.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-[var(--text-primary)]">{o.title}</p>
                    <StatusBadge status={o.status} />
                  </div>
                  <p className="text-[var(--text-secondary)] text-xs mt-1 line-clamp-2">{o.goal}</p>
                  <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-2">
                    {o.teamType} · {o.targetRepoName || o.repo}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <Button size="sm" loading={pendingId === o.id} disabled={pendingId !== null} onClick={() => onRequeue(o.id)}>
                      {t("operator.lifecycle.requeue")}
                    </Button>
                    <Link href={`/operator/${o.id}`}>
                      <Button size="sm" variant="secondary">
                        {t("dashboard.open")}
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        {/* IN PROGRESS — real running/queued work orders only. */}
        <Panel
          label={t("dashboard.section.in_progress")}
          action={inProgress.length > 0 ? <ViewAllLink href="/operator" /> : undefined}
        >
          {inProgress.length === 0 ? (
            <EmptyState title={t("dashboard.progress.empty_title")} description={t("dashboard.progress.empty_desc")} />
          ) : (
            <div className="divide-y divide-[var(--border-light)]">
              {inProgress.slice(0, 4).map((o) => (
                <Link
                  key={o.id}
                  href={`/operator/${o.id}`}
                  className="flex items-start justify-between gap-3 px-5 py-4 motion-safe:transition-colors hover:bg-[var(--interactive-bg-secondary-hover)]"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--text-primary)] truncate">{o.title}</p>
                    <p className="text-[var(--text-tertiary)] text-[11px] font-mono mt-2">
                      {o.teamType} · {o.targetRepoName || o.repo} · {formatClock(o.startedAt ?? o.createdAt)}
                    </p>
                  </div>
                  <StatusBadge status={o.status} />
                </Link>
              ))}
            </div>
          )}
        </Panel>

        {/* RECENT ACTIVITY — a quiet timeline derived from real work-order
            timestamps (created/started/completed), not a dedicated backend
            activity log (none exists yet). */}
        <Panel label={t("dashboard.section.recent_activity")}>
          {activity.length === 0 ? (
            <EmptyState title={t("dashboard.activity.empty_title")} description={t("dashboard.activity.empty_desc")} />
          ) : (
            <div className="divide-y divide-[var(--border-light)]">
              {activity.map((e) => (
                <Link
                  key={e.key}
                  href={`/operator/${e.workOrderId}`}
                  className="flex items-center justify-between gap-3 px-5 py-3.5 motion-safe:transition-colors hover:bg-[var(--interactive-bg-secondary-hover)]"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-[var(--text-primary)] truncate">{e.title}</p>
                    <p className="text-[var(--text-tertiary)] text-xs mt-0.5">{t(e.verbKey)}</p>
                  </div>
                  <p className="text-[var(--text-tertiary)] text-xs font-mono whitespace-nowrap shrink-0">{formatClock(e.at)}</p>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
