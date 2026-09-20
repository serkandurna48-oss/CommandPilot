"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { FOCUS_DECK_NAV_ITEMS, getActiveSection } from "@/lib/focusDeckNav";

export function FocusDeckMobileNav() {
  const pathname = usePathname();
  const t = useT();
  const activeSection = getActiveSection(pathname);

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[var(--bg-app)] border-t border-[var(--border-light)] pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center justify-around px-2 py-2">
        {FOCUS_DECK_NAV_ITEMS.map(({ href, section, labelKey, icon: Icon }) => {
          const active = activeSection === section;
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
              <span>{t(labelKey)}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
