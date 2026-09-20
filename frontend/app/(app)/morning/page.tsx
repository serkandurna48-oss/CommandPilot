"use client";

import { Header } from "@/components/layout/Header";
import { CheckinForm } from "@/components/morning/CheckinForm";
import { useT } from "@/lib/i18n";

export default function MorningPage() {
  const t = useT();
  return (
    <>
      <Header
        title={t("morning.title")}
        subtitle={t("morning.subtitle")}
      />
      <CheckinForm />
    </>
  );
}
