"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { PlanView } from "@/components/plans/PlanView";
import { PageLoader } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { DailyPlan } from "@/types";
import { ArrowLeft, Moon } from "lucide-react";

interface Props {
  params: { id: string };
}

export default function PlanPage({ params }: Props) {
  const { id } = params;
  const t = useT();
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.plans.get(id)
      .then(setPlan)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <AppShell>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-8">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> {t("plan.back")}
          </Button>
        </Link>
        {plan && (
          <Link href={`/review?plan_id=${plan.id}`}>
            <Button variant="secondary" size="sm">
              <Moon className="h-4 w-4" />
              {t("plan.start_review")}
            </Button>
          </Link>
        )}
      </div>

      {loading && <PageLoader />}

      {error && (
        <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
          {t("plan.load_error")} {error}
        </div>
      )}

      {plan && <PlanView plan={plan} />}
    </AppShell>
  );
}
