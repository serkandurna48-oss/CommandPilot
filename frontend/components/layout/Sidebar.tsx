"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import {
  LayoutDashboard,
  Sunrise,
  Moon,
  FolderOpen,
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
    { href: "/projects",  label: t("nav.projects"),  icon: FolderOpen },
    { href: "/rules",     label: t("nav.rules"),     icon: Sliders },
    { href: "/settings",  label: t("nav.settings"),  icon: Settings },
  ];

  return (
    <aside className="hidden md:flex flex-col w-56 bg-slate-950 border-r border-slate-800/50 min-h-screen">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-slate-800/50">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-md bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center drop-shadow-[0_0_12px_rgba(99,102,241,0.18)]">
            <span className="text-white text-xs font-bold tracking-tight">CP</span>
          </div>
          <span className="text-slate-200 font-semibold text-sm tracking-tight">CommandPilot</span>
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
                "flex items-center gap-3 py-2.5 rounded-lg text-[13px] transition-all",
                active
                  ? "bg-gradient-to-r from-brand-600/18 to-transparent text-brand-300 font-medium border-l-2 border-brand-500/70 pl-[10px] pr-3"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 border-l-2 border-transparent pl-[10px] pr-3"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", active ? "text-brand-400" : "text-slate-600")} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div className="px-4 py-4 border-t border-slate-800/50">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500/60 shrink-0" />
          <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-600">
            System Online
          </p>
        </div>
        <p className="text-[9px] text-slate-600 font-mono pl-3.5 tracking-wider">
          Private OS · v0.1
        </p>
      </div>
    </aside>
  );
}
