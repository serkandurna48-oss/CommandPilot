"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { ReviewForm } from "@/components/review/ReviewForm";
import { PageLoader } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";

function ReviewPageContent() {
  const t = useT();
  const searchParams = useSearchParams();
  const planId = searchParams.get("plan_id") ?? undefined;
  const [reviewQuestions, setReviewQuestions] = useState<string[]>([]);

  useEffect(() => {
    if (planId) {
      api.plans.get(planId)
        .then((plan) => setReviewQuestions(plan.evening_review_questions ?? []))
        .catch(() => {});
    }
  }, [planId]);

  return (
    <AppShell>
      <Header
        title={t("review.title")}
        subtitle={t("review.subtitle")}
      />
      <ReviewForm planId={planId} reviewQuestions={reviewQuestions} />
    </AppShell>
  );
}

export default function ReviewPage() {
  return (
    <Suspense fallback={<AppShell><PageLoader /></AppShell>}>
      <ReviewPageContent />
    </Suspense>
  );
}
