from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

from app.core.safety_rules import validate_approval_scope

WorkOrderStatusLiteral = Literal[
    "draft", "approved", "queued", "running",
    "needs_approval", "blocked", "failed",
    "review_ready", "accepted", "rework_requested", "cancelled",
]
AgentRoleLiteral = Literal["product", "architect", "coder", "qa", "reviewer", "reporter"]
AgentRunStatusLiteral = Literal["queued", "running", "blocked", "failed", "completed"]
ActivityLogLevelLiteral = Literal["info", "warning", "error", "approval_required"]
ArtifactTypeLiteral = Literal["plan", "diff", "test_output", "review", "summary", "screenshot", "prompt"]
ReviewVerdictLiteral = Literal["ready_for_review", "needs_fix", "blocked", "unsafe"]
WorkOrderStepStatusLiteral = Literal["pending", "queued", "running", "blocked", "completed", "failed", "skipped"]


class MissingContextItem(BaseModel):
    label: str
    description: Optional[str] = None
    required: bool = True


# ─── Approval Scope ─────────────────────────────────────────────────────────────
class ApprovalScopeCreate(BaseModel):
    allowed_actions: list[str] = []
    requires_approval: list[str] = []
    blocked_actions: list[str] = []
    allowed_paths: Optional[list[str]] = None
    blocked_paths: Optional[list[str]] = None
    max_runtime_minutes: int = Field(..., gt=0)
    max_cost_usd: Optional[float] = None

    @model_validator(mode="after")
    def _reject_blocked_actions(self):
        # Enforced at the model layer so no code path — API, future import
        # script, future UI form — can create a scope that smuggles a
        # repo-wide-blocked action into allowed_actions/requires_approval.
        # See app/core/safety_rules.py.
        validate_approval_scope(self.allowed_actions, self.requires_approval)
        return self


class ApprovalScopeResponse(BaseModel):
    # Deliberately NOT a subclass of ApprovalScopeCreate: its blocked-action
    # validator belongs on the write path only. A read should never 500
    # because of a scope that (somehow) already exists in the DB — it should
    # just be rejected from ever being written that way in the first place.
    id: str
    work_order_id: str
    allowed_actions: list[str] = []
    requires_approval: list[str] = []
    blocked_actions: list[str] = []
    allowed_paths: Optional[list[str]] = None
    blocked_paths: Optional[list[str]] = None
    max_runtime_minutes: int
    max_cost_usd: Optional[float] = None
    created_at: str


# ─── Agent Run ──────────────────────────────────────────────────────────────────
class AgentRunCreate(BaseModel):
    role: AgentRoleLiteral
    status: AgentRunStatusLiteral = "queued"
    input_summary: str = Field(..., min_length=1, max_length=2000)
    output_summary: Optional[str] = Field(None, max_length=2000)
    model: Optional[str] = None


class AgentRunUpdate(BaseModel):
    status: Optional[AgentRunStatusLiteral] = None
    output_summary: Optional[str] = Field(None, max_length=2000)
    model: Optional[str] = None


class AgentRunResponse(BaseModel):
    id: str
    work_order_id: str
    role: str
    status: str
    input_summary: str
    output_summary: Optional[str] = None
    model: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str


# ─── Activity Log ───────────────────────────────────────────────────────────────
class ActivityLogCreate(BaseModel):
    agent_run_id: Optional[str] = None
    level: ActivityLogLevelLiteral
    event_type: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=2000)
    metadata: Optional[dict] = None


class ActivityLogResponse(BaseModel):
    id: str
    work_order_id: str
    agent_run_id: Optional[str] = None
    level: str
    event_type: str
    message: str
    metadata: Optional[dict] = None
    created_at: str


# ─── Artifact ───────────────────────────────────────────────────────────────────
class ArtifactCreate(BaseModel):
    type: ArtifactTypeLiteral
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = None
    file_path: Optional[str] = None


class ArtifactResponse(BaseModel):
    id: str
    work_order_id: str
    type: str
    title: str
    content: Optional[str] = None
    file_path: Optional[str] = None
    created_at: str


# ─── Review Package ─────────────────────────────────────────────────────────────
class ReviewPackageCreate(BaseModel):
    summary: str = Field(..., min_length=1, max_length=4000)
    files_changed: list[str] = []
    tests_run: list[str] = []
    risks: list[str] = []
    open_questions: list[str] = []
    needs_human_review: bool = True
    recommended_next_step: Optional[str] = None
    verdict: ReviewVerdictLiteral


class ReviewPackageResponse(ReviewPackageCreate):
    id: str
    work_order_id: str
    created_at: str
    updated_at: str


# ─── Work Order Step (the visible execution/ticket plan) ───────────────────────
class WorkOrderStepCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    assigned_role: AgentRoleLiteral
    order_index: Optional[int] = None
    acceptance_criteria: list[str] = []


class WorkOrderStepUpdate(BaseModel):
    status: Optional[WorkOrderStepStatusLiteral] = None
    output_summary: Optional[str] = Field(None, max_length=4000)
    blocked_reason: Optional[str] = Field(None, max_length=2000)


class WorkOrderStepResponse(BaseModel):
    id: str
    work_order_id: str
    title: str
    description: Optional[str] = None
    status: str
    assigned_role: str
    order_index: int
    acceptance_criteria: list[str] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_summary: Optional[str] = None
    blocked_reason: Optional[str] = None
    created_at: str
    updated_at: str


# ─── Work Order ─────────────────────────────────────────────────────────────────
class WorkOrderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=4000)
    repo: str = Field("commandpilot", min_length=1, max_length=200)
    # Deliberately a plain string, not a Literal — "development" is the first
    # team type, not the only one. See supabase/migrations/008_work_orders_team_type.sql.
    team_type: str = Field("development", min_length=1, max_length=100)
    time_limit_minutes: int = Field(90, gt=0)
    acceptance_criteria: list[str] = []
    missing_context: list[MissingContextItem] = []
    approval_scope: ApprovalScopeCreate
    steps: list[WorkOrderStepCreate] = []
    # Optional Control-Plane/Target-Repo split (OP-Runner-RepoPath-001): a
    # work order's `repo` field has always been a free-text label, but
    # nothing distinguished "this work order edits CommandPilot itself" from
    # "this work order edits an external project CommandPilot doesn't live
    # in" — the generated runner prompt read the same either way, which
    # confused a runner started against an external repo (it expects
    # scripts/run_work_order.py or CommandPilot import paths to exist there,
    # and they don't). Both fields are pure display/prompt context — never
    # read by the backend for anything beyond storing and echoing back, and
    # never used to cd into or execute anything at that path. See
    # frontend/lib/generateRunnerPrompt.ts and
    # scripts/runner_adapters/base.py's build_runner_prompt() for where they
    # actually change behavior (prompt text only).
    target_repo_name: Optional[str] = Field(None, max_length=200)
    target_repo_path: Optional[str] = Field(None, max_length=500)


class WorkOrderUpdate(BaseModel):
    status: Optional[WorkOrderStatusLiteral] = None
    recommended_next_step: Optional[str] = None
    missing_context: Optional[list[MissingContextItem]] = None


class WorkOrderResponse(BaseModel):
    id: str
    user_id: str
    workspace_id: Optional[str] = None
    title: str
    goal: str
    repo: str
    status: str
    approval_scope_id: Optional[str] = None
    created_by: str
    team_type: str
    time_limit_minutes: int
    acceptance_criteria: list[str] = []
    missing_context: list[MissingContextItem] = []
    recommended_next_step: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    target_repo_name: Optional[str] = None
    target_repo_path: Optional[str] = None


class WorkOrderDetailResponse(WorkOrderResponse):
    approval_scope: Optional[ApprovalScopeResponse] = None
    steps: list[WorkOrderStepResponse] = []
    agent_runs: list[AgentRunResponse] = []
    activity_log: list[ActivityLogResponse] = []
    artifacts: list[ArtifactResponse] = []
    review_package: Optional[ReviewPackageResponse] = None
