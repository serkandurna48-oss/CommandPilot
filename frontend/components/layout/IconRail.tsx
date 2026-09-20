"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { Home, Sparkles, FolderOpen, Activity, Settings } from "lucide-react";

// Fünf globale Ziele (Focus-Deck-Auftrag, Phase 6 gelockt). Home bündelt
// Dashboard/Morning/Plan/Review, Activity bündelt Operator/Work Orders/
// Agent Runs/Review Packages — beide haben in Slice 1 noch keine eigene
// Focus-Deck-Route, die Links zeigen trotzdem auf die echten, heute
// existierenden Routen (dort läuft weiterhin die alte AppShell).
const ICON_NAV_ITEMS = [
  { href: "/dashboard", key: "nav.home" as const, icon: Home },
  { href: "/jarvis", key: "nav.jarvis" as const, icon: Sparkles },
  { href: "/projects", key: "nav.projects" as const, icon: FolderOpen },
  { href: "/operator", key: "nav.activity" as const, icon: Activity },
  { href: "/settings", key: "nav.settings" as const, icon: Settings },
];

// Konvention (Phase 6 Review, Abschnitt 3): nur Jarvis/Projects/Settings
// haben eine 1:1-Route in dieser Liste. Für jede andere heutige Route
// (Morning, Plan, Review, Operator-Detail, Rules, ...) bleibt "Home" aktiv
// markiert — nicht das Jarvis-Icon, auch wenn die Jarvis-Spalte Inhalt
// zeigt. Slice 1 hat nur `/settings` migriert, daher ist hier nur dessen
// Fall real testbar; die Fallback-Logik ist trotzdem vollständig, damit
// spätere Slices sie unverändert übernehmen können.
function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") {
    const knownHrefs = ICON_NAV_ITEMS.map((i) => i.href);
    return !knownHrefs.some((h) => h !== "/dashboard" && (pathname === h || pathname.startsWith(h + "/")));
  }
  return pathname === href || pathname.startsWith(href + "/");
}

export function IconRail() {
  const pathname = usePathname();
  const t = useT();

  return (
    <aside
      className="hidden md:flex flex-col items-center w-16 shrink-0 h-screen sticky top-0 bg-[var(--bg-app)] border-r border-[var(--border-light)] py-4 gap-1"
      aria-label={t("nav.settings")}
    >
      {ICON_NAV_ITEMS.map(({ href, key, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            title={t(key)}
            aria-label={t(key)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center justify-center h-11 w-11 rounded-lg motion-safe:transition-colors",
              "focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[2px] focus-visible:outline-[var(--interactive-border-focus)]",
              active
                ? "bg-[var(--interactive-bg-secondary-selected)] text-brand-400"
                : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--interactive-bg-secondary-hover)]"
            )}
          >
            <Icon className="h-5 w-5 shrink-0" />
          </Link>
        );
      })}
    </aside>
  );
}
