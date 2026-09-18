// ─── Life Areas ────────────────────────────────────────────────────────────────
export type LifeAreaSlug =
  | "work"
  | "study"
  | "business"
  | "sport"
  | "health"
  | "admin"
  | "social"
  | "content"
  | "finance"
  | "personal"
  | string;

export const LIFE_AREA_COLORS: Record<string, string> = {
  work:     "#3b82f6",
  study:    "#8b5cf6",
  business: "#10b981",
  sport:    "#f59e0b",
  health:   "#ef4444",
  admin:    "#6b7280",
  social:   "#ec4899",
  content:  "#f97316",
  finance:  "#14b8a6",
  personal: "#a78bfa",
};

// ─── Check-in ──────────────────────────────────────────────────────────────────
export interface FixedEvent {
  title: string;
  time?: string;
  duration_minutes?: number;
  life_area?: string;
}

export interface CheckinCreate {
  user_id?: string;
  checkin_date?: string;
  wake_time?: string;
  sleep_quality?: number;
  energy_level?: number;
  body_status?: string;
  mood?: string;
  fixed_events: FixedEvent[];
  important_tasks: string[];
  raw_input?: string;
  available_hours?: number;
  day_constraints?: string;
}

export interface Checkin extends CheckinCreate {
  id: string;
  created_at: string;
}

// ─── Daily Plan ────────────────────────────────────────────────────────────────
export type BlockType =
  | "deep_work"
  | "admin"
  | "sport"
  | "break"
  | "social"
  | "learning"
  | "personal"
  | "other";

export interface TimeBlock {
  start_time: string;
  end_time: string;
  title: string;
  description?: string;
  life_area?: string;
  block_type?: BlockType;
}

export interface Priority {
  title: string;
  description?: string;
  life_area?: string;
  why?: string;
}

export interface DailyPlan {
  id: string;
  user_id: string;
  checkin_id?: string;
  plan_date: string;
  status_summary?: string;
  day_mode?: string;
  main_win?: string;
  top_priorities: Priority[];
  time_blocks: TimeBlock[];
  energy_strategy?: string;
  not_today_list: string[];
  evening_review_questions: string[];
  motivational_closing?: string;
  model_used?: string;
  generated_at?: string;
  created_at: string;
  review_context_used?: boolean;
}

// ─── Evening Review ────────────────────────────────────────────────────────────
export interface ReviewCreate {
  user_id?: string;
  plan_id?: string;
  review_date?: string;
  completed_items: string[];
  missed_items: string[];
  energy_end?: number;
  biggest_win?: string;
  lessons?: string;
  carry_over_to_tomorrow: string[];
  raw_reflection?: string;
  overall_day_rating?: number;
}

export interface EveningReview extends ReviewCreate {
  id: string;
  created_at: string;
}

// ─── User Rules ────────────────────────────────────────────────────────────────
export interface RuleCreate {
  user_id?: string;
  title: string;
  rule_text: string;
  category?: string;
  life_area_id?: string;
  is_active: boolean;
  priority: number;
}

export interface UserRule extends RuleCreate {
  id: string;
  created_at: string;
  updated_at: string;
}

// ─── Rule update (partial, excludes user_id) ──────────────────────────────────
export interface RuleUpdate {
  title?: string;
  rule_text?: string;
  category?: string;
  life_area_id?: string;
  is_active?: boolean;
  priority?: number;
}

// ─── Projects ──────────────────────────────────────────────────────────────────
export type ProjectStatus = "active" | "waiting" | "paused" | "backlog" | "done" | "archived";
export type ProjectPriority = "high" | "medium" | "low";

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  status: ProjectStatus;
  priority: ProjectPriority;
  next_action?: string;
  risk?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  status: ProjectStatus;
  priority: ProjectPriority;
  next_action?: string;
  risk?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: ProjectStatus;
  priority?: ProjectPriority;
  next_action?: string;
  risk?: string;
}

// ─── Background Dev Team — Control Plane ────────────────────────────────────────
// Field names are camelCase (unlike the snake_case API-mirroring types above).
// A real backend now exists (backend/app/models/work_order.py, snake_case,
// matching every other resource) — the two conventions meet in
// frontend/lib/workOrderMapper.ts, never here. See
// docs/background-dev-team-system-design.md §3 for why.

export type WorkOrderStatus =
  | "draft"             // defined, not yet approved to run
  | "approved"           // approval scope signed off, not yet queued
  | "queued"             // waiting for an executor to pick it up
  | "running"            // an agent run is actively executing
  | "needs_approval"     // paused — hit an action outside the autonomous-allowed list
  | "blocked"            // paused — missing context or an external dependency
  | "failed"             // an agent run failed; not reviewed as done
  | "review_ready"       // review package produced, waiting on human review
  | "accepted"           // human reviewed and accepted the outcome
  | "rework_requested"   // human reviewed and asked for changes
  | "cancelled";         // withdrawn before or during execution

export interface MissingContextItem {
  label: string;
  description?: string;
  required: boolean;
}

export interface ApprovalScope {
  id: string;
  workOrderId: string;
  allowedActions: string[];
  requiresApproval: string[];
  blockedActions: string[];
  allowedPaths?: string[];
  blockedPaths?: string[];
  maxRuntimeMinutes: number;
  maxCostUsd?: number;
}

export type AgentRole = "product" | "architect" | "coder" | "qa" | "reviewer" | "reporter";
export type AgentRunStatus = "queued" | "running" | "blocked" | "failed" | "completed";

export interface AgentRun {
  id: string;
  workOrderId: string;
  role: AgentRole;
  status: AgentRunStatus;
  inputSummary: string;
  outputSummary?: string;
  startedAt?: string;
  completedAt?: string;
  model?: string;
  // CP-OP02: which bounded-retry attempt this run represents (1 = first
  // attempt). Always 1 for a human-triggered run; > 1 only ever appears on
  // a run scripts/run_work_order.py's auto-retry loop created after a
  // harness-detected technical failure on the previous attempt.
  attemptNumber?: number;
  // Set only on attempt 2+ — a short machine-readable code (e.g.
  // "technical_failure_attempt_1") naming why the previous attempt was
  // retried. Never set on attempt 1.
  retryReason?: string;
}

export type WorkOrderStepStatus = "pending" | "queued" | "running" | "blocked" | "completed" | "failed" | "skipped";

// The visible execution/ticket plan — what Serkan actually looks at to
// answer "what's my background team doing right now." Distinct from
// AgentRun, which is the execution-level audit record for one role's run.
export interface WorkOrderStep {
  id: string;
  workOrderId: string;
  title: string;
  description?: string;
  status: WorkOrderStepStatus;
  assignedRole: AgentRole;
  orderIndex: number;
  acceptanceCriteria: string[];
  startedAt?: string;
  completedAt?: string;
  outputSummary?: string;
  blockedReason?: string;
  createdAt: string;
  updatedAt: string;
}

export type ActivityLogLevel = "info" | "warning" | "error" | "approval_required";

export interface ActivityLogEntry {
  id: string;
  workOrderId: string;
  agentRunId?: string;
  level: ActivityLogLevel;
  eventType: string;
  message: string;
  metadata?: Record<string, string>;
  createdAt: string;
}

export type ArtifactType = "plan" | "diff" | "test_output" | "review" | "summary" | "screenshot" | "prompt";

export interface Artifact {
  id: string;
  workOrderId: string;
  type: ArtifactType;
  title: string;
  content?: string;
  filePath?: string;
  createdAt: string;
}

export type ReviewVerdict = "ready_for_review" | "needs_fix" | "blocked" | "unsafe";

export interface ReviewPackage {
  id: string;
  workOrderId: string;
  summary: string;
  filesChanged: string[];
  testsRun: string[];
  risks: string[];
  openQuestions: string[];
  needsHumanReview: boolean;
  recommendedNextStep: string;
  verdict: ReviewVerdict;
}

export interface WorkOrder {
  id: string;
  title: string;
  goal: string;
  repo: string;
  status: WorkOrderStatus;
  approvalScopeId: string;
  createdBy: string;
  // Deliberately a plain string, not a union — "development" is the first
  // team type this system supports, not the only one it ever will.
  teamType: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  timeLimitMinutes: number;
  acceptanceCriteria: string[];
  recommendedNextStep?: string;
  missingContext?: MissingContextItem[];
  // Optional Control-Plane/Target-Repo split (OP-Runner-RepoPath-001):
  // `repo` above has always been a free-text label; these two let a work
  // order additionally point at an external project CommandPilot doesn't
  // live in (e.g. Sommercamps/CampsPilot) so the generated runner prompt
  // can tell a runner "you're working in a different repo than CommandPilot
  // itself." Both are pure display/prompt context — CommandPilot never
  // reads from or executes anything at targetRepoPath. See
  // frontend/lib/generateRunnerPrompt.ts and
  // frontend/components/operator/LocalRunnerPanel.tsx.
  targetRepoName?: string;
  targetRepoPath?: string;
}

// ─── Jarvis (second-brain chat) ──────────────────────────────────────────────────
export interface JarvisSourceRef {
  source_file: string;
  source_heading: string;
}

// Shaped to eventually seed a WorkOrderCreate (see WorkOrder above) — v1 never
// populates this, suggested_actions is always []. See backend/app/models/jarvis.py.
export interface JarvisSuggestedAction {
  title: string;
  description: string;
  team_type: string;
  target_repo_name?: string | null;
  risk: "low" | "medium" | "high";
  requires_approval: boolean;
  sources: JarvisSourceRef[];
}

export interface JarvisChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface JarvisChatRequest {
  message: string;
  history: JarvisChatMessage[];
}

export interface JarvisChatResponse {
  reply: string;
  sources: JarvisSourceRef[];
  suggested_actions: JarvisSuggestedAction[];
}

// ─── API responses ─────────────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}

export type GeneratePlanRequest = {
  checkin_id: string;
  user_id?: string;
};
