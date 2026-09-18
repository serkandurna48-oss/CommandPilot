"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { JarvisChat } from "@/components/jarvis/JarvisChat";
import { useT } from "@/lib/i18n";

export default function JarvisPage() {
  const t = useT();
  return (
    <AppShell>
      <Header
        title={t("jarvis.title")}
        subtitle={t("jarvis.subtitle")}
      />
      <JarvisChat />
    </AppShell>
  );
}
