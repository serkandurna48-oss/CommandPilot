"use client";

import { X } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useJarvisContext } from "@/lib/jarvisContext";
import { JarvisChat } from "@/components/jarvis/JarvisChat";
import { JarvisIntelligenceHeader } from "@/components/jarvis/JarvisIntelligenceHeader";

interface MobileJarvisOverlayProps {
  open: boolean;
  onClose: () => void;
}

// Mobile Jarvis = Fullscreen/Overlay (Focus-Deck-Auftrag, gelockt) statt
// permanenter Spalte wie auf Desktop. Wrappt die unveränderte JarvisChat —
// bleibt gemountet, nur per CSS ausgeblendet, damit ein Gespräch beim
// Schließen/Wiederöffnen nicht verloren geht. Jarvis Intelligence States
// pass: same header component as desktop (JarvisRail), compact size —
// mobile gets the same real context, not a stripped-down version.
export function MobileJarvisOverlay({ open, onClose }: MobileJarvisOverlayProps) {
  const t = useT();
  const context = useJarvisContext();

  return (
    <div
      className={
        open
          ? "md:hidden fixed inset-x-0 top-0 bottom-16 z-50 bg-[var(--bg-app)] flex flex-col"
          : "hidden"
      }
      role="dialog"
      aria-modal="true"
      aria-label={t("jarvis.title")}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-light)] shrink-0">
        <JarvisIntelligenceHeader context={context} size="sm" />
        <button
          type="button"
          onClick={onClose}
          title={t("jarvis.close")}
          aria-label={t("jarvis.close")}
          className="p-2 -mr-2 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden px-4 pb-4">
        <JarvisChat />
      </div>
    </div>
  );
}
