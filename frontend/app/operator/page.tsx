"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { OperatorManager } from "@/components/operator/OperatorManager";
import { useT } from "@/lib/i18n";

export default function OperatorPage() {
  const t = useT();
  return (
    <AppShell>
      <Header
        title={t("operator.title")}
        subtitle={t("operator.subtitle")}
      />
      <OperatorManager />
    </AppShell>
  );
}
