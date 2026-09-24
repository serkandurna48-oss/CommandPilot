import type { WorkOrder, WorkOrderStatus, AgentRunStatus, ActivityLogLevel, ReviewVerdict } from "@/types";

// Status-dot palette (Focus Deck tokens, not raw Tailwind colors) — shared
// between HomeBriefing's operational rail and the Operator overview list so
// both draw the same status from the same visual language. Moved here from
// HomeBriefing.tsx (was a local, unexported const) when the Operator list
// adopted it too — same values, no visual change to Home.
export const WORK_ORDER_STATUS_DOT: Record<WorkOrder["status"], string> = {
  draft:            "bg-[var(--text-placeholder)]",
  approved:         "bg-status-success",
  queued:           "bg-[var(--text-tertiary)]",
  running:          "bg-brand-400",
  needs_approval:   "bg-status-warning",
  blocked:          "bg-status-warning",
  failed:           "bg-status-danger",
  review_ready:     "bg-status-info",
  accepted:         "bg-status-success",
  rework_requested: "bg-status-warning",
  cancelled:        "bg-[var(--text-placeholder)]",
};

// Restrained badge colors — Focus Deck tokens (--bg-elevated/--border-*/
// status-*/brand-*), not raw Tailwind slate/amber/rose. Previously raw —
// unified when the Operator overview and detail page both moved onto Focus
// Deck (23.09.2026); same semantic mapping (green=success, amber=warning,
// rose=danger, sky=info, brand=in-progress) as before, just tokenized.
export const WORK_ORDER_STATUS_COLORS: Record<WorkOrderStatus, string> = {
  draft:             "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  approved:          "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
  queued:            "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  running:           "bg-[var(--bg-elevated)] border border-brand-700/40 text-brand-400",
  needs_approval:    "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  blocked:           "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  failed:            "bg-[var(--bg-elevated)] border border-status-danger/40 text-status-danger",
  review_ready:      "bg-[var(--bg-elevated)] border border-status-info/40 text-status-info",
  accepted:          "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
  rework_requested:  "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  cancelled:         "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-placeholder)]",
};

// Ordered left-to-right the way a work order typically flows — used to render
// the status legend/flow strip in the UI.
export const WORK_ORDER_STATUS_FLOW: WorkOrderStatus[] = [
  "draft",
  "approved",
  "queued",
  "running",
  "needs_approval",
  "blocked",
  "review_ready",
  "accepted",
  "rework_requested",
  "failed",
  "cancelled",
];

export const AGENT_RUN_STATUS_COLORS: Record<AgentRunStatus, string> = {
  queued:    "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  running:   "bg-[var(--bg-elevated)] border border-brand-700/40 text-brand-400",
  blocked:   "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  failed:    "bg-[var(--bg-elevated)] border border-status-danger/40 text-status-danger",
  completed: "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
};

export const LOG_LEVEL_COLORS: Record<ActivityLogLevel, string> = {
  info:              "text-[var(--text-tertiary)]",
  warning:           "text-status-warning",
  error:             "text-status-danger",
  approval_required: "text-status-warning",
};

export const VERDICT_COLORS: Record<ReviewVerdict, string> = {
  ready_for_review: "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
  needs_fix:        "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  blocked:          "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  unsafe:           "bg-[var(--bg-elevated)] border border-status-danger/40 text-status-danger",
};

// Jarvis suggested-action risk badge (JARVIS-C1) — same low/medium/high
// traffic-light convention as the rest of this file.
export const RISK_COLORS: Record<"low" | "medium" | "high", string> = {
  low:    "bg-[var(--bg-elevated)] border border-status-success/40 text-status-success",
  medium: "bg-[var(--bg-elevated)] border border-status-warning/40 text-status-warning",
  high:   "bg-[var(--bg-elevated)] border border-status-danger/40 text-status-danger",
};
