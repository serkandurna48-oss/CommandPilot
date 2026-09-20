"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { useT, SUPPORTED_LANGS } from "@/lib/i18n";
import { api } from "@/lib/api";

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
    // Shell (Icon Rail/Jarvis Rail/Workspace-Rahmen) kommt jetzt aus
    // app/(app)/layout.tsx — pro Route nicht mehr einzeln einbinden.
    // Settings behält bewusst eine engere Lesebreite als der Shell-Default
    // (max-w-2xl statt max-w-4xl), wie im letzten Review festgelegt.
    <div className="max-w-2xl">
      {/* Seitentitel: die eine erlaubte Serif-Headline pro View (Design-
          System-Board, Typography-Blatt) — lokal hier, nicht über die
          geteilte Header.tsx, damit unmigrierte Routen (die Header.tsx
          weiter nutzen) optisch unverändert bleiben. */}
      <div className="mb-8">
        <h1 className="font-serif text-[28px] leading-[34px] font-semibold text-[var(--text-primary)]">
          {t("settings.title")}
        </h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">{t("settings.subtitle")}</p>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader><CardTitle>{t("settings.account")}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-xs text-[var(--text-tertiary)] uppercase tracking-wide mb-1">{t("settings.signed_in_as")}</p>
              <p className="text-[var(--text-secondary)] text-sm">{user?.email}</p>
              <p className="text-[var(--text-tertiary)] font-mono text-xs mt-1">{user?.id}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={() => signOut()}>
              {t("settings.sign_out")}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("settings.preferences")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs text-[var(--text-tertiary)] uppercase tracking-wide mb-2">{t("settings.language")}</p>
              <div className="flex gap-2 flex-wrap">
                {SUPPORTED_LANGS.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => handleLanguageChange(value)}
                    disabled={langSaving}
                    className={
                      language === value
                        ? "px-4 py-1.5 rounded-lg text-sm font-medium bg-[var(--interactive-bg-primary-default)] text-white border border-transparent"
                        : "px-4 py-1.5 rounded-lg text-sm font-medium bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-default)] hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors"
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
              {langSaved && (
                <p className="text-brand-400 text-xs mt-2">{t("settings.language_saved")}</p>
              )}
              {langError && (
                <p className="text-status-danger text-xs mt-2">{langError}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-[var(--text-tertiary)] uppercase tracking-wide mb-1">{t("settings.ai_model")}</p>
              <p className="text-[var(--text-secondary)] text-sm">GPT-4o</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
