"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Sunrise, Moon, Sliders, Settings } from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Home",     icon: LayoutDashboard },
  { href: "/morning",   label: "Morning",  icon: Sunrise },
  { href: "/review",    label: "Review",   icon: Moon },
  { href: "/rules",     label: "Rules",    icon: Sliders },
  { href: "/settings",  label: "Settings", icon: Settings },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-slate-900 border-t border-slate-800">
      <div className="flex items-center justify-around px-2 py-2">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-xs transition-colors",
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
