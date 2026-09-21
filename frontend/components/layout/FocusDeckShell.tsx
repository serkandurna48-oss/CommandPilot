"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import { ProtectedRoute } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { isWideWorkspaceRoute } from "@/lib/focusDeckNav";
import { JarvisContextProvider } from "@/lib/jarvisContext";
import { IconRail } from "@/components/layout/IconRail";
import { JarvisRail } from "@/components/layout/JarvisRail";
import { CommandJarvisBar } from "@/components/layout/CommandJarvisBar";
import { FocusDeckMobileNav } from "@/components/layout/FocusDeckMobileNav";
import { MobileJarvisOverlay } from "@/components/layout/MobileJarvisOverlay";

// Interactive Operating System pass: Jarvis is no longer an overlay that
// covers the workspace — opening it REFLOWS the workspace narrower via a
// real width transition on an in-flow flex sibling, so nothing is ever
// covered. Card width stays within the 440-480px target (PANEL_CARD_WIDTH);
// the reserved column adds a small inset on all sides so it reads as a
// floating surface placed in the workspace, not a permanent extension of it.
const PANEL_CARD_WIDTH = 452;
const PANEL_INSET = 12;
const PANEL_COLUMN_WIDTH = PANEL_CARD_WIDTH + PANEL_INSET * 2;

// Exactly one <JarvisRail><JarvisChat/></JarvisRail> tree is ever mounted
// (children of JarvisContextProvider, alongside the workspace children) —
// it never unmounts across open/close, so conversation state, Suggested
// Actions, and Sources are never reset by a shell interaction. On the
// dedicated /jarvis route this panel does not render at all: that route's
// own page content IS the full Jarvis workspace (see app/(app)/jarvis).
export function FocusDeckShell({ children }: { children: React.ReactNode }) {
  const t = useT();
  const pathname = usePathname();
  const [panelOpen, setPanelOpen] = useState(false);
  const [mobileJarvisOpen, setMobileJarvisOpen] = useState(false);
  const wide = isWideWorkspaceRoute(pathname);
  const isJarvisRoute = pathname.startsWith("/jarvis");

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (!isJarvisRoute) setPanelOpen((v) => !v);
      } else if (e.key === "Escape" && panelOpen) {
        setPanelOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [panelOpen, isJarvisRoute]);

  return (
    <ProtectedRoute>
      <JarvisContextProvider onRequestOpen={() => setPanelOpen(true)}>
        <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
          <div className="hidden md:flex min-h-screen relative">
            <IconRail />

            <main className="flex-1 min-w-0 overflow-y-auto relative">
              <div
                className={cn(
                  "px-8 py-8 mx-auto",
                  !isJarvisRoute && "pb-28",
                  isJarvisRoute && "h-full",
                  wide ? "w-full" : "max-w-[1120px]"
                )}
              >
                {children}
              </div>
              {!isJarvisRoute && !panelOpen && <CommandJarvisBar onOpen={() => setPanelOpen(true)} />}
            </main>

            {!isJarvisRoute && (
              <div
                className="shrink-0 h-screen sticky top-0 overflow-hidden motion-safe:transition-[width] duration-200 ease-out"
                style={{ width: panelOpen ? PANEL_COLUMN_WIDTH : 0 }}
                aria-hidden={!panelOpen}
              >
                {/* Fixed inner width regardless of the animating outer
                    wrapper — during the transition it's progressively
                    revealed/clipped by the wrapper's overflow-hidden rather
                    than itself resizing, which keeps its own contents
                    (JarvisChat) from reflowing mid-animation. */}
                <div className="h-full box-border" style={{ width: PANEL_COLUMN_WIDTH, padding: PANEL_INSET }}>
                  <div className="h-full rounded-2xl overflow-hidden shadow-[var(--shadow-float)]">
                    <JarvisRail onClose={() => setPanelOpen(false)} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Mobile: unchanged — fullscreen workspace, bottom nav, Jarvis as a
              global FAB + fullscreen overlay. */}
          <div className="md:hidden min-h-screen pb-20">
            <div className="px-4 py-6">{children}</div>
            <button
              type="button"
              onClick={() => setMobileJarvisOpen(true)}
              title={t("jarvis.open_mobile")}
              aria-label={t("jarvis.open_mobile")}
              className="fixed right-4 bottom-20 z-40 h-14 w-14 rounded-full bg-[var(--interactive-bg-primary-default)] text-white shadow-[0_4px_16px_rgba(0,0,0,0.4)] flex items-center justify-center focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-2 focus-visible:outline-[var(--interactive-border-focus)]"
            >
              <Sparkles className="h-5 w-5" />
            </button>
            <FocusDeckMobileNav />
            <MobileJarvisOverlay open={mobileJarvisOpen} onClose={() => setMobileJarvisOpen(false)} />
          </div>
        </div>
      </JarvisContextProvider>
    </ProtectedRoute>
  );
}
