"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageLoader } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { CommandHero } from "@/components/dashboard/CommandHero";
import { SignalNoisePanel } from "@/components/dashboard/SignalNoisePanel";
import { ProjectRadar } from "@/components/dashboard/ProjectRadar";
import { DailyCommandTimeline } from "@/components/dashboard/DailyCommandTimeline";
import { WeeklyMomentum } from "@/components/dashboard/WeeklyMomentum";
import type { DailyPlan, Project, ProjectPriority, ProjectStatus } from "@/types";

// ─── Project sorting helpers ─────────────────────────────────────────────────
const STATUS_SCORE: Partial<Record<ProjectStatus, number>> = { active: 0, waiting: 1 };
const PRIORITY_SCORE: Record<ProjectPriority, number> = { high: 0, medium: 1, low: 2 };

function sortedRelevant(projects: Project[]): Project[] {
  const relevant = projects.filter(
    (p) => p.status === "active" || p.status === "waiting"
  );
  return [...relevant].sort((a, b) => {
    const s = (STATUS_SCORE[a.status] ?? 2) - (STATUS_SCORE[b.status] ?? 2);
    if (s !== 0) return s;
    const p = PRIORITY_SCORE[a.priority] - PRIORITY_SCORE[b.priority];
    if (p !== 0) return p;
    return (a.next_action ? 0 : 1) - (b.next_action ? 0 : 1);
  });
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [latestPlan, setLatestPlan] = useState<DailyPlan | null>(null);
  const [recentPlans, setRecentPlans] = useState<DailyPlan[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const CACHE_KEY = "cp_plans_cache";
    const today = new Date().toISOString().slice(0, 10);

    // Show cached plans immediately if from today
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (raw) {
        const { date, plans } = JSON.parse(raw) as { date: string; plans: DailyPlan[] };
        if (date === today) {
          setRecentPlans(plans.slice(0, 7));
          if (plans.length > 0) setLatestPlan(plans[0]);
          setLoading(false);
        }
      }
    } catch { /* ignore malformed cache */ }

    // Load plans + projects in parallel
    async function load() {
      const [plansResult, projectsResult] = await Promise.allSettled([
        api.plans.listMine(),
        api.projects.listMine(),
      ]);

      if (plansResult.status === "fulfilled") {
        const plans = plansResult.value;
        localStorage.setItem(CACHE_KEY, JSON.stringify({ date: today, plans }));
        setRecentPlans(plans.slice(0, 7));
        if (plans.length > 0) setLatestPlan(plans[0]);
      }
      if (projectsResult.status === "fulfilled") {
        setProjects(projectsResult.value);
      }
      setLoading(false);
    }

    load();
  }, []);

  // Derived project signals
  const sorted = sortedRelevant(projects);
  const focusProject = sorted[0] ?? null;
  const secondaryProjects = sorted.slice(1, 3);
  const noiseItems = latestPlan?.not_today_list ?? [];

  // Cap radar at 4 — link to /projects for the rest
  const radarProjects = sorted.slice(0, 4);
  const totalRelevant = sorted.length;
  const noiseCount = noiseItems.length;

  const hasSignals = focusProject !== null || secondaryProjects.length > 0 || noiseItems.length > 0;
  const hasProjects = sorted.length > 0;

  return (
    <AppShell wide>
      {loading ? (
        <PageLoader />
      ) : (
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
          style={{ backgroundImage: 'radial-gradient(ellipse at 10% 90%, rgba(15,23,42,0.7) 0%, transparent 50%)' }}
        >

          {/* Row 1: Hero Surface — full width, atmosphere rings inside */}
          <div className="md:col-span-3">
            <CommandHero
              plan={latestPlan}
              focusProject={focusProject}
              online={latestPlan !== null}
              activeCount={sorted.length}
              noiseCount={noiseCount}
            />
          </div>

          {/* Row 2: Signal/Noise + Project Radar — adaptive layout */}
          {hasSignals && hasProjects && (
            <>
              <div className="md:col-span-1">
                <SignalNoisePanel
                  focusProject={focusProject}
                  secondaryProjects={secondaryProjects}
                  noiseItems={noiseItems}
                />
              </div>
              <div className="md:col-span-2">
                <ProjectRadar projects={radarProjects} totalCount={totalRelevant} />
              </div>
            </>
          )}
          {hasSignals && !hasProjects && (
            <div className="md:col-span-3">
              <SignalNoisePanel
                focusProject={focusProject}
                secondaryProjects={secondaryProjects}
                noiseItems={noiseItems}
              />
            </div>
          )}
          {!hasSignals && hasProjects && (
            <div className="md:col-span-3">
              <ProjectRadar projects={radarProjects} totalCount={totalRelevant} />
            </div>
          )}

          {/* Row 3: Command Timeline */}
          {latestPlan && latestPlan.time_blocks.length > 0 && (
            <div className="md:col-span-3">
              <DailyCommandTimeline plan={latestPlan} />
            </div>
          )}

          {/* Row 4: Weekly Momentum — slice(1) excludes latest plan shown in Hero; need 3+ total so slice(1) yields 2+ */}
          {recentPlans.length > 2 && (
            <div className="md:col-span-3">
              <WeeklyMomentum recentPlans={recentPlans.slice(1)} />
            </div>
          )}

        </div>
      )}
    </AppShell>
  );
}
