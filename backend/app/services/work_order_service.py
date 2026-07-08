import logging
from datetime import datetime, timezone

from app.db.client import get_db
from app.models.work_order import (
    ActivityLogCreate,
    AgentRunCreate,
    ArtifactCreate,
    ReviewPackageCreate,
    WorkOrderCreate,
    WorkOrderStepCreate,
)

# Step statuses that mark a step as no longer active — mirrors the work
# order-level _TERMINAL_STATUSES/_STARTED_STATUSES derivation below, but for
# the smaller per-step lifecycle (see supabase/migrations/007_work_order_steps.sql).
_STEP_TERMINAL_STATUSES = {"completed", "failed", "skipped"}

logger = logging.getLogger(__name__)

# Status values that mark a work order as no longer active — reaching one of
# these sets completed_at if it isn't already set. Never trusts a
# client-supplied timestamp; both started_at and completed_at are derived
# server-side from the status transition, matching the request_date /
# generated_at pattern used elsewhere in this backend.
_TERMINAL_STATUSES = {"accepted", "failed", "cancelled"}
_STARTED_STATUSES = {"running", "needs_approval", "blocked", "review_ready", "accepted", "rework_requested"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _maybe_single(query) -> dict | None:
    """Safely unwraps a `.maybe_single()` query.

    The installed supabase/postgrest client returns `None` from `.execute()`
    itself (not a response object with `.data = None`) when a
    `.maybe_single()` query matches zero rows — `app/auth.py`'s
    `get_current_user` already works around this same quirk for the
    profile lookup. Every `.maybe_single()` call in this module goes
    through this helper so "zero rows" (the normal state for, say, a draft
    work order's review_package) returns `None` cleanly instead of crashing
    with `AttributeError: 'NoneType' object has no attribute 'data'`.
    """
    result = query.execute()
    return result.data if result else None


def _attach_approval_scope_id(order: dict, scope: dict | None) -> dict:
    order["approval_scope_id"] = scope["id"] if scope else None
    return order


def create_work_order(user_id: str, workspace_id: str | None, created_by: str, data: WorkOrderCreate) -> dict:
    db = get_db()

    order_payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "title": data.title,
        "goal": data.goal,
        "repo": data.repo,
        "created_by": created_by,
        "team_type": data.team_type,
        "time_limit_minutes": data.time_limit_minutes,
        "acceptance_criteria": [c for c in data.acceptance_criteria],
        "missing_context": [m.model_dump() for m in data.missing_context],
        "target_repo_name": data.target_repo_name,
        "target_repo_path": data.target_repo_path,
    }
    order_result = db.table("work_orders").insert(order_payload).execute()
    if not order_result.data:
        raise RuntimeError("Work order insert returned no data")
    order = order_result.data[0]

    scope_payload = {
        "work_order_id": order["id"],
        "allowed_actions": data.approval_scope.allowed_actions,
        "requires_approval": data.approval_scope.requires_approval,
        "blocked_actions": data.approval_scope.blocked_actions,
        "allowed_paths": data.approval_scope.allowed_paths,
        "blocked_paths": data.approval_scope.blocked_paths,
        "max_runtime_minutes": data.approval_scope.max_runtime_minutes,
        "max_cost_usd": data.approval_scope.max_cost_usd,
    }
    try:
        scope_result = db.table("approval_scopes").insert(scope_payload).execute()
        if not scope_result.data:
            raise RuntimeError("Approval scope insert returned no data")
    except Exception:
        # Compensate: a work order without an approval scope violates the
        # "one-time approval scope defines the allowed frame" principle, so
        # don't leave an orphaned, effectively-unscoped work order behind.
        logger.error("Approval scope insert failed — rolling back work_order %s", order["id"])
        db.table("work_orders").delete().eq("id", order["id"]).execute()
        raise

    if data.steps:
        step_rows = [
            {
                "work_order_id": order["id"],
                "title": s.title,
                "description": s.description,
                "assigned_role": s.assigned_role,
                "order_index": s.order_index if s.order_index is not None else i,
                "acceptance_criteria": s.acceptance_criteria,
            }
            for i, s in enumerate(data.steps)
        ]
        try:
            db.table("work_order_steps").insert(step_rows).execute()
        except Exception:
            # Non-fatal: the work order and its approval scope are already
            # valid on their own — a failed initial plan can be re-added via
            # POST /{id}/steps. Don't roll back the whole work order for it.
            logger.error("Initial step batch insert failed for work_order %s — continuing without steps", order["id"])

    return _attach_approval_scope_id(order, scope_result.data[0])


def get_work_orders_for_user(user_id: str) -> list[dict]:
    db = get_db()
    orders = (
        db.table("work_orders")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    if not orders:
        return []

    order_ids = [o["id"] for o in orders]
    scopes = (
        db.table("approval_scopes")
        .select("id, work_order_id")
        .in_("work_order_id", order_ids)
        .execute()
        .data
        or []
    )
    scope_by_wo = {s["work_order_id"]: s["id"] for s in scopes}
    for o in orders:
        o["approval_scope_id"] = scope_by_wo.get(o["id"])
    return orders


def get_work_order_children(work_order_id: str) -> dict:
    """Fetches everything scoped to an already-ownership-verified work order.

    Callers must verify ownership first (e.g. via auth.require_owned_record on
    "work_orders") — this function trusts work_order_id without re-checking
    user_id, matching how the rest of this backend separates the ownership
    check (router layer) from data access (service layer).
    """
    db = get_db()
    scope = _maybe_single(
        db.table("approval_scopes")
        .select("*")
        .eq("work_order_id", work_order_id)
        .maybe_single()
    )
    steps = (
        db.table("work_order_steps")
        .select("*")
        .eq("work_order_id", work_order_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    agent_runs = (
        db.table("agent_runs")
        .select("*")
        .eq("work_order_id", work_order_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    activity_log = (
        db.table("activity_logs")
        .select("*")
        .eq("work_order_id", work_order_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    artifacts = (
        db.table("artifacts")
        .select("*")
        .eq("work_order_id", work_order_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    review_package = _maybe_single(
        db.table("review_packages")
        .select("*")
        .eq("work_order_id", work_order_id)
        .maybe_single()
    )
    return {
        "approval_scope": scope,
        "steps": steps,
        "agent_runs": agent_runs,
        "activity_log": activity_log,
        "artifacts": artifacts,
        "review_package": review_package,
    }


def update_work_order(work_order_id: str, updates: dict) -> dict | None:
    db = get_db()

    if "missing_context" in updates and updates["missing_context"] is not None:
        updates["missing_context"] = [m.model_dump() if hasattr(m, "model_dump") else m for m in updates["missing_context"]]

    status = updates.get("status")
    if status in _STARTED_STATUSES:
        # Only set started_at if it isn't already set — don't overwrite the
        # original start time on every subsequent status change.
        existing = _maybe_single(db.table("work_orders").select("started_at").eq("id", work_order_id).maybe_single())
        if existing and not existing.get("started_at"):
            updates["started_at"] = _now_iso()
    if status in _TERMINAL_STATUSES:
        updates["completed_at"] = _now_iso()

    result = db.table("work_orders").update(updates).eq("id", work_order_id).execute()
    if not result.data:
        return None
    order = result.data[0]
    scope = _maybe_single(db.table("approval_scopes").select("id").eq("work_order_id", work_order_id).maybe_single())
    return _attach_approval_scope_id(order, scope)


def append_activity_log(work_order_id: str, data: ActivityLogCreate) -> dict:
    db = get_db()
    payload = {
        "work_order_id": work_order_id,
        "agent_run_id": data.agent_run_id,
        "level": data.level,
        "event_type": data.event_type,
        "message": data.message,
        "metadata": data.metadata,
    }
    result = db.table("activity_logs").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Activity log insert returned no data")
    return result.data[0]


def create_agent_run(work_order_id: str, data: AgentRunCreate) -> dict:
    db = get_db()
    payload = {
        "work_order_id": work_order_id,
        "role": data.role,
        "status": data.status,
        "input_summary": data.input_summary,
        "output_summary": data.output_summary,
        "model": data.model,
    }
    result = db.table("agent_runs").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Agent run insert returned no data")
    return result.data[0]


def update_agent_run(run_id: str, work_order_id: str, updates: dict) -> dict | None:
    db = get_db()
    if updates.get("status") == "completed":
        updates.setdefault("completed_at", _now_iso())
    elif updates.get("status") == "running":
        updates.setdefault("started_at", _now_iso())
    result = (
        db.table("agent_runs")
        .update(updates)
        .eq("id", run_id)
        .eq("work_order_id", work_order_id)  # scope to the verified work order — never trust run_id alone
        .execute()
    )
    return result.data[0] if result.data else None


def create_artifact(work_order_id: str, data: ArtifactCreate) -> dict:
    db = get_db()
    payload = {
        "work_order_id": work_order_id,
        "type": data.type,
        "title": data.title,
        "content": data.content,
        "file_path": data.file_path,
    }
    result = db.table("artifacts").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Artifact insert returned no data")
    return result.data[0]


def create_step(work_order_id: str, data: WorkOrderStepCreate) -> dict:
    db = get_db()
    if data.order_index is None:
        existing = (
            db.table("work_order_steps")
            .select("order_index")
            .eq("work_order_id", work_order_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
            .data
        )
        next_index = (existing[0]["order_index"] + 1) if existing else 0
    else:
        next_index = data.order_index
    payload = {
        "work_order_id": work_order_id,
        "title": data.title,
        "description": data.description,
        "assigned_role": data.assigned_role,
        "order_index": next_index,
        "acceptance_criteria": data.acceptance_criteria,
    }
    result = db.table("work_order_steps").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Work order step insert returned no data")
    return result.data[0]


def update_step(step_id: str, work_order_id: str, updates: dict) -> dict | None:
    db = get_db()
    status = updates.get("status")
    if status == "running":
        updates.setdefault("started_at", _now_iso())
    elif status in _STEP_TERMINAL_STATUSES:
        updates.setdefault("completed_at", _now_iso())
    updates["updated_at"] = _now_iso()
    result = (
        db.table("work_order_steps")
        .update(updates)
        .eq("id", step_id)
        .eq("work_order_id", work_order_id)  # scope to the verified work order — never trust step_id alone
        .execute()
    )
    return result.data[0] if result.data else None


def upsert_review_package(work_order_id: str, data: ReviewPackageCreate) -> dict:
    db = get_db()
    payload = {
        "work_order_id": work_order_id,
        "summary": data.summary,
        "files_changed": data.files_changed,
        "tests_run": data.tests_run,
        "risks": data.risks,
        "open_questions": data.open_questions,
        "needs_human_review": data.needs_human_review,
        "recommended_next_step": data.recommended_next_step,
        "verdict": data.verdict,
        "updated_at": _now_iso(),
    }
    result = db.table("review_packages").upsert(payload, on_conflict="work_order_id").execute()
    if not result.data:
        raise RuntimeError("Review package upsert returned no data")
    return result.data[0]
