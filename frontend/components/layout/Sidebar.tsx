"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import {
  LayoutDashboard,
  Sunrise,
  FileText,
  Moon,
  Sliders,
  Settings,
} from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const t = useT();

  const navItems = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
    { href: "/morning",   label: t("nav.morning"),   icon: Sunrise },
    { href: "/review",    label: t("nav.review"),    icon: Moon },
    { href: "/rules",     label: t("nav.rules"),     icon: Sliders },
    { href: "/settings",  label: t("nav.settings"),  icon: Settings },
  ];

  return (
    <aside className="hidden md:flex flex-col w-56 bg-slate-900 border-r border-slate-800 min-h-screen">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-800">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-md bg-brand-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">CP</span>
          </div>
          <span className="text-slate-100 font-semibold text-sm">CommandPilot</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                active
                  ? "bg-brand-600/20 text-brand-400 font-medium"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-800">
        <p className="text-xs text-slate-600">v0.1.0</p>
      </div>
    </aside>
  );
}
