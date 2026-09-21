"use client";

import { AlertTriangle, Activity, Target, Wrench, CalendarCheck, ListChecks, Rocket, BarChart3, ChevronRight, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { JarvisQuickActionIcon } from "@/lib/jarvisContext";

const ICONS: Record<JarvisQuickActionIcon, typeof Sparkles> = {
  risk: AlertTriangle,
  progress: Activity,
  next_move: Target,
  action: Wrench,
  review: CalendarCheck,
  blocked: ListChecks,
  running: Rocket,
  priority: BarChart3,
  sparkles: Sparkles,
};

// Upgrade from a plain label button: icon + title + short supporting
// description + chevron, so a quick action reads as "here's what this does"
// rather than a bare command. Still just sends a real prompt through the
// existing Jarvis chat endpoint — no new backend behavior.
export function JarvisQuickAction({
  label,
  description,
  icon,
  onClick,
  disabled,
}: {
  label: string;
  description: string;
  icon: JarvisQuickActionIcon;
  onClick: () => void;
  disabled?: boolean;
}) {
  const Icon = ICONS[icon] ?? Sparkles;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "w-full flex items-start gap-3 rounded-xl border border-[var(--border-light)] px-4 py-3 text-left",
        "hover:bg-[var(--interactive-bg-secondary-hover)] hover:border-[var(--border-medium)]",
        "motion-safe:transition-colors duration-150",
        "disabled:opacity-50 disabled:pointer-events-none",
        "focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-2 focus-visible:outline-[var(--interactive-border-focus)]"
      )}
    >
      <span className="flex items-center justify-center h-8 w-8 rounded-full bg-[var(--interactive-bg-primary-default)]/15 text-[var(--text-accent)] shrink-0 mt-0.5">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-[var(--text-primary)] leading-tight">{label}</span>
        <span className="block text-xs text-[var(--text-tertiary)] leading-snug mt-0.5">{description}</span>
      </span>
      <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)] shrink-0 mt-1.5" />
    </button>
  );
}
