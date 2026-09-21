"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { CreateWorkOrderForm } from "@/components/operator/CreateWorkOrderForm";
import { useT } from "@/lib/i18n";

export default function NewWorkOrderPage() {
  const t = useT();
  return (
    <>
      <PageHeader
        title={t("operator.create.title")}
        subtitle={t("operator.create.subtitle")}
      />
      <CreateWorkOrderForm />
    </>
  );
}
