"""
CommandPilot — Suggested Action confirm/reject (JARVIS-C1)

Bridges a Jarvis chat proposal (app/models/jarvis.py SuggestedAction — never
persisted at chat time, see app/routers/jarvis.py's chat endpoint) to a real
work order. A proposal becomes a work order only when a human confirms it
here; nothing is written on the chat turn itself.

Reuses work_order_service.create_work_order() (work order + approval scope
in one transaction, with its existing rollback-on-scope-failure) and
work_order_service.append_activity_log() — this module does not talk to
work_orders/approval_scopes/activity_logs directly, only to
suggested_action_decisions, so there is exactly one work-order-creation path
in the codebase, not two.

Idempotency (Phase 6): request_id is a client-generated token, one per
suggested-action card, reused across retries of the same click. The
suggested_action_decisions table's UNIQUE(user_id, request_id) index (see
supabase/migrations/013_suggested_action_decisions.sql) is the actual guard
against a double-click/retry creating two work orders for one proposal — the
functions below claim that row *before* doing anything expensive, so the
guarantee holds even under concurrent requests, not just sequential retries.
A decision, once recorded, is immutable: a later request for the same
request_id with a *different* decision raises AlreadyDecidedError rather
than silently applying it.
"""
import logging

from app.db.client import get_db
from app.models.jarvis import SuggestedAction
from app.models.work_order import ActivityLogCreate, ApprovalScopeCreate, WorkOrderCreate
from app.services import work_order_service

logger = logging.getLogger(__name__)

_TABLE = "suggested_action_decisions"


class AlreadyDecidedError(Exception):
    """A decision already exists for this request_id, and it differs from
    the one now being requested (e.g. reject called on an already-confirmed
    request_id). Callers should map this to HTTP 409."""

    def __init__(self, existing_decision: str, work_order_id: str | None):
        self.existing_decision = existing_decision
        self.work_order_id = work_order_id
        super().__init__(f"request_id already decided as {existing_decision!r}")


# ─── Default Approval Scope ──────────────────────────────────────────────────────
# Mirrors frontend/components/operator/CreateWorkOrderForm.tsx's manual-creation
# defaults exactly — a work order created from a confirmed Jarvis suggestion
# starts from the same safe baseline as one created by hand, not a separate,
# looser posture.
_DEFAULT_ALLOWED_ACTIONS = [
    "repo_read", "plan_create", "code_edit_within_scope",
    "test_lint_typecheck", "local_artifacts", "review_package_write",
]
_DEFAULT_REQUIRES_APPROVAL_ACTIONS = [
    "dependency_install", "external_service_change", "migration_execute",
    "push_or_pr_create", "runtime_or_cost_increase", "major_architecture_change",
]
_DEFAULT_BLOCKED_ACTIONS = [
    "deploy", "production_data_write", "secrets_read_or_log", "email_send",
    "payment_action", "destructive_git", "direct_main_change", "user_data_export",
]
_DEFAULT_ALLOWED_PATHS = ["frontend/**", "backend/**", "scripts/**", "docs/**", "supabase/migrations/**"]
_DEFAULT_BLOCKED_PATHS = [".env", ".env.*", "**/node_modules/**", "**/.git/**", "**/secrets/**", "**/*key*", "**/*token*"]
_DEFAULT_TIME_LIMIT_MINUTES = 90


def _default_approval_scope(requires_approval: bool) -> ApprovalScopeCreate:
    """
    When the proposal itself is flagged requires_approval=True, nothing is
    auto-allowed — every action, not just the sensitive ones (dependency
    installs, migrations, pushes), waits for a human nod. Otherwise the
    normal split applies: routine actions auto-allowed, sensitive ones need
    approval, a fixed set always blocked regardless.
    """
    if requires_approval:
        return ApprovalScopeCreate(
            allowed_actions=[],
            requires_approval=_DEFAULT_ALLOWED_ACTIONS + _DEFAULT_REQUIRES_APPROVAL_ACTIONS,
            blocked_actions=_DEFAULT_BLOCKED_ACTIONS,
            allowed_paths=_DEFAULT_ALLOWED_PATHS,
            blocked_paths=_DEFAULT_BLOCKED_PATHS,
            max_runtime_minutes=_DEFAULT_TIME_LIMIT_MINUTES,
        )
    return ApprovalScopeCreate(
        allowed_actions=_DEFAULT_ALLOWED_ACTIONS,
        requires_approval=_DEFAULT_REQUIRES_APPROVAL_ACTIONS,
        blocked_actions=_DEFAULT_BLOCKED_ACTIONS,
        allowed_paths=_DEFAULT_ALLOWED_PATHS,
        blocked_paths=_DEFAULT_BLOCKED_PATHS,
        max_runtime_minutes=_DEFAULT_TIME_LIMIT_MINUTES,
    )


def _build_work_order_create(action: SuggestedAction) -> WorkOrderCreate:
    return WorkOrderCreate(
        title=action.title,
        goal=action.description,
        team_type=action.team_type,
        target_repo_name=action.target_repo_name,
        approval_scope=_default_approval_scope(action.requires_approval),
    )


def _source_labels(action: SuggestedAction) -> str:
    if not action.sources:
        return "–"
    return ", ".join(
        f"{s.source_file}{' — ' + s.source_heading if s.source_heading else ''}"
        for s in action.sources
    )


def _get_existing_decision(user_id: str, request_id: str) -> dict | None:
    db = get_db()
    result = (
        db.table(_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("request_id", request_id)
        .execute()
    )
    return result.data[0] if result.data else None


def _claim_request_id(
    user_id: str, workspace_id: str | None, request_id: str, decision: str, action: SuggestedAction
) -> dict | None:
    """
    Insert-first: the UNIQUE(user_id, request_id) index is what actually
    makes this atomic under concurrent requests. Returns the inserted row on
    success, or None if another request already claimed this request_id
    (unique-violation) — the caller re-fetches the winning row.
    """
    db = get_db()
    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "request_id": request_id,
        "decision": decision,
        "title": action.title,
        "team_type": action.team_type,
        "target_repo_name": action.target_repo_name,
        "risk": action.risk,
        "requires_approval": action.requires_approval,
        "sources": [s.model_dump() for s in action.sources],
        "work_order_id": None,
    }
    try:
        result = db.table(_TABLE).insert(payload).execute()
    except Exception as exc:
        logger.info(
            "suggested_action_decisions insert lost the race for request_id=%s — treating as already decided | %s",
            request_id, exc,
        )
        return None
    return result.data[0] if result.data else None


def _resolve_lost_race(user_id: str, request_id: str, wanted_decision: str) -> dict:
    existing = _get_existing_decision(user_id, request_id)
    if existing is None:
        # The insert failed for a reason other than the unique constraint
        # (e.g. a real DB error) — surface as a normal error rather than
        # silently claiming success.
        raise RuntimeError("Failed to record suggested-action decision")
    if existing["decision"] != wanted_decision:
        raise AlreadyDecidedError(existing["decision"], existing.get("work_order_id"))
    return {
        "decision": existing["decision"],
        "work_order_id": existing.get("work_order_id"),
        "already_decided": True,
    }


def confirm_suggested_action(
    user_id: str, workspace_id: str | None, created_by: str, action: SuggestedAction, request_id: str
) -> dict:
    existing = _get_existing_decision(user_id, request_id)
    if existing:
        if existing["decision"] != "confirmed":
            raise AlreadyDecidedError(existing["decision"], existing.get("work_order_id"))
        return {"decision": "confirmed", "work_order_id": existing["work_order_id"], "already_decided": True}

    claim = _claim_request_id(user_id, workspace_id, request_id, "confirmed", action)
    if claim is None:
        return _resolve_lost_race(user_id, request_id, "confirmed")

    try:
        order = work_order_service.create_work_order(
            user_id, workspace_id, created_by, _build_work_order_create(action)
        )
        work_order_service.append_activity_log(
            order["id"],
            ActivityLogCreate(
                level="info",
                event_type="jarvis_suggestion_confirmed",
                message=(
                    f"Aus Jarvis-Vorschlag übernommen (Risiko: {action.risk}, "
                    f"genehmigungspflichtig: {'ja' if action.requires_approval else 'nein'}). "
                    f"Quellen: {_source_labels(action)}."
                ),
            ),
        )
    except Exception:
        # Release the claim so the same request_id can be retried cleanly —
        # mirrors work_order_service.create_work_order()'s own
        # compensate-on-failure precedent for its approval_scope insert.
        logger.error(
            "Work order creation failed after claiming request_id=%s — releasing claim so it can be retried",
            request_id,
        )
        get_db().table(_TABLE).delete().eq("id", claim["id"]).execute()
        raise

    get_db().table(_TABLE).update({"work_order_id": order["id"]}).eq("id", claim["id"]).execute()
    return {"decision": "confirmed", "work_order_id": order["id"], "already_decided": False}


def reject_suggested_action(
    user_id: str, workspace_id: str | None, action: SuggestedAction, request_id: str
) -> dict:
    existing = _get_existing_decision(user_id, request_id)
    if existing:
        if existing["decision"] != "rejected":
            raise AlreadyDecidedError(existing["decision"], existing.get("work_order_id"))
        return {"decision": "rejected", "work_order_id": None, "already_decided": True}

    claim = _claim_request_id(user_id, workspace_id, request_id, "rejected", action)
    if claim is None:
        return _resolve_lost_race(user_id, request_id, "rejected")

    # Rejecting has no side effect beyond the row itself — that row IS the
    # entire audit trail for a rejected proposal (see the migration's header
    # comment for why activity_logs can't represent this).
    return {"decision": "rejected", "work_order_id": None, "already_decided": False}
