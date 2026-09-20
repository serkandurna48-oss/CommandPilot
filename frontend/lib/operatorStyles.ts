import type { WorkOrderStatus, AgentRunStatus, ActivityLogLevel, ReviewVerdict } from "@/types";

// Restrained badge colors — same visual language as ProjectsManager's STATUS_COLORS.
export const WORK_ORDER_STATUS_COLORS: Record<WorkOrderStatus, string> = {
  draft:             "bg-slate-800 border border-slate-700 text-slate-500",
  approved:          "bg-slate-800 border border-green-800/40 text-green-400/80",
  queued:            "bg-slate-800 border border-slate-600 text-slate-300",
  running:           "bg-slate-800 border border-brand-700/40 text-brand-400/80",
  needs_approval:    "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  blocked:           "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  failed:            "bg-slate-800 border border-rose-800/40 text-rose-400/80",
  review_ready:      "bg-slate-800 border border-sky-800/40 text-sky-400/80",
  accepted:          "bg-slate-800 border border-green-800/40 text-green-400/80",
  rework_requested:  "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  cancelled:         "bg-slate-800 border border-slate-800 text-slate-600",
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
  queued:    "bg-slate-800 border border-slate-600 text-slate-300",
  running:   "bg-slate-800 border border-brand-700/40 text-brand-400/80",
  blocked:   "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  failed:    "bg-slate-800 border border-rose-800/40 text-rose-400/80",
  completed: "bg-slate-800 border border-green-800/40 text-green-400/80",
};

export const LOG_LEVEL_COLORS: Record<ActivityLogLevel, string> = {
  info:              "text-slate-400",
  warning:           "text-amber-400/80",
  error:             "text-rose-400/80",
  approval_required: "text-amber-300",
};

export const VERDICT_COLORS: Record<ReviewVerdict, string> = {
  ready_for_review: "bg-slate-800 border border-green-800/40 text-green-400/80",
  needs_fix:        "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  blocked:          "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  unsafe:           "bg-slate-800 border border-rose-800/40 text-rose-400/80",
};

// Jarvis suggested-action risk badge (JARVIS-C1) — same low/medium/high
// traffic-light convention as the rest of this file.
export const RISK_COLORS: Record<"low" | "medium" | "high", string> = {
  low:    "bg-slate-800 border border-green-800/40 text-green-400/80",
  medium: "bg-slate-800 border border-amber-800/40 text-amber-400/80",
  high:   "bg-slate-800 border border-rose-800/40 text-rose-400/80",
};
