"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { CheckinForm } from "@/components/morning/CheckinForm";
import { CheckinHistory } from "@/components/morning/CheckinHistory";
import { PlanHistory } from "@/components/morning/PlanHistory";
import { useT } from "@/lib/i18n";

export default function MorningPage() {
  const t = useT();
  return (
    <>
      <PageHeader
        title={t("morning.title")}
        subtitle={t("morning.subtitle")}
      />
      <CheckinForm />
      <PlanHistory />
      <CheckinHistory />
    </>
  );
}
