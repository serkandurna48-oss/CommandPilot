"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { LayoutDashboard, Sunrise, Moon, FolderOpen, Sliders, Settings } from "lucide-react";

export function MobileNav() {
  const pathname = usePathname();
  const t = useT();

  const navItems = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
    { href: "/morning",   label: t("nav.morning"),   icon: Sunrise },
    { href: "/review",    label: t("nav.review"),    icon: Moon },
    { href: "/projects",  label: t("nav.projects"),  icon: FolderOpen },
    { href: "/rules",     label: t("nav.rules"),     icon: Sliders },
    { href: "/settings",  label: t("nav.settings"),  icon: Settings },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-slate-900 border-t border-slate-800 pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center justify-around px-2 py-2">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 px-3 py-1.5 min-h-11 rounded-lg text-xs transition-colors active:scale-95 active:text-slate-200",
                active
                  ? "text-brand-400"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
