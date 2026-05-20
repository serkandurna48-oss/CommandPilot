"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { CheckinForm } from "@/components/morning/CheckinForm";
import { useT } from "@/lib/i18n";

export default function MorningPage() {
  const t = useT();
  return (
    <AppShell>
      <Header
        title={t("morning.title")}
        subtitle={t("morning.subtitle")}
      />
      <CheckinForm />
    </AppShell>
  );
}
