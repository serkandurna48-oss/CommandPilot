"use client";

import { Sparkles } from "lucide-react";
import { useJarvisContext } from "@/lib/jarvisContext";
import { JarvisChat } from "@/components/jarvis/JarvisChat";
import { JarvisIntelligenceHeader } from "@/components/jarvis/JarvisIntelligenceHeader";

// Interactive Operating System pass — the dedicated route is now the FULL
// Jarvis workspace: a real header, then JarvisChat (conversation, sources,
// Suggested Actions, composer — all unchanged logic) filling the rest of
// the viewport. No second, redundant Jarvis area — this route doesn't
// render the shell's reflow panel at all (see FocusDeckShell), so this
// page's own content IS the whole experience.
//
// Jarvis Intelligence States pass — reuses the exact same header/snapshot/
// quick-action/answer components as the panel (JarvisRail) and the mobile
// overlay; only the surrounding width differs (max-w-3xl here vs. the
// panel's fixed column).
export default function JarvisPage() {
  const context = useJarvisContext();

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 pb-5 mb-1 border-b border-white/[0.06] shrink-0">
        <span className="flex items-center justify-center h-9 w-9 rounded-full bg-[var(--interactive-bg-primary-default)]/15 text-[var(--text-accent)] shrink-0">
          <Sparkles className="h-4 w-4" />
        </span>
        <JarvisIntelligenceHeader context={context} size="lg" />
      </div>
      <div className="flex-1 min-h-0 max-w-3xl mx-auto w-full pt-2">
        <JarvisChat />
      </div>
    </div>
  );
}
