"use client";

import { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { MobileNav } from "@/components/layout/MobileNav";
import { Header } from "@/components/layout/Header";
import { useT } from "@/lib/i18n";
import type { JarvisSourceRef, JarvisSuggestedAction } from "@/types";
import { DesignTokens } from "./DesignTokens";
import { PreviewJarvisPanel } from "./PreviewJarvisPanel";
import { PreviewActionCard } from "./PreviewActionCard";
import { FlaskConical } from "lucide-react";

type Selected =
  | { type: "source"; source: JarvisSourceRef }
  | { type: "action"; action: JarvisSuggestedAction }
  | null;

const SUGGESTED_ACTIONS: JarvisSuggestedAction[] = [
  {
    title: "Finance-Abstimmung für Q3-Report vorbereiten",
    description:
      "Entwurf ist fertig, offen ist die Rückmeldung von Finance. Fasst den aktuellen Stand zusammen und formuliert eine Nachfrage.",
    team_type: "development",
    target_repo_name: null,
    risk: "low",
    requires_approval: false,
    sources: [{ source_file: "Projekte/Q3-Report.md", source_heading: "Status" }],
  },
  {
    title: "Alternativanbieter für Zahlungsanbindung recherchieren",
    description:
      "Der aktuelle Anbieter reagiert seit zwei Wochen nicht. Stellt zwei bis drei Alternativen mit Vor- und Nachteilen zusammen.",
    team_type: "development",
    target_repo_name: "CampPilot",
    risk: "medium",
    requires_approval: true,
    sources: [{ source_file: "Projekte/CampPilot.md", source_heading: "Zahlungsanbindung" }],
  },
  {
    title: "Schreibzugriff auf die Produktionsdatenbank für ein Migrationsskript",
    description:
      "Würde eine einmalige, manuelle Datenkorrektur direkt in der Produktionsdatenbank ausführen.",
    team_type: "development",
    target_repo_name: "CommandPilot",
    risk: "high",
    requires_approval: true,
    sources: [],
  },
];

export default function DesignPreviewPage() {
  const t = useT();
  const [selected, setSelected] = useState<Selected>(null);

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="bg-status-warning/10 border-b border-status-warning/30 px-4 md:px-8 py-2 flex items-center gap-2 text-status-warning text-xs">
          <FlaskConical className="h-3.5 w-3.5 shrink-0" />
          <span className="font-semibold uppercase tracking-wide">{t("design_preview.badge")}</span>
          <span className="opacity-80">— {t("design_preview.banner")}</span>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Content-Spalte 768px für Jarvis (docs/referenzen/) — Operator bleibt
              bewusst breiter, ist hier aber nicht betroffen. */}
          <main className="flex-1 overflow-y-auto px-4 md:px-8 py-6 pb-20 md:pb-6 min-w-0">
            <div className="max-w-[768px]">
              <Header title="Jarvis" subtitle="Gestaltungsentwurf — JARVIS-D1, Phase 3" />

              <DesignTokens />

              <section className="mb-10">
                <PreviewJarvisPanel onSelectSource={(source) => setSelected({ type: "source", source })} />
              </section>

              <section>
                <div className="mb-3">
                  <h2 className="text-xl font-semibold text-[var(--text-primary)]">{t("design_preview.actions_title")}</h2>
                  <p className="text-xs text-[var(--text-tertiary)] mt-0.5">{t("design_preview.actions_hint")}</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {SUGGESTED_ACTIONS.map((action, i) => (
                    <PreviewActionCard
                      key={i}
                      action={action}
                      selected={selected?.type === "action" && selected.action === action}
                      onSelect={() => setSelected({ type: "action", action })}
                    />
                  ))}
                </div>
              </section>
            </div>
          </main>

          <aside className="hidden lg:block w-80 shrink-0 border-l border-[var(--border-light)] overflow-y-auto p-5">
            <p className="text-[11px] uppercase tracking-wide text-[var(--text-tertiary)] mb-3">{t("design_preview.detail_title")}</p>
            {!selected && <p className="text-sm text-[var(--text-tertiary)]">{t("design_preview.detail_empty")}</p>}

            {selected?.type === "source" && (
              <div className="space-y-2">
                <p className="text-sm font-mono text-brand-300 break-words">{selected.source.source_file}</p>
                {selected.source.source_heading && (
                  <p className="text-xs text-[var(--text-secondary)]">{selected.source.source_heading}</p>
                )}
                <p className="text-xs text-[var(--text-tertiary)] mt-3 border-t border-[var(--border-light)] pt-3">
                  Beispielhafter Kontextausschnitt — zeigt, wie ein aufgeklappter Quellen-Snippet hier Platz hätte, ohne den Hauptverlauf zu verlängern.
                </p>
              </div>
            )}

            {selected?.type === "action" && (
              <div className="space-y-3">
                <p className="text-sm font-medium text-[var(--text-primary)]">{selected.action.title}</p>
                <p className="text-xs text-[var(--text-secondary)]">{selected.action.description}</p>
                <dl className="text-xs space-y-1.5 pt-2 border-t border-[var(--border-light)]">
                  <div className="flex justify-between gap-2">
                    <dt className="text-[var(--text-tertiary)]">Team</dt>
                    <dd className="text-[var(--text-secondary)] font-mono">{selected.action.team_type}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-[var(--text-tertiary)]">Repo</dt>
                    <dd className="text-[var(--text-secondary)] font-mono">{selected.action.target_repo_name ?? "—"}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-[var(--text-tertiary)]">{t("design_preview.requires_approval")}</dt>
                    <dd className="text-[var(--text-secondary)]">{selected.action.requires_approval ? "Ja" : "Nein"}</dd>
                  </div>
                </dl>
                {selected.action.sources.length > 0 && (
                  <div className="pt-2 border-t border-[var(--border-light)]">
                    <p className="text-[var(--text-tertiary)] mb-1">Quellen</p>
                    <ul className="space-y-0.5">
                      {selected.action.sources.map((s, i) => (
                        <li key={i} className="font-mono text-[var(--text-secondary)] truncate">
                          {s.source_file}
                          {s.source_heading ? ` — ${s.source_heading}` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      </div>

      <MobileNav />
    </div>
  );
}
