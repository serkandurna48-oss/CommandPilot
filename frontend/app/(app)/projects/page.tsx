"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectsManager } from "@/components/projects/ProjectsManager";
import { useT } from "@/lib/i18n";

export default function ProjectsPage() {
  const t = useT();
  return (
    <>
      <PageHeader
        title={t("projects.title")}
        subtitle={t("projects.subtitle")}
      />
      <ProjectsManager />
    </>
  );
}
