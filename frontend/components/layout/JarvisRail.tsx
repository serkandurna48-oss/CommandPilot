"use client";

import { Sparkles, X } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useJarvisContext } from "@/lib/jarvisContext";
import { JarvisChat } from "@/components/jarvis/JarvisChat";

interface JarvisRailProps {
  onClose: () => void;
}

// Wraps the UNCHANGED JarvisChat component — no conversation-logic changes,
// only chrome: a header showing what Jarvis currently has in context (JARVIS
// route/entity, Interactive Operating System pass) and a close control.
export function JarvisRail({ onClose }: JarvisRailProps) {
  const t = useT();
  const context = useJarvisContext();

  return (
    <div
      className="h-full flex flex-col overflow-hidden"
      style={{
        background: "linear-gradient(180deg, color-mix(in srgb, var(--bg-surface) 92%, var(--interactive-bg-primary-default) 8%), var(--bg-app))",
      }}
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles className="h-4 w-4 text-[var(--text-accent)] shrink-0" />
          <div className="min-w-0">
            <span className="block text-sm font-medium text-[var(--text-primary)] leading-tight truncate">{t("jarvis.title")}</span>
            <span className="block text-[11px] text-[var(--text-tertiary)] leading-tight truncate">{context.title}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          title={t("jarvis.close")}
          aria-label={t("jarvis.close")}
          className="flex items-center justify-center h-8 w-8 rounded-full shrink-0 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover-surface)] motion-safe:transition-colors duration-150 focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden px-3 pb-3">
        <JarvisChat />
      </div>
    </div>
  );
}
