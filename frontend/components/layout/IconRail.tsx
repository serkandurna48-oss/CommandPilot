"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { FOCUS_DECK_NAV_ITEMS, getActiveSection } from "@/lib/focusDeckNav";

// Restrained active state (Visual Polish Pass): a slim accent bar + tinted
// icon reads as "current section" without the heavier full-bronze-fill block
// this used to be — bronze stays reserved for the one bar, not the surface.
const activeClass = "bg-[var(--bg-elevated)] text-[var(--text-accent)]";
const inactiveClass = "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover-surface)]";
const iconButtonClass = "flex items-center justify-center h-10 w-10 rounded-xl motion-safe:transition-colors duration-150 focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[2px] focus-visible:outline-[var(--interactive-border-focus)]";

// Full-workspace shell: Jarvis quick access lives in the global
// CommandJarvisBar (opens the right-side reflow panel from anywhere), so
// this rail item is a plain link to the dedicated /jarvis route — no
// toggle state, no special-casing, same as every other item.
export function IconRail() {
  const pathname = usePathname();
  const t = useT();
  const activeSection = getActiveSection(pathname);

  return (
    <aside
      className="hidden md:flex flex-col items-center w-16 shrink-0 h-screen sticky top-0 bg-[var(--bg-app)] pt-6 gap-3"
      aria-label={t("nav.settings")}
    >
      {FOCUS_DECK_NAV_ITEMS.map((item) => {
        const active = activeSection === item.section;
        return (
          <Link
            key={item.href}
            href={item.href}
            title={t(item.labelKey)}
            aria-label={t(item.labelKey)}
            aria-current={active ? "page" : undefined}
            className={cn("relative", iconButtonClass, active ? activeClass : inactiveClass)}
            data-section={item.section}
          >
            {active && (
              <span className="absolute -left-3 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-[var(--interactive-bg-primary-default)]" />
            )}
            <item.icon className="h-[18px] w-[18px] shrink-0" />
          </Link>
        );
      })}
    </aside>
  );
}
