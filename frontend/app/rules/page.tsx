"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { RulesManager } from "@/components/rules/RulesManager";
import { useT } from "@/lib/i18n";

export default function RulesPage() {
  const t = useT();
  return (
    <AppShell>
      <Header
        title={t("rules.title")}
        subtitle={t("rules.subtitle")}
      />
      <RulesManager />
    </AppShell>
  );
}
