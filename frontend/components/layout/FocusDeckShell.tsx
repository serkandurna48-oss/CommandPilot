"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { ProtectedRoute } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { IconRail } from "@/components/layout/IconRail";
import { JarvisRail, type JarvisRailState } from "@/components/layout/JarvisRail";
import { FocusDeckMobileNav } from "@/components/layout/FocusDeckMobileNav";
import { MobileJarvisOverlay } from "@/components/layout/MobileJarvisOverlay";

// Spaltenbreiten pro Jarvis-Layout-State (Focus-Deck-Auftrag, Phase 7 Plan
// Abschnitt 6 "State Ownership"). Feste px-Werte statt Prozent, damit die
// Lesebreite auf sehr breiten Screens nicht ausufert — CSS Grid Template
// Columns, wie im Implementierungsplan als bevorzugte Richtung festgelegt.
const JARVIS_RAIL_WIDTH: Record<JarvisRailState, string> = {
  collapsed: "64px",
  normal: "380px",
  expanded: "640px",
};

// Neue, parallel zur bestehenden AppShell existierende Shell (kontrollierter
// Migrationszustand, Slice 1 nutzt sie ausschließlich für /settings).
// [Icon Rail] [Jarvis Rail] [Workspace] auf Desktop, Workspace-Vollbild +
// Bottom-Nav + Jarvis-Fullscreen-Overlay auf Mobile.
export function FocusDeckShell({ children }: { children: React.ReactNode }) {
  const t = useT();
  const [jarvisState, setJarvisState] = useState<JarvisRailState>("normal");
  const [mobileJarvisOpen, setMobileJarvisOpen] = useState(false);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
        {/* Desktop: echter Grid-Layout-State, kein Overlay. Icon Rail und
            Jarvis Rail bleiben immer gemountet — nur die mittlere
            Spaltenbreite ändert sich, Workspace verliert nie seinen
            Zustand (kein Unmount irgendeiner Spalte). */}
        <div
          className="hidden md:grid min-h-screen motion-safe:transition-[grid-template-columns] duration-200 ease-out"
          style={{ gridTemplateColumns: `64px ${JARVIS_RAIL_WIDTH[jarvisState]} 1fr` }}
        >
          <IconRail />
          <JarvisRail state={jarvisState} onStateChange={setJarvisState} />
          <main className="min-w-0 overflow-y-auto">
            {/* Links am Workspace-Gutter ausgerichtet, nicht zentriert —
                Jarvis Rail und Workspace sollen wie ein zusammenhängendes
                System wirken, nicht wie zwei getrennte Blöcke. Max-width
                bleibt als Lesebreiten-Grenze, aber ohne mx-auto. */}
            <div className="max-w-2xl px-8 py-8">{children}</div>
          </main>
        </div>

        {/* Mobile: Workspace Vollbild, Bottom-Nav, Jarvis als globaler FAB +
            Fullscreen-Overlay statt gequetschter Drei-Spalten-Ansicht. */}
        <div className="md:hidden min-h-screen pb-20">
          <div className="px-4 py-6">{children}</div>
          <button
            type="button"
            onClick={() => setMobileJarvisOpen(true)}
            title={t("jarvis.open_mobile")}
            aria-label={t("jarvis.open_mobile")}
            className="fixed right-4 bottom-20 z-40 h-14 w-14 rounded-full bg-[var(--interactive-bg-primary-default)] text-white shadow-[0_4px_16px_rgba(0,0,0,0.4)] flex items-center justify-center focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-2 focus-visible:outline-[var(--interactive-border-focus)]"
          >
            <Sparkles className="h-5 w-5" />
          </button>
          <FocusDeckMobileNav />
          <MobileJarvisOverlay open={mobileJarvisOpen} onClose={() => setMobileJarvisOpen(false)} />
        </div>
      </div>
    </ProtectedRoute>
  );
}
