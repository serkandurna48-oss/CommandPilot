import type { WorkOrderStep } from "@/types";

// The one canonical progress calculation for a ticketplan — shared by
// StepPipeline.tsx (the Mission Control node graph that replaced this
// file's old list-based ExecutionPlan component) so there's never a
// second, potentially-drifting percentage computed elsewhere.
export function progressPercent(steps: WorkOrderStep[]): number {
  if (steps.length === 0) return 0;
  const done = steps.filter((s) => s.status === "completed" || s.status === "skipped").length;
  return Math.round((done / steps.length) * 100);
}
