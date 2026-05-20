import logging
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.client import get_db

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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    token = _get_bearer_token(credentials)
    db = get_db()

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
