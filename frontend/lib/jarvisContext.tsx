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
//
// Jarvis Intelligence States pass — this model grew two more fields that
// stay strictly presentation-only, never fabricated: `kicker` (what the
// panel's header names as currently in view) and `snapshot` (a compact list
// of real structured fields, shown before conversation starts — see
// JarvisContextSnapshot). Both are omitted rather than invented when there's
// no real data to back them.
export type JarvisQuickActionIcon =
  | "risk"
  | "progress"
  | "next_move"
  | "action"
  | "review"
  | "blocked"
  | "running"
  | "priority"
  | "sparkles";

export interface JarvisQuickAction {
  label: string;
  description: string;
  prompt: string;
  icon: JarvisQuickActionIcon;
  // Shown uppercased while the request for this action is in flight (e.g.
  // "Analyzing risks…") and as the small mode label above the resulting
  // answer (e.g. "Risk analysis"). Optional: actions without these fall back
  // to the generic "Thinking..." state and a plain "Jarvis" answer label —
  // never a fabricated mode name.
  workingLabel?: string;
  resultLabel?: string;
}

export interface JarvisSnapshotField {
  label: string;
  value: string;
}

export interface JarvisContextInfo {
  route: string;
  entityType?: "project" | "work_order" | "plan";
  entityId?: string;
  kicker: string;
  title: string;
  summary: string;
  snapshot?: JarvisSnapshotField[];
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
      kicker: t("jarvis.kicker.projects_none"),
      title: t("jarvis.context.projects.title"),
      summary: t("jarvis.context.projects.summary"),
      quickActions: [
        { label: t("jarvis.suggestion.1"), prompt: t("jarvis.suggestion.1"), description: t("jarvis.suggestion.1_desc"), icon: "review" },
        { label: t("jarvis.qa.show_risks"), prompt: t("jarvis.qa.show_risks") + "?", description: t("jarvis.qa.show_risks_desc"), icon: "risk" },
        {
          label: t("jarvis.qa.prioritize_projects"),
          prompt: t("jarvis.qa.prioritize_projects") + ".",
          description: t("jarvis.qa.prioritize_projects_desc"),
          icon: "priority",
          workingLabel: t("jarvis.qa.prioritize_projects_working"),
          resultLabel: t("jarvis.qa.prioritize_projects_result"),
        },
      ],
    };
  }
  if (pathname.startsWith("/operator")) {
    return {
      route: "operator",
      kicker: t("jarvis.kicker.operator"),
      title: t("jarvis.context.operator.title"),
      summary: t("jarvis.context.operator.summary"),
      quickActions: [
        { label: t("jarvis.qa.check_blocked"), prompt: t("jarvis.qa.check_blocked") + ".", description: t("jarvis.qa.check_blocked_desc"), icon: "blocked" },
        { label: t("jarvis.qa.summarize_running"), prompt: t("jarvis.qa.summarize_running") + ".", description: t("jarvis.qa.summarize_running_desc"), icon: "running" },
      ],
    };
  }
  if (pathname.startsWith("/plans") || pathname === "/morning" || pathname === "/review") {
    return {
      route: "daily_plan",
      kicker: t("jarvis.kicker.daily_plan"),
      title: t("jarvis.context.daily_plan.title"),
      summary: t("jarvis.context.daily_plan.summary"),
      quickActions: [
        {
          label: t("jarvis.qa.review_today"),
          prompt: t("jarvis.qa.review_today") + ".",
          description: t("jarvis.qa.review_today_desc"),
          icon: "review",
          workingLabel: t("jarvis.qa.review_today_working"),
          resultLabel: t("jarvis.qa.review_today_result"),
        },
        {
          label: t("jarvis.suggestion.3"),
          prompt: t("jarvis.suggestion.3"),
          description: t("jarvis.qa.plan_day_desc"),
          icon: "next_move",
          workingLabel: t("jarvis.qa.plan_day_working"),
          resultLabel: t("jarvis.qa.plan_day_result"),
        },
      ],
    };
  }
  if (pathname.startsWith("/settings") || pathname.startsWith("/rules")) {
    return {
      route: "settings",
      kicker: t("jarvis.kicker.settings"),
      title: t("jarvis.context.settings.title"),
      summary: t("jarvis.context.settings.summary"),
      quickActions: [],
    };
  }
  return {
    route: "home",
    kicker: t("jarvis.kicker.home"),
    title: t("jarvis.context.home.title"),
    summary: t("jarvis.context.home.summary"),
    quickActions: [
      {
        label: t("jarvis.qa.review_today"),
        prompt: t("jarvis.qa.review_today") + ".",
        description: t("jarvis.qa.review_today_desc"),
        icon: "review",
        workingLabel: t("jarvis.qa.review_today_working"),
        resultLabel: t("jarvis.qa.review_today_result"),
      },
      {
        label: t("jarvis.qa.check_blocked"),
        prompt: t("jarvis.qa.check_blocked") + ".",
        description: t("jarvis.qa.check_blocked_desc"),
        icon: "blocked",
        workingLabel: t("jarvis.qa.check_blocked_working"),
        resultLabel: t("jarvis.qa.check_blocked_result"),
      },
      {
        label: t("jarvis.qa.prioritize_projects"),
        prompt: t("jarvis.qa.prioritize_projects") + ".",
        description: t("jarvis.qa.prioritize_projects_desc"),
        icon: "priority",
        workingLabel: t("jarvis.qa.prioritize_projects_working"),
        resultLabel: t("jarvis.qa.prioritize_projects_result"),
      },
      {
        label: t("jarvis.suggestion.3"),
        prompt: t("jarvis.suggestion.3"),
        description: t("jarvis.qa.plan_day_desc"),
        icon: "next_move",
        workingLabel: t("jarvis.qa.plan_day_working"),
        resultLabel: t("jarvis.qa.plan_day_result"),
      },
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
