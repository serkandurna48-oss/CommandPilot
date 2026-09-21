"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { OperatorManager } from "@/components/operator/OperatorManager";
import { useT } from "@/lib/i18n";

export default function OperatorPage() {
  const t = useT();
  return (
    <>
      <PageHeader
        title={t("operator.title")}
        subtitle={t("operator.subtitle")}
      />
      <OperatorManager />
    </>
  );
}
