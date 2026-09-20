"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { useT, SUPPORTED_LANGS } from "@/lib/i18n";
import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

// One coherent surface, not three separate cards (Focus-Deck-Kompositions-
// Pass): a section is title + description + content, sharing one outer
// border and divided by hairlines — no per-section icon, circle, or chevron.
// Icons/chevrons are for orientation or real navigation; none of these three
// blocks is expandable or needs a category glyph to tell them apart, the
// typography already does that job.
function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-6 py-6">
      <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{title}</h2>
      <p className="text-[var(--text-tertiary)] text-xs mt-0.5">{description}</p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { signOut, user, language, setLanguage } = useAuth();
  const t = useT();
  const [langSaving, setLangSaving] = useState(false);
  const [langSaved, setLangSaved] = useState(false);
  const [langError, setLangError] = useState<string | null>(null);

  async function handleLanguageChange(value: string) {
    if (value !== "en" && value !== "de") return;
    setLangSaving(true);
    setLangSaved(false);
    setLangError(null);
    try {
      await api.profile.update({ language: value });
      setLanguage(value);
      setLangSaved(true);
    } catch (err: unknown) {
      setLangError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLangSaving(false);
    }
  }

  return (
    // Shell (Icon Rail/Jarvis Rail/Workspace-Rahmen) kommt aus
    // app/(app)/layout.tsx — pro Route nicht mehr einzeln einbinden.
    // /settings ist in lib/focusDeckNav.ts's isWideWorkspaceRoute() als
    // Wide-Route markiert (wie /dashboard) — kein ~896px-Lesebreite-Deckel.
    <div>
      {/* Seitentitel: die eine erlaubte Serif-Headline pro View (Design-
          System-Board, Typography-Blatt) — lokal hier, nicht über die
          geteilte Header.tsx, damit unmigrierte Routen (die Header.tsx
          weiter nutzen) optisch unverändert bleiben. */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <h1 className="relative inline-block font-serif text-[40px] leading-[1.15] font-semibold text-[var(--text-primary)] pb-2.5">
            {t("settings.title")}
            <span className="absolute left-0 bottom-0 h-[2px] w-10 bg-[var(--interactive-bg-primary-default)]" />
          </h1>
          {/* Auf Mobile konkurriert das Datum mit der großen Serif-Headline
              um Platz/Aufmerksamkeit — dort ausgeblendet, Desktop bleibt
              unverändert sichtbar. */}
          <p className="hidden md:block text-xs font-mono text-[var(--text-tertiary)] whitespace-nowrap mt-2">
            {formatDate(new Date().toISOString())}
          </p>
        </div>
        <p className="text-[var(--text-secondary)] text-sm mt-3">{t("settings.subtitle")}</p>
      </div>

      {/* Klare Achsen (Focus-Deck-Kompositions-Pass): Section-Titel und
          Section-Content teilen dieselbe linke Kante (px-6 der Section),
          Aktionen (Sign out) landen auf derselben rechten Kante wie der
          Container-Innenrand — keine zufälligen Einrückungen pro Zeile.
          Eine Oberfläche, rounded-lg (mittlere Radius-Ebene, wie Button),
          Abschnitte durch Trennlinien statt eigener Card-Rahmen. */}
      <div className="max-w-6xl rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]/60 divide-y divide-[var(--border-light)]">
        <Section title={t("settings.account")} description={t("settings.account_desc")}>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <p className="text-[var(--text-primary)] text-sm font-medium truncate">{user?.email}</p>
              <p className="text-[var(--text-tertiary)] text-xs mt-0.5">{t("settings.signed_in")}</p>
            </div>
            <Button variant="outline-accent" size="sm" onClick={() => signOut()}>
              {t("settings.sign_out")}
            </Button>
          </div>
        </Section>

        <Section title={t("settings.language")} description={t("settings.language_desc")}>
          <div className="flex gap-3 flex-wrap">
            {SUPPORTED_LANGS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => handleLanguageChange(value)}
                disabled={langSaving}
                className={cn(
                  "px-6 py-3 rounded-lg text-sm font-medium motion-safe:transition-colors",
                  language === value
                    ? "bg-[var(--interactive-bg-primary-default)] text-white"
                    : "bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-default)] hover:bg-[var(--interactive-bg-secondary-hover)]"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {langSaved && <p className="text-brand-400 text-xs mt-3">{t("settings.language_saved")}</p>}
          {langError && <p className="text-status-danger text-xs mt-3">{langError}</p>}
        </Section>

        <Section title={t("settings.ai_model")} description={t("settings.ai_model_desc")}>
          <p className="text-[var(--text-primary)] text-sm font-medium">GPT-4o</p>
          <p className="text-[var(--text-tertiary)] text-xs mt-0.5">{t("settings.ai_model_active")}</p>
        </Section>
      </div>
    </div>
  );
}
