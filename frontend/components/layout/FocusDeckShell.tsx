"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import { ProtectedRoute } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { isWideWorkspaceRoute } from "@/lib/focusDeckNav";
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

// Globale, authentifizierte Shell (Slice 2: jetzt von einem einzigen
// gemeinsamen Layout — app/(app)/layout.tsx — für ALLE App-Routen genutzt,
// nicht mehr nur /settings). Genau EINE FocusDeckShell-Instanz bleibt über
// Routenwechsel hinweg gemountet, weil Next.js Layouts bei
// Geschwister-Routen nicht neu mountet — das ist der ganze Mechanismus
// hinter "Jarvis wird nicht unnötig remounted", kein Extra-State-Manager
// nötig. State-Ownership (siehe auch Implementierungsplan):
//   - Jarvis-Konversation: lebt in JarvisChat selbst, bleibt erhalten, weil
//     JarvisChat hier nie unmountet (nur CSS "hidden" im collapsed-State).
//   - Jarvis Layout-State (collapsed/normal/expanded): lebt HIER, einmalig,
//     nicht pro Route.
//   - Mobile-Jarvis-Overlay offen/zu: lebt HIER, einmalig.
//   - Aktiver Navigationsbereich: wird NICHT als State gehalten, sondern
//     direkt aus der URL (usePathname) abgeleitet — siehe lib/focusDeckNav.
export function FocusDeckShell({ children }: { children: React.ReactNode }) {
  const t = useT();
  const pathname = usePathname();
  const [jarvisState, setJarvisState] = useState<JarvisRailState>("normal");
  const [mobileJarvisOpen, setMobileJarvisOpen] = useState(false);
  const wide = isWideWorkspaceRoute(pathname);

  // Auf /jarvis darf der Bereich sinnvoll expanded sein (eigener Auftrag) —
  // ein Default beim ANKOMMEN auf der Route, keine erzwungene Sperre.
  // Danach bleibt es normaler State: der Mensch darf jederzeit wieder
  // verkleinern, ohne dass ein erneuter Render das zurücksetzt.
  const lastAutoExpandedFor = useRef<string | null>(null);
  useEffect(() => {
    if (pathname.startsWith("/jarvis") && lastAutoExpandedFor.current !== pathname) {
      lastAutoExpandedFor.current = pathname;
      setJarvisState("expanded");
    }
  }, [pathname]);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
        {/* Desktop: echter Grid-Layout-State, kein Overlay. Icon Rail und
            Jarvis Rail bleiben immer gemountet — nur die mittlere
            Spaltenbreite ändert sich, Workspace verliert nie seinen
            Zustand (kein Unmount irgendeiner Spalte, keine Remounts beim
            Routenwechsel innerhalb dieser Shell). */}
        <div
          className="hidden md:grid min-h-screen motion-safe:transition-[grid-template-columns] duration-200 ease-out"
          style={{ gridTemplateColumns: `64px ${JARVIS_RAIL_WIDTH[jarvisState]} 1fr` }}
        >
          <IconRail />
          <JarvisRail state={jarvisState} onStateChange={setJarvisState} />
          <main className="min-w-0 overflow-y-auto">
            {/* Links am Workspace-Gutter ausgerichtet, nicht zentriert —
                Jarvis Rail und Workspace sollen wie ein zusammenhängendes
                System wirken. "wide" (Dashboard, Work-Order-Detail) nutzt
                die volle Breite wie zuvor unter der alten AppShell. */}
            <div className={cn("px-8 py-8", wide ? "w-full" : "max-w-4xl")}>{children}</div>
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
