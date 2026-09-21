"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { RulesManager } from "@/components/rules/RulesManager";
import { useT } from "@/lib/i18n";

export default function RulesPage() {
  const t = useT();
  return (
    <>
      <PageHeader
        title={t("rules.title")}
        subtitle={t("rules.subtitle")}
      />
      <RulesManager />
    </>
  );
}
