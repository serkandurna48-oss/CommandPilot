"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { PageLoader, EmptyState } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { formatDateShort } from "@/lib/utils";
import type { DailyPlan } from "@/types";
import { Sunrise, ArrowRight, Trophy, Zap } from "lucide-react";

export default function DashboardPage() {
  const [latestPlan, setLatestPlan] = useState<DailyPlan | null>(null);
  const [recentPlans, setRecentPlans] = useState<DailyPlan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const plans = await api.plans.listMine();
        setRecentPlans(plans.slice(0, 7));
        if (plans.length > 0) setLatestPlan(plans[0]);
      } catch {
        // first-time user — no plans yet
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  return (
    <AppShell>
      <Header
        title="Dashboard"
        subtitle="Your personal command center."
      />

      {loading ? (
        <PageLoader />
      ) : (
        <div className="space-y-6">
          {/* CTA: Start morning check-in */}
          {!latestPlan && (
            <div className="rounded-xl bg-gradient-to-br from-brand-600/20 to-slate-800/40 border border-brand-500/20 p-8 text-center">
              <Sunrise className="h-10 w-10 text-brand-400 mx-auto mb-3" />
              <h2 className="text-slate-100 font-semibold text-lg mb-1">No plan for today yet.</h2>
              <p className="text-slate-400 text-sm mb-5">
                Start your morning check-in and get your AI-generated daily strategy in under 30 seconds.
              </p>
              <Link href="/morning">
                <Button size="lg">
                  Start Morning Check-in
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          )}

          {/* Latest plan summary */}
          {latestPlan && (
            <Card variant="elevated">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Today's Plan</CardTitle>
                  <Link href={`/plans/${latestPlan.id}`}>
                    <Button variant="ghost" size="sm">
                      View full plan <ArrowRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Day mode */}
                {latestPlan.day_mode && (
                  <p className="text-brand-400 text-sm font-semibold uppercase tracking-wide">
                    {latestPlan.day_mode}
                  </p>
                )}

                {/* Main win */}
                {latestPlan.main_win && (
                  <div className="flex gap-2">
                    <Trophy className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-slate-200 text-sm">{latestPlan.main_win}</p>
                  </div>
                )}

                {/* Top priorities */}
                {latestPlan.top_priorities.length > 0 && (
                  <div className="space-y-2">
                    {latestPlan.top_priorities.map((p, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="text-brand-500 text-xs font-mono">{i + 1}.</span>
                        <span className="text-slate-300 text-sm">{p.title}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="pt-2 border-t border-slate-700 flex gap-2">
                  <Link href="/morning">
                    <Button variant="secondary" size="sm">New Check-in</Button>
                  </Link>
                  <Link href="/review">
                    <Button variant="ghost" size="sm">Evening Review</Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Recent plans */}
          {recentPlans.length > 1 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-brand-400" />
                  Recent Plans
                </CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-slate-700/50">
                {recentPlans.map((plan) => (
                  <Link
                    key={plan.id}
                    href={`/plans/${plan.id}`}
                    className="flex items-center justify-between py-3 hover:bg-slate-800/30 -mx-5 px-5 transition-colors"
                  >
                    <div>
                      <p className="text-slate-300 text-sm">{formatDateShort(plan.plan_date)}</p>
                      <p className="text-slate-500 text-xs">{plan.day_mode ?? "—"}</p>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-slate-600" />
                  </Link>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </AppShell>
  );
}
