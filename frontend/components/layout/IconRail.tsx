"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { FOCUS_DECK_NAV_ITEMS, getActiveSection } from "@/lib/focusDeckNav";

function NavIcon({
  href,
  section,
  labelKey,
  icon: Icon,
  active,
  t,
}: {
  href: string;
  section: string;
  labelKey: string;
  icon: (typeof FOCUS_DECK_NAV_ITEMS)[number]["icon"];
  active: boolean;
  t: (key: string) => string;
}) {
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
          ? "bg-brand-500/15 text-brand-400"
          : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--interactive-bg-secondary-hover)]"
      )}
      data-section={section}
    >
      <Icon className="h-5 w-5 shrink-0" />
    </Link>
  );
}

export function IconRail() {
  const pathname = usePathname();
  const t = useT();
  const activeSection = getActiveSection(pathname);
  // First item ("home") lives in its own header band, matching the height
  // of JarvisRail's workspace-switcher band above the Jarvis section label
  // (Visual Fidelity Sprint) — the rest keep their own generously-spaced
  // list below a divider, same as before.
  const [primary, ...rest] = FOCUS_DECK_NAV_ITEMS;

  return (
    <aside
      className="hidden md:flex flex-col items-center w-16 shrink-0 h-screen sticky top-0 bg-[var(--bg-app)] border-r border-[var(--border-light)]"
      aria-label={t("nav.settings")}
    >
      <div className="h-16 flex items-center justify-center border-b border-[var(--border-light)] w-full shrink-0">
        <NavIcon {...primary} active={activeSection === primary.section} t={t} />
      </div>
      <div className="flex flex-col items-center py-4 gap-1.5">
        {rest.map((item) => (
          <NavIcon key={item.href} {...item} active={activeSection === item.section} t={t} />
        ))}
      </div>
    </aside>
  );
}
