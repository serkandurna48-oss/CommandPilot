"use client";

import { Sparkles, X } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useJarvisContext } from "@/lib/jarvisContext";
import { JarvisChat } from "@/components/jarvis/JarvisChat";
import { JarvisIntelligenceHeader } from "@/components/jarvis/JarvisIntelligenceHeader";

interface JarvisRailProps {
  onClose: () => void;
}

// Wraps the UNCHANGED JarvisChat component — no conversation-logic changes,
// only chrome: a header showing what Jarvis currently has in context (JARVIS
// route/entity, Interactive Operating System pass) and a close control.
// Jarvis Intelligence States pass — the entity title (JarvisIntelligenceHeader)
// is now visually stronger than the generic "Jarvis" label, per-context.
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
        <div className="flex items-center gap-2.5 min-w-0">
          <Sparkles className="h-4 w-4 text-[var(--text-accent)] shrink-0" />
          <JarvisIntelligenceHeader context={context} size="md" />
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
