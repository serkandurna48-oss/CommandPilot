"use client";

import { Header } from "@/components/layout/Header";
import { CreateWorkOrderForm } from "@/components/operator/CreateWorkOrderForm";
import { useT } from "@/lib/i18n";

export default function NewWorkOrderPage() {
  const t = useT();
  return (
    <>
      <Header
        title={t("operator.create.title")}
        subtitle={t("operator.create.subtitle")}
      />
      <CreateWorkOrderForm />
    </>
  );
}
