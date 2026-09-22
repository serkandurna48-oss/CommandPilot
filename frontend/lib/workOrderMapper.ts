import type {
  WorkOrder,
  ApprovalScope,
  AgentRun,
  ActivityLogEntry,
  Artifact,
  ReviewPackage,
  MissingContextItem,
  WorkOrderStep,
} from "@/types";

/**
 * Wire format ↔ domain type mapping for the work-order control plane.
 *
 * Convention: the backend (Pydantic + Postgres) uses snake_case, matching
 * every other resource in this codebase. The frontend domain types
 * (`frontend/types/index.ts`) use camelCase for this feature specifically,
 * because they were designed before any backend existed. Rather than
 * breaking that established frontend shape (and every component built
 * against it) or breaking the backend's snake_case convention (and every
 * other resource's precedent), this module is the single seam where the two
 * conventions meet. Nothing outside this file should see snake_case field
 * names — `lib/api.ts` returns raw API shapes, and callers must run them
 * through the `mapXFromApi` functions below before touching them.
 *
 * See docs/background-dev-team-system-design.md for the full rationale.
 */

// ─── Wire (API) shapes — mirror the backend Pydantic response models ──────────
export interface ApiMissingContextItem {
  label: string;
  description?: string | null;
  required: boolean;
}

export interface ApiApprovalScope {
  id: string;
  work_order_id: string;
  allowed_actions: string[];
  requires_approval: string[];
  blocked_actions: string[];
  allowed_paths?: string[] | null;
  blocked_paths?: string[] | null;
  max_runtime_minutes: number;
  max_cost_usd?: number | null;
  created_at: string;
}

export interface ApiWorkOrderStep {
  id: string;
  work_order_id: string;
  title: string;
  description?: string | null;
  status: string;
  assigned_role: string;
  order_index: number;
  acceptance_criteria: string[];
  started_at?: string | null;
  completed_at?: string | null;
  output_summary?: string | null;
  blocked_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiAgentRun {
  id: string;
  work_order_id: string;
  role: string;
  status: string;
  input_summary: string;
  output_summary?: string | null;
  model?: string | null;
  attempt_number?: number;
  retry_reason?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface ApiActivityLogEntry {
  id: string;
  work_order_id: string;
  agent_run_id?: string | null;
  level: string;
  event_type: string;
  message: string;
  metadata?: Record<string, string> | null;
  created_at: string;
}

export interface ApiArtifact {
  id: string;
  work_order_id: string;
  type: string;
  title: string;
  content?: string | null;
  file_path?: string | null;
  created_at: string;
}

export interface ApiReviewPackage {
  id: string;
  work_order_id: string;
  summary: string;
  files_changed: string[];
  tests_run: string[];
  risks: string[];
  open_questions: string[];
  needs_human_review: boolean;
  recommended_next_step?: string | null;
  verdict: string;
  created_at: string;
  updated_at: string;
}

export interface ApiWorkOrder {
  id: string;
  user_id: string;
  workspace_id?: string | null;
  title: string;
  goal: string;
  repo: string;
  status: string;
  approval_scope_id?: string | null;
  created_by: string;
  team_type: string;
  time_limit_minutes: number;
  acceptance_criteria: string[];
  missing_context: ApiMissingContextItem[];
  recommended_next_step?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  target_repo_name?: string | null;
  target_repo_path?: string | null;
  daemon_run_requested_at?: string | null;
}

export interface ApiWorkOrderDetail extends ApiWorkOrder {
  approval_scope?: ApiApprovalScope | null;
  steps: ApiWorkOrderStep[];
  agent_runs: ApiAgentRun[];
  activity_log: ApiActivityLogEntry[];
  artifacts: ApiArtifact[];
  review_package?: ApiReviewPackage | null;
}

export interface WorkOrderDetailBundle {
  order: WorkOrder;
  approvalScope?: ApprovalScope;
  steps: WorkOrderStep[];
  agentRuns: AgentRun[];
  activityLog: ActivityLogEntry[];
  artifacts: Artifact[];
  reviewPackage?: ReviewPackage;
}

// ─── API → domain ───────────────────────────────────────────────────────────────
function mapMissingContext(items: ApiMissingContextItem[]): MissingContextItem[] {
  return items.map((m) => ({ label: m.label, description: m.description ?? undefined, required: m.required }));
}

export function mapWorkOrderFromApi(raw: ApiWorkOrder): WorkOrder {
  return {
    id: raw.id,
    title: raw.title,
    goal: raw.goal,
    repo: raw.repo,
    status: raw.status as WorkOrder["status"],
    approvalScopeId: raw.approval_scope_id ?? "",
    createdBy: raw.created_by,
    teamType: raw.team_type,
    createdAt: raw.created_at,
    startedAt: raw.started_at ?? undefined,
    completedAt: raw.completed_at ?? undefined,
    timeLimitMinutes: raw.time_limit_minutes,
    acceptanceCriteria: raw.acceptance_criteria,
    recommendedNextStep: raw.recommended_next_step ?? undefined,
    missingContext: raw.missing_context.length > 0 ? mapMissingContext(raw.missing_context) : undefined,
    targetRepoName: raw.target_repo_name ?? undefined,
    targetRepoPath: raw.target_repo_path ?? undefined,
    daemonRunRequestedAt: raw.daemon_run_requested_at ?? undefined,
  };
}

// Deliberately derived, not a stored/mapped field of its own — a work order
// is "external repo mode" exactly when it has a targetRepoPath, so storing
// a second boolean alongside it would just be a second source of truth
// that could drift (see supabase/migrations/009_work_orders_target_repo.sql).
export function isExternalRepoWorkOrder(order: Pick<WorkOrder, "targetRepoPath">): boolean {
  return Boolean(order.targetRepoPath?.trim());
}

export function mapApprovalScopeFromApi(raw: ApiApprovalScope): ApprovalScope {
  return {
    id: raw.id,
    workOrderId: raw.work_order_id,
    allowedActions: raw.allowed_actions,
    requiresApproval: raw.requires_approval,
    blockedActions: raw.blocked_actions,
    allowedPaths: raw.allowed_paths ?? undefined,
    blockedPaths: raw.blocked_paths ?? undefined,
    maxRuntimeMinutes: raw.max_runtime_minutes,
    maxCostUsd: raw.max_cost_usd ?? undefined,
  };
}

export function mapWorkOrderStepFromApi(raw: ApiWorkOrderStep): WorkOrderStep {
  return {
    id: raw.id,
    workOrderId: raw.work_order_id,
    title: raw.title,
    description: raw.description ?? undefined,
    status: raw.status as WorkOrderStep["status"],
    assignedRole: raw.assigned_role as WorkOrderStep["assignedRole"],
    orderIndex: raw.order_index,
    acceptanceCriteria: raw.acceptance_criteria,
    startedAt: raw.started_at ?? undefined,
    completedAt: raw.completed_at ?? undefined,
    outputSummary: raw.output_summary ?? undefined,
    blockedReason: raw.blocked_reason ?? undefined,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function mapAgentRunFromApi(raw: ApiAgentRun): AgentRun {
  return {
    id: raw.id,
    workOrderId: raw.work_order_id,
    role: raw.role as AgentRun["role"],
    status: raw.status as AgentRun["status"],
    inputSummary: raw.input_summary,
    outputSummary: raw.output_summary ?? undefined,
    startedAt: raw.started_at ?? undefined,
    completedAt: raw.completed_at ?? undefined,
    model: raw.model ?? undefined,
    attemptNumber: raw.attempt_number ?? 1,
    retryReason: raw.retry_reason ?? undefined,
  };
}

export function mapActivityLogEntryFromApi(raw: ApiActivityLogEntry): ActivityLogEntry {
  return {
    id: raw.id,
    workOrderId: raw.work_order_id,
    agentRunId: raw.agent_run_id ?? undefined,
    level: raw.level as ActivityLogEntry["level"],
    eventType: raw.event_type,
    message: raw.message,
    metadata: raw.metadata ?? undefined,
    createdAt: raw.created_at,
  };
}

export function mapArtifactFromApi(raw: ApiArtifact): Artifact {
  return {
    id: raw.id,
    workOrderId: raw.work_order_id,
    type: raw.type as Artifact["type"],
    title: raw.title,
    content: raw.content ?? undefined,
    filePath: raw.file_path ?? undefined,
    createdAt: raw.created_at,
  };
}

export function mapReviewPackageFromApi(raw: ApiReviewPackage): ReviewPackage {
  return {
    id: raw.id,
    workOrderId: raw.work_order_id,
    summary: raw.summary,
    filesChanged: raw.files_changed,
    testsRun: raw.tests_run,
    risks: raw.risks,
    openQuestions: raw.open_questions,
    needsHumanReview: raw.needs_human_review,
    recommendedNextStep: raw.recommended_next_step ?? "",
    verdict: raw.verdict as ReviewPackage["verdict"],
  };
}

export function mapWorkOrderDetailFromApi(raw: ApiWorkOrderDetail): WorkOrderDetailBundle {
  return {
    order: mapWorkOrderFromApi(raw),
    approvalScope: raw.approval_scope ? mapApprovalScopeFromApi(raw.approval_scope) : undefined,
    steps: raw.steps.map(mapWorkOrderStepFromApi),
    agentRuns: raw.agent_runs.map(mapAgentRunFromApi),
    activityLog: raw.activity_log.map(mapActivityLogEntryFromApi),
    artifacts: raw.artifacts.map(mapArtifactFromApi),
    reviewPackage: raw.review_package ? mapReviewPackageFromApi(raw.review_package) : undefined,
  };
}

// ─── Domain → API (for creating a work order) ──────────────────────────────────
export interface WorkOrderStepInput {
  title: string;
  description?: string;
  assignedRole: WorkOrderStep["assignedRole"];
  orderIndex?: number;
  acceptanceCriteria?: string[];
}

export interface WorkOrderCreateInput {
  title: string;
  goal: string;
  repo?: string;
  teamType?: string;
  timeLimitMinutes?: number;
  acceptanceCriteria?: string[];
  missingContext?: MissingContextItem[];
  steps?: WorkOrderStepInput[];
  targetRepoName?: string;
  targetRepoPath?: string;
  approvalScope: {
    allowedActions: string[];
    requiresApproval: string[];
    blockedActions: string[];
    allowedPaths?: string[];
    blockedPaths?: string[];
    maxRuntimeMinutes: number;
    maxCostUsd?: number;
  };
}

export interface ApiWorkOrderStepCreate {
  title: string;
  description?: string;
  assigned_role: string;
  order_index?: number;
  acceptance_criteria?: string[];
}

export interface ApiWorkOrderStepUpdate {
  status?: string;
  output_summary?: string;
  blocked_reason?: string;
}

export interface ApiWorkOrderUpdate {
  status?: string;
  recommended_next_step?: string;
  missing_context?: ApiMissingContextItem[];
  daemon_run_requested_at?: string | null;
}

export interface ApiActivityLogCreate {
  agent_run_id?: string;
  level: string;
  event_type: string;
  message: string;
  metadata?: Record<string, string>;
}

export interface ApiAgentRunCreate {
  role: string;
  status?: string;
  input_summary: string;
  output_summary?: string;
  model?: string;
}

export interface ApiAgentRunUpdate {
  status?: string;
  output_summary?: string;
  model?: string;
}

export interface ApiArtifactCreate {
  type: string;
  title: string;
  content?: string;
  file_path?: string;
}

export interface ApiReviewPackageCreate {
  summary: string;
  files_changed: string[];
  tests_run: string[];
  risks: string[];
  open_questions: string[];
  needs_human_review: boolean;
  recommended_next_step?: string;
  verdict: string;
}

export function mapWorkOrderCreateToApi(input: WorkOrderCreateInput) {
  return {
    title: input.title,
    goal: input.goal,
    repo: input.repo ?? "commandpilot",
    team_type: input.teamType ?? "development",
    time_limit_minutes: input.timeLimitMinutes ?? 90,
    acceptance_criteria: input.acceptanceCriteria ?? [],
    missing_context: (input.missingContext ?? []).map((m) => ({
      label: m.label,
      description: m.description,
      required: m.required,
    })),
    steps: (input.steps ?? []).map((s) => ({
      title: s.title,
      description: s.description,
      assigned_role: s.assignedRole,
      order_index: s.orderIndex,
      acceptance_criteria: s.acceptanceCriteria ?? [],
    })),
    target_repo_name: input.targetRepoName,
    target_repo_path: input.targetRepoPath,
    approval_scope: {
      allowed_actions: input.approvalScope.allowedActions,
      requires_approval: input.approvalScope.requiresApproval,
      blocked_actions: input.approvalScope.blockedActions,
      allowed_paths: input.approvalScope.allowedPaths,
      blocked_paths: input.approvalScope.blockedPaths,
      max_runtime_minutes: input.approvalScope.maxRuntimeMinutes,
      max_cost_usd: input.approvalScope.maxCostUsd,
    },
  };
}
