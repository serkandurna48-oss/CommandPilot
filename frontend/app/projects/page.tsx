"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { ProjectsManager } from "@/components/projects/ProjectsManager";
import { useT } from "@/lib/i18n";

export default function ProjectsPage() {
  const t = useT();
  return (
    <AppShell>
      <Header
        title={t("projects.title")}
        subtitle={t("projects.subtitle")}
      />
      <ProjectsManager />
    </AppShell>
  );
}
