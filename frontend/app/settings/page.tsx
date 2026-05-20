"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
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
    <AppShell>
      <Header
        title={t("settings.title")}
        subtitle={t("settings.subtitle")}
      />

      <div className="space-y-4">
        <Card>
          <CardHeader><CardTitle>{t("settings.account")}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">{t("settings.signed_in_as")}</p>
              <p className="text-slate-300 text-sm">{user?.email}</p>
              <p className="text-slate-600 font-mono text-xs mt-1">{user?.id}</p>
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
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">{t("settings.language")}</p>
              <div className="flex gap-2 flex-wrap">
                {SUPPORTED_LANGS.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => handleLanguageChange(value)}
                    disabled={langSaving}
                    className={
                      language === value
                        ? "px-4 py-1.5 rounded-lg text-sm font-medium bg-brand-600 text-white border border-brand-500"
                        : "px-4 py-1.5 rounded-lg text-sm font-medium bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 transition-colors"
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
                <p className="text-red-400 text-xs mt-2">{langError}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">{t("settings.ai_model")}</p>
              <p className="text-slate-400 text-sm">GPT-4o — set in backend .env</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
