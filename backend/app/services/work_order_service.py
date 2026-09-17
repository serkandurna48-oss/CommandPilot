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

# Same idea, for agent_runs (see supabase/migrations/006_work_orders.sql).
# "blocked" counts as terminal here (unlike work order status, which has its
# own separate "blocked" meaning "needs approval mid-run") — an agent run
# that ends up blocked has stopped, same as failed/completed.
_AGENT_RUN_TERMINAL_STATUSES = {"completed", "failed", "blocked"}

logger = logging.getLogger(__name__)


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


def _extract_postgrest_message(exc: Exception) -> str:
    """Best-effort extraction of the human-readable message from whatever
    exception shape postgrest-py raises for a failed RPC call — different
    client versions expose this as `.message`, or as a dict in `.args[0]`.
    Falls back to `str(exc)` so a shape we didn't anticipate still surfaces
    *something* useful instead of a bare traceback."""
    message = getattr(exc, "message", None)
    if message:
        return str(message)
    args = getattr(exc, "args", None)
    if args and isinstance(args[0], dict):
        return str(args[0].get("message") or args[0])
    return str(exc)


def transition_work_order(work_order_id: str, to_status: str, source: str = "ui", reason: str | None = None) -> dict:
    """The only way work_orders.status may change (CP-OP01).

    Delegates to the transition_work_order() Postgres function (see
    supabase/migrations/010_transition_work_order_function.sql), which
    validates the transition against the authoritative state machine, checks
    per-edge preconditions (e.g. review_ready requires an existing review
    package), applies the status + started_at/completed_at update, and
    inserts the matching activity_logs audit entry — all inside one DB
    transaction. A successful transition without its audit entry is not
    possible; a rejected transition changes nothing.

    Raises:
        LookupError: work_order_id does not exist.
        ValueError: the transition is illegal or fails a precondition —
            callers should map this to HTTP 400.
    """
    db = get_db()
    try:
        result = db.rpc(
            "transition_work_order",
            {
                "p_work_order_id": work_order_id,
                "p_to_status": to_status,
                "p_source": source,
                "p_reason": reason,
            },
        ).execute()
    except Exception as exc:
        message = _extract_postgrest_message(exc)
        if "work_order_not_found" in message:
            raise LookupError(work_order_id) from exc
        raise ValueError(message) from exc

    data = result.data
    if isinstance(data, list):
        data = data[0] if data else None
    if not data:
        raise LookupError(work_order_id)

    scope = _maybe_single(db.table("approval_scopes").select("id").eq("work_order_id", work_order_id).maybe_single())
    return _attach_approval_scope_id(data, scope)


def update_work_order_fields(work_order_id: str, updates: dict) -> dict | None:
    """Applies non-status work_order field updates (recommended_next_step,
    missing_context). Status changes must go through transition_work_order()
    instead — this function deliberately refuses to touch `status` so a
    future regression can't silently reintroduce the unvalidated
    any-status-to-any-status write CP-OP01 removed."""
    if "status" in updates:
        raise ValueError("update_work_order_fields() must not receive 'status' — use transition_work_order() instead")

    db = get_db()
    if "missing_context" in updates and updates["missing_context"] is not None:
        updates["missing_context"] = [m.model_dump() if hasattr(m, "model_dump") else m for m in updates["missing_context"]]

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
        "dedup_key": data.dedup_key,
    }
    # Upsert on (work_order_id, dedup_key) (CP-OP03): when the import script
    # sets dedup_key, a repeated or corrected re-import of the same
    # agent_run's result updates the same slot instead of duplicating it.
    # Every other caller leaves dedup_key None — Postgres never treats two
    # NULLs as equal for uniqueness, so an upsert with dedup_key=None can
    # never match an existing row and behaves exactly like a plain insert.
    result = db.table("activity_logs").upsert(payload, on_conflict="work_order_id,dedup_key").execute()
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
        "attempt_number": data.attempt_number,
        "retry_reason": data.retry_reason,
    }
    # A run can be created already "running" (the runner harness creates it
    # at the same moment it starts the session, see scripts/run_work_order.py
    # OP-Runner-Session-001) — mirror update_agent_run's timestamp-on-status
    # logic here too, otherwise a run created directly as "running" would
    # never get a started_at and the UI couldn't show when it started.
    if payload["status"] == "running":
        payload.setdefault("started_at", _now_iso())
    result = db.table("agent_runs").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Agent run insert returned no data")
    return result.data[0]


def update_agent_run(run_id: str, work_order_id: str, updates: dict) -> dict | None:
    db = get_db()
    status = updates.get("status")
    if status == "running":
        updates.setdefault("started_at", _now_iso())
    elif status in _AGENT_RUN_TERMINAL_STATUSES:
        updates.setdefault("completed_at", _now_iso())
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
        "dedup_key": data.dedup_key,
    }
    # See append_activity_log()'s comment — same upsert-on-(work_order_id,
    # dedup_key) idempotency pattern (CP-OP03).
    result = db.table("artifacts").upsert(payload, on_conflict="work_order_id,dedup_key").execute()
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
