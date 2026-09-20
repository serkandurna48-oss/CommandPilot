"use client";

import { Header } from "@/components/layout/Header";
import { ProjectsManager } from "@/components/projects/ProjectsManager";
import { useT } from "@/lib/i18n";

export default function ProjectsPage() {
  const t = useT();
  return (
    <>
      <Header
        title={t("projects.title")}
        subtitle={t("projects.subtitle")}
      />
      <ProjectsManager />
    </>
  );
}
