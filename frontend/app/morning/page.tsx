import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { CheckinForm } from "@/components/morning/CheckinForm";

export default function MorningPage() {
  return (
    <AppShell>
      <Header
        title="Morning Check-in"
        subtitle="Dump your morning state. The AI handles the structure."
      />
      <CheckinForm />
    </AppShell>
  );
}
