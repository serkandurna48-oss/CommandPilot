import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { RulesManager } from "@/components/rules/RulesManager";

export default function RulesPage() {
  return (
    <AppShell>
      <Header
        title="Personal Rules"
        subtitle="Your operating principles. The AI uses these to personalize every plan."
      />
      <RulesManager />
    </AppShell>
  );
}
