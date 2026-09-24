import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.client import get_db
from app.services.runner_connection_service import RUNNER_TOKEN_PREFIX

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    workspace_id: str | None


def _get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return credentials.credentials


def _resolve_runner_token(db, token: str) -> CurrentUser | None:
    """Accepts a paired local-runner token (scripts/run_work_order_daemon.py,
    supabase/migrations/017_runner_connections.sql) as a drop-in alternative
    to a real Supabase session — resolves to the SAME CurrentUser shape, so
    every existing ownership check downstream (require_owned_record,
    .eq("user_id", ...)) keeps working unchanged; the runner is simply a
    second way to prove "I am this specific, already-onboarded user."

    Returns None immediately (no DB call at all) for anything that isn't
    prefixed as a runner token — a real Supabase JWT never matches this, so
    the normal frontend request path pays nothing for this check existing.
    An unknown, revoked, or not-yet-approved (user_id still NULL) token
    returns None too, falling through to the real 401 below — never a
    silent partial success.
    """
    if not token.startswith(RUNNER_TOKEN_PREFIX):
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    # maybe_single().execute() returns None outright (not a response object
    # with .data=None) when zero rows match — postgrest-py 2.30.0 behavior,
    # same as runner_connection_service.py's _find_pending_request/
    # poll_pairing_status. A revoked or unknown token is the expected common
    # case here, not an error — caught live 23.09.2026 when revoking a real
    # paired connection and then reusing its token crashed this dependency
    # with a 500 instead of the intended clean 401.
    response = (
        db.table("runner_connections")
        .select("*")
        .eq("token_hash", token_hash)
        .is_("revoked_at", "null")
        .maybe_single()
        .execute()
    )
    row = response.data if response else None
    if not row or not row.get("user_id"):
        return None

    # Best-effort — a failed timestamp update must never block a real,
    # already-validated request.
    try:
        db.table("runner_connections").update(
            {"last_used_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", row["id"]).execute()
    except Exception:
        logger.warning("runner_connections.last_used_at update failed for connection_id=%s", row["id"])

    return CurrentUser(id=row["user_id"], email=None, workspace_id=row.get("workspace_id"))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Browser-session only — a runner token is NOT accepted here.

    CMD-002 (found in review, 24.09.2026): this used to accept a runner
    token transparently, same as a real Supabase session, for EVERY
    endpoint that depends on it — including routers with nothing to do
    with work orders (projects.py, plans.py, jarvis.py, rules.py, ...). A
    runner script only ever needs to claim/report on work orders; a runner
    token resolving to full account access everywhere else meant a single
    leaked/compromised runner token could read or write anything the real
    account owner could, in any router, not just work_orders.py. Live-
    reproduced: a paired runner token successfully called GET
    /api/projects/me and got the owner's real projects back.

    Runner tokens are now opt-in per router via get_current_user_or_runner
    (see below) — work_orders.py is the only router that should ever use
    it, since that's the only surface a runner script actually calls.
    """
    return get_current_browser_user(credentials)


def get_current_user_or_runner(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Accepts EITHER a real Supabase session OR a paired runner token.
    Use only where a local runner script legitimately needs to call the
    endpoint — currently just routers/work_orders.py. Every other router
    should keep using the browser-only get_current_user (see its
    docstring for why — CMD-002).
    """
    token = _get_bearer_token(credentials)
    db = get_db()

    runner_user = _resolve_runner_token(db, token)
    if runner_user is not None:
        return runner_user

    return _resolve_supabase_session(db, token)


def get_current_browser_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Same as get_current_user, but explicitly, locally rejects a runner
    token with 401 rather than just never having accepted one — for
    endpoints where being extra explicit about "no runner token, ever"
    earns its keep, e.g. approving a NEW pairing request
    (routers/runner_pairing.py's approve_pairing): letting a runner token
    self-approve further pairing requests would let a single compromised/
    leaked runner token mint arbitrarily more of itself, with no browser
    session ever involved. get_current_user (above) now has the same
    effective behavior; this name stays for that self-documenting intent
    at the call site.
    """
    token = _get_bearer_token(credentials)
    if token.startswith(RUNNER_TOKEN_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A runner token cannot be used here — log in via the browser to approve a pairing request.",
        )
    return _resolve_supabase_session(get_db(), token)


def _resolve_supabase_session(db, token: str) -> CurrentUser:
    try:
        auth_response = db.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    auth_user = getattr(auth_response, "user", None)
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user_id = str(auth_user.id)

    profile = (
        db.table("profiles")
        .select("workspace_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    return CurrentUser(
        id=user_id,
        email=getattr(auth_user, "email", None),
        workspace_id=(profile.data if profile else {}).get("workspace_id"),
    )


def ensure_user_workspace(user: CurrentUser) -> dict:
    db = get_db()

    # ── Profile ──────────────────────────────────────────────────────────────
    profile_result = (
        db.table("profiles")
        .select("*")
        .eq("id", user.id)
        .maybe_single()
        .execute()
    )
    profile = profile_result.data if profile_result else None
    profile_exists = profile is not None

    logger.info(
        "ensure_user_workspace | user_id=%s | profile_exists=%s",
        user.id,
        profile_exists,
    )

    if not profile:
        insert_result = (
            db.table("profiles")
            .insert({"id": user.id, "display_name": user.email})
            .execute()
        )
        if not insert_result.data:
            logger.error(
                "ensure_user_workspace | profile insert returned no data | user_id=%s",
                user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "USER_SETUP_FAILED",
                    "message": "Account setup could not be completed. Please try again.",
                },
            )
        profile = insert_result.data[0]
        logger.info("ensure_user_workspace | profile created | user_id=%s", user.id)

    # ── Workspace ─────────────────────────────────────────────────────────────
    workspace_id = profile.get("workspace_id")
    logger.info(
        "ensure_user_workspace | workspace_id_present=%s | user_id=%s",
        bool(workspace_id),
        user.id,
    )

    if not workspace_id:
        workspace_slug = f"personal-{user.id.replace('-', '')}"

        # Mirror the SQL trigger's logic: look up an existing workspace by slug
        # before inserting.  The trigger (handle_new_user) may have already
        # created it with ON CONFLICT DO NOTHING, leaving profiles.workspace_id
        # NULL if the subsequent UPDATE failed.  A plain INSERT here would hit
        # the unique slug constraint and return no data.
        existing_ws = (
            db.table("workspaces")
            .select("id")
            .eq("slug", workspace_slug)
            .maybe_single()
            .execute()
        )
        if existing_ws and existing_ws.data:
            workspace_id = existing_ws.data["id"]
            logger.info(
                "ensure_user_workspace | workspace found by slug | user_id=%s",
                user.id,
            )
        else:
            workspace_insert = (
                db.table("workspaces")
                .insert(
                    {
                        "name": "Personal Workspace",
                        "slug": workspace_slug,
                        "owner_id": user.id,
                    }
                )
                .execute()
            )
            if not workspace_insert.data:
                logger.error(
                    "ensure_user_workspace | workspace insert returned no data | user_id=%s",
                    user.id,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "code": "USER_SETUP_FAILED",
                        "message": "Account setup could not be completed. Please try again.",
                    },
                )
            workspace_id = workspace_insert.data[0]["id"]
            logger.info(
                "ensure_user_workspace | workspace created | user_id=%s",
                user.id,
            )

        profile_update = (
            db.table("profiles")
            .update({"workspace_id": workspace_id})
            .eq("id", user.id)
            .execute()
        )
        if not profile_update.data:
            logger.error(
                "ensure_user_workspace | profile workspace link returned no data | user_id=%s",
                user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "USER_SETUP_FAILED",
                    "message": "Account setup could not be completed. Please try again.",
                },
            )
        profile = profile_update.data[0]

    # ── Workspace membership ──────────────────────────────────────────────────
    member_result = (
        db.table("workspace_members")
        .select("id")
        .eq("workspace_id", workspace_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    member_exists = bool(member_result and member_result.data)
    logger.info(
        "ensure_user_workspace | workspace_members_exists=%s | user_id=%s",
        member_exists,
        user.id,
    )

    if not member_exists:
        db.table("workspace_members").insert(
            {
                "workspace_id": workspace_id,
                "user_id": user.id,
                "role": "owner",
            }
        ).execute()

        # Re-select to verify the row was actually persisted.
        verify_member = (
            db.table("workspace_members")
            .select("id")
            .eq("workspace_id", workspace_id)
            .eq("user_id", user.id)
            .maybe_single()
            .execute()
        )
        member_exists = bool(verify_member and verify_member.data)
        logger.info(
            "ensure_user_workspace | workspace_members created | verified=%s | user_id=%s",
            member_exists,
            user.id,
        )
        if not member_exists:
            logger.error(
                "ensure_user_workspace | workspace_members could not be persisted | user_id=%s",
                user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "USER_SETUP_FAILED",
                    "message": "Account setup could not be completed. Please try again.",
                },
            )

    return {
        "user_id": user.id,
        "workspace_id": workspace_id,
        "profile": profile,
    }


def require_owned_record(table: str, record_id: str, user: CurrentUser) -> dict:
    db = get_db()
    record = (
        db.table(table)
        .select("*")
        .eq("id", record_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
        .data
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
