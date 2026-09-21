import { Home, Sparkles, FolderOpen, Activity, Settings, type LucideIcon } from "lucide-react";

// Fünf globale Ziele (Focus-Deck-Auftrag, Phase 6 gelockt, Slice 2 global
// verdrahtet). Einzige Quelle für Icon Rail + Mobile Nav + Section-Mapping —
// nicht pro Komponente duplizieren.
export type FocusDeckSection = "home" | "jarvis" | "projects" | "activity" | "settings";

export interface FocusDeckNavItem {
  section: FocusDeckSection;
  href: string;
  labelKey: string;
  icon: LucideIcon;
}

export const FOCUS_DECK_NAV_ITEMS: FocusDeckNavItem[] = [
  { section: "home", href: "/dashboard", labelKey: "nav.home", icon: Home },
  { section: "jarvis", href: "/jarvis", labelKey: "nav.jarvis", icon: Sparkles },
  { section: "projects", href: "/projects", labelKey: "nav.projects", icon: FolderOpen },
  { section: "activity", href: "/operator", labelKey: "nav.activity", icon: Activity },
  { section: "settings", href: "/settings", labelKey: "nav.settings", icon: Settings },
];

// Bündelung der acht echten Routen auf fünf globale Icons (Auftrag "Focus
// Deck Slice 2"): Home = Dashboard/Morning/Plan/Review, Activity =
// Operator/Work Orders, Settings = Settings/Rules. Alles, was hier keiner
// expliziten Regel entspricht, fällt auf "home" zurück — bewusst, damit ein
// künftiger neuer Pfad nie ganz ohne aktive Markierung dasteht.
export function getActiveSection(pathname: string): FocusDeckSection {
  if (pathname.startsWith("/jarvis")) return "jarvis";
  if (pathname.startsWith("/projects")) return "projects";
  if (pathname.startsWith("/operator")) return "activity";
  if (pathname.startsWith("/settings") || pathname.startsWith("/rules")) return "settings";
  return "home";
}

// /dashboard und /operator/[id] liefen unter der alten AppShell mit
// wide=true (volle Breite statt der ~896px-Lesebreite). Über den Pfad
// bestimmt, nicht pro Page übergeben — eine Quelle für den Shell-State,
// kein doppelt gehaltenes Flag.
export function isWideWorkspaceRoute(pathname: string): boolean {
  if (pathname === "/dashboard") return true;
  if (pathname.startsWith("/operator/") && pathname !== "/operator/new") return true;
  // Visual Fidelity Sprint (Higgsfield Focus-Deck-Referenz): Settings nutzt
  // dort die volle Workspace-Breite statt der ~896px-Lesebreite — die Seite
  // setzt selbst noch ein eigenes, etwas engeres max-w auf ihren Karten.
  if (pathname === "/settings") return true;
  // Interactive Operating System pass: Projects became a two-column control
  // surface (scannable list + detail panel) — needs the same full width as
  // the other control-surface routes, not the ~896px reading column.
  if (pathname === "/projects") return true;
  // The dedicated Jarvis route is the one place Jarvis gets the large,
  // permanently-open workspace experience (Interactive Operating System
  // pass) — its own content still caps conversation line-length internally.
  if (pathname.startsWith("/jarvis")) return true;
  return false;
}
