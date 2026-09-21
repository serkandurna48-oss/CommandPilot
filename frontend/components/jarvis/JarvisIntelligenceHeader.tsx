"use client";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { JarvisContextInfo } from "@/lib/jarvisContext";

// The entity title is the point of this header — "Jarvis" is fixed chrome,
// the kicker just names what bucket we're in. Reused everywhere Jarvis's
// current context is shown (JarvisRail, the dedicated /jarvis page,
// MobileJarvisOverlay) so the three surfaces never drift into different
// wording for the same real context.
export function JarvisIntelligenceHeader({
  context,
  size = "md",
  className,
}: {
  context: JarvisContextInfo;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const t = useT();

  return (
    <div className={cn("min-w-0", className)}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] truncate">
        {context.kicker}
      </p>
      <p className="text-[11px] text-[var(--text-tertiary)] leading-tight">{t("jarvis.title")}</p>
      <p
        className={cn(
          "font-serif text-[var(--text-primary)] leading-tight truncate",
          size === "lg" && "text-xl mt-0.5",
          size === "md" && "text-base",
          size === "sm" && "text-sm"
        )}
      >
        {context.title}
      </p>
    </div>
  );
}
