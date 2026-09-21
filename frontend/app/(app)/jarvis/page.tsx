"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/Spinner";
import { useT } from "@/lib/i18n";

// Jarvis lebt jetzt permanent in der Jarvis-Rail (Focus-Deck-Auftrag,
// Slice 2) und wird beim Ankommen auf dieser Route automatisch auf
// "expanded" gestellt (siehe FocusDeckShell). Diese Seite rendert deshalb
// KEINE zweite JarvisChat-Instanz mehr — das gäbe zwei unabhängige,
// gegeneinander laufende Chats mit eigenem State. Nur ein kurzer,
// zustandsneutraler Hinweis im Workspace; JarvisChat selbst bleibt
// unverändert (keine neue Chat-Logik).
export default function JarvisPage() {
  const t = useT();
  return (
    <>
      <PageHeader title={t("jarvis.title")} subtitle={t("jarvis.subtitle")} />
      <EmptyState title={t("jarvis.empty_state")} />
    </>
  );
}
