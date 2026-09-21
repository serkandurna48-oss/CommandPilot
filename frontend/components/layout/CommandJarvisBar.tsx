"use client";

import { Sparkles, ArrowRight } from "lucide-react";
import { useT } from "@/lib/i18n";

interface CommandJarvisBarProps {
  onOpen: () => void;
}

// The primary Jarvis affordance (Interactive Operating System pass) — a
// persistent, restrained system command bar, not a giant input field. Desktop
// only; mobile keeps its existing FAB + fullscreen overlay.
export function CommandJarvisBar({ onOpen }: CommandJarvisBarProps) {
  const t = useT();

  return (
    <button
      type="button"
      onClick={onOpen}
      className="hidden md:flex fixed bottom-6 left-1/2 -translate-x-1/2 z-40 items-center gap-3 w-[min(700px,calc(100vw_-_7rem))] rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] px-4 py-2.5 text-left shadow-[var(--shadow-float)] hover:border-[var(--interactive-bg-primary-default)] motion-safe:transition-colors duration-150 focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-2 focus-visible:outline-[var(--interactive-border-focus)]"
    >
      <span className="flex items-center justify-center h-8 w-8 rounded-full bg-[var(--interactive-bg-primary-default)]/15 text-[var(--text-accent)] shrink-0">
        <Sparkles className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-[var(--text-primary)] leading-tight">
          {t("jarvis.command_bar.title")}
        </span>
        <span className="block text-xs text-[var(--text-tertiary)] truncate leading-tight">
          {t("jarvis.command_bar.subtitle")}
        </span>
      </span>
      <span className="flex items-center justify-center h-8 w-8 rounded-full bg-[var(--interactive-bg-primary-default)] text-white shrink-0">
        <ArrowRight className="h-4 w-4" />
      </span>
    </button>
  );
}
