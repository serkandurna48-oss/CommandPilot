"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { Home, Sparkles, FolderOpen, Activity, Settings } from "lucide-react";

// Fünf globale Ziele, identisch zu components/layout/IconRail.tsx — Focus
// Deck hat auf Mobile dieselbe Navigationsstruktur wie auf Desktop, nur
// mit sichtbaren Textlabeln (Design-System-Board, Mobile-Blatt).
const NAV_ITEMS = [
  { href: "/dashboard", key: "nav.home" as const, icon: Home },
  { href: "/jarvis", key: "nav.jarvis" as const, icon: Sparkles },
  { href: "/projects", key: "nav.projects" as const, icon: FolderOpen },
  { href: "/operator", key: "nav.activity" as const, icon: Activity },
  { href: "/settings", key: "nav.settings" as const, icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") {
    const knownHrefs = NAV_ITEMS.map((i) => i.href);
    return !knownHrefs.some((h) => h !== "/dashboard" && (pathname === h || pathname.startsWith(h + "/")));
  }
  return pathname === href || pathname.startsWith(href + "/");
}

export function FocusDeckMobileNav() {
  const pathname = usePathname();
  const t = useT();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[var(--bg-app)] border-t border-[var(--border-light)] pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center justify-around px-2 py-2">
        {NAV_ITEMS.map(({ href, key, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 px-3 py-1.5 min-h-11 min-w-11 rounded-lg text-xs motion-safe:transition-colors active:scale-95",
                "focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--interactive-border-focus)]",
                active ? "text-brand-400" : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span>{t(key)}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
