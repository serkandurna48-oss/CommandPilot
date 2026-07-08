import type {
  WorkOrder,
  ApprovalScope,
  WorkOrderStep,
  AgentRun,
  ActivityLogEntry,
  Artifact,
  ReviewPackage,
} from "@/types";

/**
 * Mock data only — no backend endpoint exists yet for the Background Dev Team
 * control plane. Every entity below is invented example data for CommandPilot's
 * own repo/roadmap, or explicitly modeled as "blocked on missing context" for
 * external projects (CampsPilot, Signalübertragung) that CommandPilot has no
 * real access to. See docs/background-dev-team-system-design.md.
 */

// ─── Work Order 1: CommandPilot Operator MVP ───────────────────────────────────
// A self-referential example: the exact kind of task that produced this file.
const WO1_ID = "wo-1";

const wo1: WorkOrder = {
  id: WO1_ID,
  title: "CommandPilot Operator MVP weiterbauen",
  goal: "Erweitere die Operator-Seite zu einem Background Dev Team Control Plane: saubere Typen, Statusflow, Approval Scopes, Runner-Prompt-Generator, sichtbare Safety Rules.",
  repo: "commandpilot",
  status: "review_ready",
  approvalScopeId: "as-1",
  createdBy: "Serkan",
  teamType: "development",
  createdAt: "2026-07-07T09:00:00Z",
  startedAt: "2026-07-07T09:05:00Z",
  completedAt: "2026-07-07T10:20:00Z",
  timeLimitMinutes: 90,
  acceptanceCriteria: [
    "WorkOrder/ApprovalScope/AgentRun/ActivityLog/Artifact/ReviewPackage sauber typisiert",
    "Statusflow UI-seitig erkennbar",
    "Safety Rules sichtbar (allowed / needs approval / blocked)",
    "Generate Runner Prompt Funktion vorhanden und kopierbar",
    "Mindestens 3 realistische Mock Work Orders",
    "typecheck + build laufen fehlerfrei durch",
  ],
  recommendedNextStep: "Reales Backend-Modell (work_orders, approval_scopes, agent_runs) spezifizieren und als eigenständiges Work Order einreichen.",
};

// ─── Work Order 2: CampsPilot CS-302 to CS-305 ─────────────────────────────────
const WO2_ID = "wo-2";

const wo2: WorkOrder = {
  id: WO2_ID,
  title: "CampsPilot CS-302 bis CS-305 vorbereiten",
  goal: "Baue CampsPilot CS-302 bis CS-305 weiter: Repo lesen, Plan erstellen, Code ändern, Tests laufen lassen. Nicht erlaubt: deployen, production data ändern, E-Mails senden, Secrets anzeigen.",
  repo: "campspilot",
  status: "blocked",
  approvalScopeId: "as-2",
  createdBy: "Serkan",
  teamType: "development",
  createdAt: "2026-07-06T08:00:00Z",
  timeLimitMinutes: 90,
  acceptanceCriteria: [
    "TBD — abhängig von Ticket-Inhalten (Platzhalter, bis Kontext vorliegt)",
  ],
  missingContext: [
    { label: "Ticket-Beschreibungen CS-302 bis CS-305", required: true },
    { label: "Repo-Zugriff auf CampsPilot", required: true },
    { label: "Akzeptanzkriterien pro Ticket", required: true },
  ],
  recommendedNextStep: "Serkan: Ticket-Texte einfügen oder Repo-Zugriff freigeben, bevor dieses Work Order approved werden kann.",
};

// ─── Work Order 3: Signalübertragung Lerncoach Spike ───────────────────────────
const WO3_ID = "wo-3";

const wo3: WorkOrder = {
  id: WO3_ID,
  title: "Signalübertragung Lerncoach Spike",
  goal: "Spike: aus vorhandenen Vorlesungsnotizen eine Active-Recall-Session generieren (Fragen + Schwierigkeitsstufen), rein lokal, ohne externe Anbindung.",
  repo: "commandpilot",
  status: "needs_approval",
  approvalScopeId: "as-3",
  createdBy: "Serkan",
  teamType: "development",
  createdAt: "2026-07-06T20:00:00Z",
  startedAt: "2026-07-06T20:10:00Z",
  timeLimitMinutes: 60,
  acceptanceCriteria: [
    "Session-Generator erzeugt mind. 5 Fragen aus bereitgestelltem Notiztext",
    "Jede Frage hat eine Schwierigkeitsstufe",
    "Keine externe Anfrage, keine neue Abhängigkeit ohne Approval",
  ],
  missingContext: [
    { label: "Vorlesungsnotizen", required: true },
    { label: "Themenliste", required: true },
    { label: "Schwierigkeitsgrad", required: false },
  ],
  recommendedNextStep: "Architect Agent hat eine neue Dependency vorgeschlagen (Spaced-Repetition-Bibliothek) — das braucht Approval, bevor der Coder Agent weiterarbeitet.",
};

export const MOCK_WORK_ORDERS: WorkOrder[] = [wo1, wo2, wo3];

// ─── Approval Scopes ────────────────────────────────────────────────────────────
export const MOCK_APPROVAL_SCOPES: ApprovalScope[] = [
  {
    id: "as-1",
    workOrderId: WO1_ID,
    allowedActions: [
      "Repo lesen",
      "Plan erstellen",
      "Code ändern innerhalb frontend/",
      "Tests / Lint / Typecheck ausführen",
      "Lokale Artifacts erzeugen",
      "Review Package schreiben",
    ],
    requiresApproval: [
      "Neue Dependencies installieren",
      "Backend/DB-Schema ändern",
      "Push / PR erstellen",
    ],
    blockedActions: [
      "Deployen",
      "Production-Daten ändern",
      "Secrets anzeigen oder loggen",
      "E-Mails senden",
      "Destructive Git-Kommandos",
      "Direkte Änderungen auf main",
    ],
    allowedPaths: ["frontend/", "docs/"],
    blockedPaths: ["backend/.env", "supabase/"],
    maxRuntimeMinutes: 90,
    maxCostUsd: 5,
  },
  {
    id: "as-2",
    workOrderId: WO2_ID,
    allowedActions: [
      "Repo lesen",
      "Plan erstellen",
      "Code ändern innerhalb Scope",
      "Tests laufen lassen",
    ],
    requiresApproval: [
      "Ausführung starten, solange Ticket-Kontext fehlt",
      "Push / PR erstellen",
      "Dependencies installieren",
    ],
    blockedActions: [
      "Deployen",
      "Production-Daten ändern",
      "E-Mails senden",
      "Secrets anzeigen",
    ],
    maxRuntimeMinutes: 90,
  },
  {
    id: "as-3",
    workOrderId: WO3_ID,
    allowedActions: [
      "Bereitgestellten Notiztext lesen",
      "Fragen/Recall-Items lokal generieren",
      "Lokale Artifacts erzeugen",
    ],
    requiresApproval: [
      "Neue Dependency hinzufügen",
      "Architekturänderung am Lernmodul",
    ],
    blockedActions: [
      "Externe API-Calls",
      "Deployen",
      "Secrets anzeigen",
    ],
    maxRuntimeMinutes: 60,
    maxCostUsd: 2,
  },
];

// ─── Work Order Steps (the visible execution/ticket plan) ──────────────────────
export const MOCK_WORK_ORDER_STEPS: WorkOrderStep[] = [
  // WO1 — full 6-step plan, all completed (review_ready)
  { id: "step-1-1", workOrderId: WO1_ID, title: "Product/Criteria", description: "Ziel + Akzeptanzkriterien aus Mission-Text ableiten.", status: "completed", assignedRole: "product", orderIndex: 0, acceptanceCriteria: ["Akzeptanzkriterien stehen"], startedAt: "2026-07-07T09:05:00Z", completedAt: "2026-07-07T09:12:00Z", outputSummary: "Akzeptanzkriterien + MVP-Scope definiert.", createdAt: "2026-07-07T09:00:00Z", updatedAt: "2026-07-07T09:12:00Z" },
  { id: "step-1-2", workOrderId: WO1_ID, title: "Architecture", description: "Datenmodell + Routing-Struktur festlegen.", status: "completed", assignedRole: "architect", orderIndex: 1, acceptanceCriteria: ["Datenmodell entschieden", "camelCase/snake_case-Konvention dokumentiert"], startedAt: "2026-07-07T09:12:00Z", completedAt: "2026-07-07T09:22:00Z", outputSummary: "Datenmodell + Routing-Struktur entschieden.", createdAt: "2026-07-07T09:00:00Z", updatedAt: "2026-07-07T09:22:00Z" },
  { id: "step-1-3", workOrderId: WO1_ID, title: "Implementation", description: "Typen, Mock-Daten, Detail-UI, Prompt-Generator implementieren.", status: "completed", assignedRole: "coder", orderIndex: 2, acceptanceCriteria: ["Alle geplanten Dateien geändert/erstellt"], startedAt: "2026-07-07T09:22:00Z", completedAt: "2026-07-07T10:05:00Z", outputSummary: "6 Dateien geändert/erstellt.", createdAt: "2026-07-07T09:00:00Z", updatedAt: "2026-07-07T10:05:00Z" },
  { id: "step-1-4", workOrderId: WO1_ID, title: "QA", description: "typecheck + build ausführen.", status: "completed", assignedRole: "qa", orderIndex: 3, acceptanceCriteria: ["tsc --noEmit clean", "next build erfolgreich"], startedAt: "2026-07-07T10:05:00Z", completedAt: "2026-07-07T10:12:00Z", outputSummary: "tsc --noEmit clean, next build erfolgreich.", createdAt: "2026-07-07T09:00:00Z", updatedAt: "2026-07-07T10:12:00Z" },
  { id: "step-1-5", workOrderId: WO1_ID, title: "Review", description: "Scope-Verletzungen, Edge Cases prüfen.", status: "completed", assignedRole: "reviewer", orderIndex: 4, acceptanceCriteria: ["Keine Scope-Verletzung"], startedAt: "2026-07-07T10:12:00Z", completedAt: "2026-07-07T10:17:00Z", outputSummary: "Keine Scope-Verletzung gefunden.", createdAt: "2026-07-07T09:00:00Z", updatedAt: "2026-07-07T10:17:00Z" },
  { id: "step-1-6", workOrderId: WO1_ID, title: "Reporter", description: "Review Package zusammenstellen.", status: "completed", assignedRole: "reporter", orderIndex: 5, acceptanceCriteria: ["Review Package mit Verdict vorhanden"], startedAt: "2026-07-07T10:17:00Z", completedAt: "2026-07-07T10:20:00Z", outputSummary: "Review Package erstellt, verdict: ready_for_review.", createdAt: "2026-07-07T09:00:00Z", updatedAt: "2026-07-07T10:20:00Z" },

  // WO2 — blocked right at step 1, nothing downstream has started
  { id: "step-2-1", workOrderId: WO2_ID, title: "Product/Criteria", description: "Akzeptanzkriterien pro Ticket ableiten.", status: "blocked", assignedRole: "product", orderIndex: 0, acceptanceCriteria: ["Akzeptanzkriterien pro Ticket (CS-302–CS-305)"], startedAt: "2026-07-06T08:01:00Z", blockedReason: "Ticket-Beschreibungen CS-302–CS-305 nicht verfügbar — kann keine Akzeptanzkriterien ableiten.", createdAt: "2026-07-06T08:00:00Z", updatedAt: "2026-07-06T08:02:00Z" },
  { id: "step-2-2", workOrderId: WO2_ID, title: "Architecture", description: "Technische Umsetzung pro Ticket planen.", status: "pending", assignedRole: "architect", orderIndex: 1, acceptanceCriteria: [], createdAt: "2026-07-06T08:00:00Z", updatedAt: "2026-07-06T08:00:00Z" },
  { id: "step-2-3", workOrderId: WO2_ID, title: "Implementation", status: "pending", assignedRole: "coder", orderIndex: 2, acceptanceCriteria: [], createdAt: "2026-07-06T08:00:00Z", updatedAt: "2026-07-06T08:00:00Z" },
  { id: "step-2-4", workOrderId: WO2_ID, title: "QA", status: "pending", assignedRole: "qa", orderIndex: 3, acceptanceCriteria: [], createdAt: "2026-07-06T08:00:00Z", updatedAt: "2026-07-06T08:00:00Z" },
  { id: "step-2-5", workOrderId: WO2_ID, title: "Review", status: "pending", assignedRole: "reviewer", orderIndex: 4, acceptanceCriteria: [], createdAt: "2026-07-06T08:00:00Z", updatedAt: "2026-07-06T08:00:00Z" },
  { id: "step-2-6", workOrderId: WO2_ID, title: "Reporter", status: "pending", assignedRole: "reporter", orderIndex: 5, acceptanceCriteria: [], createdAt: "2026-07-06T08:00:00Z", updatedAt: "2026-07-06T08:00:00Z" },

  // WO3 — step 1 done, step 2 blocked on a scope violation, rest pending
  { id: "step-3-1", workOrderId: WO3_ID, title: "Product/Criteria", description: "Nutzerflow für Active-Recall-Session skizzieren.", status: "completed", assignedRole: "product", orderIndex: 0, acceptanceCriteria: ["Nutzerflow steht"], startedAt: "2026-07-06T20:10:00Z", completedAt: "2026-07-06T20:18:00Z", outputSummary: "Flow steht, wartet auf Lerninhalte.", createdAt: "2026-07-06T20:00:00Z", updatedAt: "2026-07-06T20:18:00Z" },
  { id: "step-3-2", workOrderId: WO3_ID, title: "Architecture", description: "Technische Umsetzung planen.", status: "blocked", assignedRole: "architect", orderIndex: 1, acceptanceCriteria: ["Umsetzung ohne neue Dependency ohne Approval"], startedAt: "2026-07-06T20:18:00Z", blockedReason: "Schlägt Spaced-Repetition-Bibliothek vor — außerhalb allowedActions, braucht Approval.", createdAt: "2026-07-06T20:00:00Z", updatedAt: "2026-07-06T20:25:00Z" },
  { id: "step-3-3", workOrderId: WO3_ID, title: "Implementation", status: "pending", assignedRole: "coder", orderIndex: 2, acceptanceCriteria: [], createdAt: "2026-07-06T20:00:00Z", updatedAt: "2026-07-06T20:00:00Z" },
  { id: "step-3-4", workOrderId: WO3_ID, title: "QA", status: "pending", assignedRole: "qa", orderIndex: 3, acceptanceCriteria: [], createdAt: "2026-07-06T20:00:00Z", updatedAt: "2026-07-06T20:00:00Z" },
  { id: "step-3-5", workOrderId: WO3_ID, title: "Review", status: "pending", assignedRole: "reviewer", orderIndex: 4, acceptanceCriteria: [], createdAt: "2026-07-06T20:00:00Z", updatedAt: "2026-07-06T20:00:00Z" },
  { id: "step-3-6", workOrderId: WO3_ID, title: "Reporter", status: "pending", assignedRole: "reporter", orderIndex: 5, acceptanceCriteria: [], createdAt: "2026-07-06T20:00:00Z", updatedAt: "2026-07-06T20:00:00Z" },
];

// ─── Agent Runs ─────────────────────────────────────────────────────────────────
export const MOCK_AGENT_RUNS: AgentRun[] = [
  // WO1 — full pipeline, completed
  { id: "ar-1-product",   workOrderId: WO1_ID, role: "product",   status: "completed", inputSummary: "Ziel + Nutzerflow aus Mission-Text ableiten", outputSummary: "Akzeptanzkriterien + MVP-Scope definiert", startedAt: "2026-07-07T09:05:00Z", completedAt: "2026-07-07T09:12:00Z", model: "claude-sonnet-5" },
  { id: "ar-1-architect", workOrderId: WO1_ID, role: "architect", status: "completed", inputSummary: "Bestehende Patterns (Project/Plan) analysieren", outputSummary: "Datenmodell + Routing-Struktur entschieden", startedAt: "2026-07-07T09:12:00Z", completedAt: "2026-07-07T09:22:00Z", model: "claude-sonnet-5" },
  { id: "ar-1-coder",     workOrderId: WO1_ID, role: "coder",     status: "completed", inputSummary: "Typen, Mock-Daten, Detail-UI, Prompt-Generator implementieren", outputSummary: "6 Dateien geändert/erstellt, build grün", startedAt: "2026-07-07T09:22:00Z", completedAt: "2026-07-07T10:05:00Z", model: "claude-sonnet-5" },
  { id: "ar-1-qa",        workOrderId: WO1_ID, role: "qa",        status: "completed", inputSummary: "typecheck + build ausführen", outputSummary: "tsc --noEmit clean, next build erfolgreich", startedAt: "2026-07-07T10:05:00Z", completedAt: "2026-07-07T10:12:00Z", model: "claude-sonnet-5" },
  { id: "ar-1-reviewer",  workOrderId: WO1_ID, role: "reviewer",  status: "completed", inputSummary: "Scope-Verletzungen, Edge Cases prüfen", outputSummary: "Keine Scope-Verletzung gefunden; Naming-Abweichung (camelCase) dokumentiert", startedAt: "2026-07-07T10:12:00Z", completedAt: "2026-07-07T10:17:00Z", model: "claude-sonnet-5" },
  { id: "ar-1-reporter",  workOrderId: WO1_ID, role: "reporter",  status: "completed", inputSummary: "Review Package zusammenstellen", outputSummary: "Review Package erstellt, verdict: ready_for_review", startedAt: "2026-07-07T10:17:00Z", completedAt: "2026-07-07T10:20:00Z", model: "claude-sonnet-5" },

  // WO2 — blocked right after product agent noticed missing context
  { id: "ar-2-product",   workOrderId: WO2_ID, role: "product",   status: "blocked", inputSummary: "Ziel aus Work-Order-Text ableiten", outputSummary: "Ticket-Inhalte fehlen — kann Akzeptanzkriterien nicht ableiten", startedAt: "2026-07-06T08:01:00Z" },
  { id: "ar-2-architect", workOrderId: WO2_ID, role: "architect", status: "queued",  inputSummary: "Wartet auf Product-Agent-Output" },

  // WO3 — architect proposed an out-of-scope action, paused for approval
  { id: "ar-3-product",   workOrderId: WO3_ID, role: "product",   status: "completed", inputSummary: "Nutzerflow für Active-Recall-Session skizzieren", outputSummary: "Flow steht, wartet auf Lerninhalte", startedAt: "2026-07-06T20:10:00Z", completedAt: "2026-07-06T20:18:00Z", model: "claude-sonnet-5" },
  { id: "ar-3-architect", workOrderId: WO3_ID, role: "architect", status: "blocked",  inputSummary: "Technische Umsetzung planen", outputSummary: "Schlägt Spaced-Repetition-Bibliothek vor — außerhalb Approval Scope, wartet auf Freigabe", startedAt: "2026-07-06T20:18:00Z" },
];

// ─── Activity Log ───────────────────────────────────────────────────────────────
export const MOCK_ACTIVITY_LOG: ActivityLogEntry[] = [
  { id: "log-1-1", workOrderId: WO1_ID, agentRunId: "ar-1-product",   level: "info",             eventType: "run_started",   message: "Product Agent gestartet.", createdAt: "2026-07-07T09:05:00Z" },
  { id: "log-1-2", workOrderId: WO1_ID, agentRunId: "ar-1-architect", level: "info",             eventType: "run_completed", message: "Architect Agent: Datenmodell entschieden (camelCase, frontend-only).", createdAt: "2026-07-07T09:22:00Z" },
  { id: "log-1-3", workOrderId: WO1_ID, agentRunId: "ar-1-coder",     level: "info",             eventType: "artifact_created", message: "Artifact erzeugt: diff (types/index.ts, mockWorkOrders.ts, OperatorManager.tsx).", createdAt: "2026-07-07T10:00:00Z" },
  { id: "log-1-4", workOrderId: WO1_ID, agentRunId: "ar-1-qa",        level: "info",             eventType: "check_passed",  message: "tsc --noEmit: 0 Fehler.", createdAt: "2026-07-07T10:10:00Z" },
  { id: "log-1-5", workOrderId: WO1_ID, agentRunId: "ar-1-reporter",  level: "info",             eventType: "review_package_created", message: "Review Package erstellt, verdict: ready_for_review.", createdAt: "2026-07-07T10:20:00Z" },

  { id: "log-2-1", workOrderId: WO2_ID, agentRunId: "ar-2-product",   level: "warning",          eventType: "missing_context", message: "Ticket-Beschreibungen CS-302–CS-305 nicht verfügbar.", createdAt: "2026-07-06T08:01:30Z" },
  { id: "log-2-2", workOrderId: WO2_ID,                                level: "approval_required", eventType: "blocked",      message: "Work Order blockiert, bis Serkan Ticket-Kontext bereitstellt.", createdAt: "2026-07-06T08:02:00Z" },

  { id: "log-3-1", workOrderId: WO3_ID, agentRunId: "ar-3-product",   level: "info",             eventType: "run_completed", message: "Nutzerflow für Recall-Session steht.", createdAt: "2026-07-06T20:18:00Z" },
  { id: "log-3-2", workOrderId: WO3_ID, agentRunId: "ar-3-architect", level: "approval_required", eventType: "scope_boundary", message: "Architect Agent schlägt neue Dependency vor — außerhalb allowedActions, Approval nötig.", createdAt: "2026-07-06T20:25:00Z" },
];

// ─── Artifacts ───────────────────────────────────────────────────────────────────
export const MOCK_ARTIFACTS: Artifact[] = [
  { id: "art-1-plan",    workOrderId: WO1_ID, type: "plan",    title: "MVP-Plan: Control Plane", content: "1) Typen finalisieren 2) Mock-Daten 3) Detail-UI 4) Runner-Prompt 5) Safety Rules 6) Doku", createdAt: "2026-07-07T09:12:00Z" },
  { id: "art-1-diff",    workOrderId: WO1_ID, type: "diff",    title: "Geänderte Dateien (Zusammenfassung)", content: "types/index.ts, lib/mockWorkOrders.ts, components/operator/*, app/operator/*, docs/background-dev-team-system-design.md", createdAt: "2026-07-07T10:00:00Z" },
  { id: "art-1-tests",   workOrderId: WO1_ID, type: "test_output", title: "typecheck + build", content: "tsc --noEmit: OK\nnext build: OK (/operator, /operator/[id] kompilieren)", createdAt: "2026-07-07T10:10:00Z" },
  { id: "art-1-summary", workOrderId: WO1_ID, type: "summary", title: "Kurzfassung für Serkan", content: "Operator-Seite ist jetzt ein Command Center mit Approval Scopes, Agent Runs, Activity Log, Artifacts und Runner-Prompt-Generator.", createdAt: "2026-07-07T10:19:00Z" },

  { id: "art-2-plan",    workOrderId: WO2_ID, type: "plan",    title: "Vorläufiger Plan (unvollständig)", content: "Kann erst nach Ticket-Kontext konkretisiert werden.", createdAt: "2026-07-06T08:03:00Z" },

  { id: "art-3-plan",    workOrderId: WO3_ID, type: "plan",    title: "Spike-Plan: Recall-Session-Generator", content: "Notiztext → Themen extrahieren → Fragen generieren → Schwierigkeit taggen.", createdAt: "2026-07-06T20:15:00Z" },
];

// ─── Review Packages ─────────────────────────────────────────────────────────────
export const MOCK_REVIEW_PACKAGES: ReviewPackage[] = [
  {
    id: "rp-1",
    workOrderId: WO1_ID,
    summary: "Operator-Seite zu einem Background Dev Team Control Plane ausgebaut: vollständige Typisierung, Statusflow, Approval Scopes, Runner-Prompt-Generator, sichtbare Safety Rules und 3 realistische Mock Work Orders.",
    filesChanged: [
      "frontend/types/index.ts",
      "frontend/lib/mockWorkOrders.ts",
      "frontend/components/operator/OperatorManager.tsx",
      "frontend/app/operator/page.tsx",
      "frontend/app/operator/[id]/page.tsx",
      "docs/background-dev-team-system-design.md",
    ],
    testsRun: ["tsc --noEmit", "next build"],
    risks: [
      "Neue Typen sind camelCase statt snake_case wie der Rest des Repos — bewusste Abweichung, da (noch) kein Backend-Gegenstück existiert.",
      "Kein echtes Backend/DB — bei realer Umsetzung muss RLS/Ownership wie bei projects/plans nachgezogen werden.",
    ],
    openQuestions: [
      "Soll der Judge/Executor-Split ein echter Prozess (zwei Claude-Code-Instanzen) oder zunächst nur ein UI-Konzept sein?",
    ],
    needsHumanReview: true,
    recommendedNextStep: "Serkan reviewt die Operator-Seite im Browser, danach: Backend-Datenmodell für work_orders spezifizieren.",
    verdict: "ready_for_review",
  },
];

// ─── Lookup helpers ───────────────────────────────────────────────────────────────
export function getApprovalScope(workOrderId: string): ApprovalScope | undefined {
  return MOCK_APPROVAL_SCOPES.find((s) => s.workOrderId === workOrderId);
}

export function getSteps(workOrderId: string): WorkOrderStep[] {
  return MOCK_WORK_ORDER_STEPS
    .filter((s) => s.workOrderId === workOrderId)
    .sort((a, b) => a.orderIndex - b.orderIndex);
}

export function getAgentRuns(workOrderId: string): AgentRun[] {
  return MOCK_AGENT_RUNS.filter((r) => r.workOrderId === workOrderId);
}

export function getActivityLog(workOrderId: string): ActivityLogEntry[] {
  return MOCK_ACTIVITY_LOG
    .filter((e) => e.workOrderId === workOrderId)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export function getArtifacts(workOrderId: string): Artifact[] {
  return MOCK_ARTIFACTS.filter((a) => a.workOrderId === workOrderId);
}

export function getReviewPackage(workOrderId: string): ReviewPackage | undefined {
  return MOCK_REVIEW_PACKAGES.find((p) => p.workOrderId === workOrderId);
}

export function getWorkOrder(id: string): WorkOrder | undefined {
  return MOCK_WORK_ORDERS.find((o) => o.id === id);
}
