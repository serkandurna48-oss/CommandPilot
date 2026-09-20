"use client";

import { Sparkles, Maximize2, Minimize2, PanelLeftClose } from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { JarvisChat } from "@/components/jarvis/JarvisChat";

export type JarvisRailState = "collapsed" | "normal" | "expanded";

interface JarvisRailProps {
  state: JarvisRailState;
  onStateChange: (state: JarvisRailState) => void;
}

// Desktop-Jarvis-Rail (Focus-Deck-Auftrag, Slice 1): permanente Spalte,
// drei Layout-States. Wrappt die UNVERÄNDERTE JarvisChat-Komponente — keine
// Logikänderung, nur eine neue Umgebung. JarvisChat bleibt bei jedem
// State-Wechsel gemountet (nur CSS "hidden" im collapsed-Zustand), damit
// Konversations-/Eingabe-Zustand nicht verloren geht.
export function JarvisRail({ state, onStateChange }: JarvisRailProps) {
  const t = useT();

  return (
    <div className="h-screen sticky top-0 flex flex-col bg-[var(--bg-surface)]/40 border-r border-[var(--border-light)] overflow-hidden">
      <div className="flex items-center justify-between px-3 py-3 border-b border-[var(--border-light)] shrink-0">
        <div className={cn("flex items-center gap-2 min-w-0", state === "collapsed" && "justify-center w-full")}>
          <Sparkles className="h-4 w-4 text-brand-400 shrink-0" />
          {state !== "collapsed" && (
            <span className="text-sm font-medium text-[var(--text-primary)] truncate">{t("jarvis.title")}</span>
          )}
        </div>

        {/* Nur die Aktion(en), die vom jeweiligen State aus Sinn ergeben —
            unterschiedliche Icon-Familien statt zweier ähnlich aussehender
            Chevron-Varianten, damit die Bedeutung eindeutig ist. */}
        {state === "normal" && (
          <div className="flex items-center gap-0.5 shrink-0">
            <button
              type="button"
              onClick={() => onStateChange("expanded")}
              title={t("jarvis.expand")}
              aria-label={t("jarvis.expand")}
              className="p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => onStateChange("collapsed")}
              title={t("jarvis.collapse")}
              aria-label={t("jarvis.collapse")}
              className="p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>
        )}
        {state === "expanded" && (
          <button
            type="button"
            onClick={() => onStateChange("normal")}
            title={t("jarvis.restore")}
            aria-label={t("jarvis.restore")}
            className="p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)] shrink-0"
          >
            <Minimize2 className="h-4 w-4" />
          </button>
        )}
      </div>

      {state === "collapsed" ? (
        <button
          type="button"
          onClick={() => onStateChange("normal")}
          title={t("jarvis.expand")}
          aria-label={t("jarvis.expand")}
          className="flex-1 flex items-start justify-center pt-4 text-[var(--text-tertiary)] hover:text-brand-400 motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
        >
          <Sparkles className="h-4 w-4" />
        </button>
      ) : (
        <div className="flex-1 min-h-0 overflow-hidden px-3 pb-3">
          <JarvisChat />
        </div>
      )}
    </div>
  );
}
