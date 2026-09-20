"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { FOCUS_DECK_NAV_ITEMS, getActiveSection } from "@/lib/focusDeckNav";

export function IconRail() {
  const pathname = usePathname();
  const t = useT();
  const activeSection = getActiveSection(pathname);

  return (
    <aside
      className="hidden md:flex flex-col items-center w-16 shrink-0 h-screen sticky top-0 bg-[var(--bg-app)] border-r border-[var(--border-light)] py-4 gap-1"
      aria-label={t("nav.settings")}
    >
      {FOCUS_DECK_NAV_ITEMS.map(({ href, section, labelKey, icon: Icon }) => {
        const active = activeSection === section;
        return (
          <Link
            key={href}
            href={href}
            title={t(labelKey)}
            aria-label={t(labelKey)}
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
