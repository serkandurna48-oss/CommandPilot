"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { useT } from "@/lib/i18n";

// Interactive Operating System pass — Jarvis needs to know what the user is
// looking at without inventing backend intelligence: this is purely a
// frontend model of "what page/entity is currently in view," built from
// data pages already have. It never talks to the backend by itself; a
// quick action's *prompt* is just a normal, real-data chat message sent
// through the existing /api/jarvis/chat endpoint (see JarvisChat.tsx).
export interface JarvisQuickAction {
  label: string;
  prompt: string;
}

export interface JarvisContextInfo {
  route: string;
  entityType?: "project" | "work_order" | "plan";
  entityId?: string;
  title: string;
  summary: string;
  quickActions: JarvisQuickAction[];
}

// Route-level fallback, shown until a page pushes something more specific
// (e.g. ProjectsManager selecting one project). Translated via i18n since
// it's fixed UI chrome, unlike entity-specific context below which quotes
// real record data and can't be pre-translated.
function useDefaultContextForPath(pathname: string): JarvisContextInfo {
  const t = useT();

  if (pathname.startsWith("/projects")) {
    return {
      route: "projects",
      title: t("jarvis.context.projects.title"),
      summary: t("jarvis.context.projects.summary"),
      quickActions: [
        { label: t("jarvis.suggestion.1"), prompt: t("jarvis.suggestion.1") },
        { label: t("jarvis.qa.show_risks"), prompt: t("jarvis.qa.show_risks") + "?" },
        { label: t("jarvis.qa.prioritize_projects"), prompt: t("jarvis.qa.prioritize_projects") + "." },
      ],
    };
  }
  if (pathname.startsWith("/operator")) {
    return {
      route: "operator",
      title: t("jarvis.context.operator.title"),
      summary: t("jarvis.context.operator.summary"),
      quickActions: [
        { label: t("jarvis.qa.check_blocked"), prompt: t("jarvis.qa.check_blocked") + "." },
        { label: t("jarvis.qa.summarize_running"), prompt: t("jarvis.qa.summarize_running") + "." },
      ],
    };
  }
  if (pathname.startsWith("/plans") || pathname === "/morning" || pathname === "/review") {
    return {
      route: "daily_plan",
      title: t("jarvis.context.daily_plan.title"),
      summary: t("jarvis.context.daily_plan.summary"),
      quickActions: [
        { label: t("jarvis.qa.review_today"), prompt: t("jarvis.qa.review_today") + "." },
        { label: t("jarvis.suggestion.3"), prompt: t("jarvis.suggestion.3") },
      ],
    };
  }
  if (pathname.startsWith("/settings") || pathname.startsWith("/rules")) {
    return {
      route: "settings",
      title: t("jarvis.context.settings.title"),
      summary: t("jarvis.context.settings.summary"),
      quickActions: [],
    };
  }
  return {
    route: "home",
    title: t("jarvis.context.home.title"),
    summary: t("jarvis.context.home.summary"),
    quickActions: [
      { label: t("jarvis.qa.review_today"), prompt: t("jarvis.qa.review_today") + "." },
      { label: t("jarvis.qa.check_blocked"), prompt: t("jarvis.qa.check_blocked") + "." },
      { label: t("jarvis.qa.prioritize_projects"), prompt: t("jarvis.qa.prioritize_projects") + "." },
      { label: t("jarvis.suggestion.3"), prompt: t("jarvis.suggestion.3") },
    ],
  };
}

interface JarvisContextOverride {
  pathname: string;
  ctx: JarvisContextInfo;
}

interface JarvisContextValue {
  setOverride: (pathname: string, ctx: JarvisContextInfo | null) => void;
  openPanel: () => void;
}

const Ctx = createContext<JarvisContextValue | null>(null);
const ContextInfoCtx = createContext<JarvisContextInfo | null>(null);

export function JarvisContextProvider({
  children,
  onRequestOpen,
}: {
  children: React.ReactNode;
  // Wired by FocusDeckShell to its own panel-open state — lets a page (e.g.
  // "Ask Jarvis about this project") open the panel without the shell
  // exposing that state directly. No-op if omitted (e.g. in tests).
  onRequestOpen?: () => void;
}) {
  const pathname = usePathname();
  const [override, setOverrideState] = useState<JarvisContextOverride | null>(null);
  const defaultContext = useDefaultContextForPath(pathname);

  const setOverride = useCallback((path: string, ctx: JarvisContextInfo | null) => {
    setOverrideState((prev) => {
      if (ctx === null) {
        return prev && prev.pathname === path ? null : prev;
      }
      if (prev && prev.pathname === path && prev.ctx === ctx) return prev;
      return { pathname: path, ctx };
    });
  }, []);

  const context = useMemo(
    () => (override && override.pathname === pathname ? override.ctx : defaultContext),
    [override, pathname, defaultContext]
  );

  const actions = useMemo(
    () => ({ setOverride, openPanel: onRequestOpen ?? (() => {}) }),
    [setOverride, onRequestOpen]
  );

  return (
    <Ctx.Provider value={actions}>
      <ContextInfoCtx.Provider value={context}>{children}</ContextInfoCtx.Provider>
    </Ctx.Provider>
  );
}

export function useJarvisContext(): JarvisContextInfo {
  const ctx = useContext(ContextInfoCtx);
  if (!ctx) throw new Error("useJarvisContext must be used within JarvisContextProvider");
  return ctx;
}

// Pages call this to push entity-specific context (e.g. a selected project
// or an open work order). Pass a memoized `ctx` (useMemo keyed on the real
// entity fields) — its identity is the update signal, and a fresh object
// every render would otherwise re-push on every render. Pass null to clear
// (e.g. when nothing is selected); unmounting clears it automatically.
export function useSetJarvisContext(ctx: JarvisContextInfo | null) {
  const pathname = usePathname();
  const provider = useContext(Ctx);
  if (!provider) throw new Error("useSetJarvisContext must be used within JarvisContextProvider");
  const { setOverride } = provider;

  useEffect(() => {
    setOverride(pathname, ctx);
    return () => setOverride(pathname, null);
  }, [pathname, ctx, setOverride]);
}

// Lets a page open the Jarvis panel itself (e.g. an "Ask Jarvis about this
// project" button) without the shell exposing its open/close state directly.
export function useJarvisPanelControl(): { openPanel: () => void } {
  const provider = useContext(Ctx);
  if (!provider) throw new Error("useJarvisPanelControl must be used within JarvisContextProvider");
  return { openPanel: provider.openPanel };
}
