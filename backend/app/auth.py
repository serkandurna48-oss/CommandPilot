from dataclasses import dataclass
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.client import get_db

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

    profile_result = (
        db.table("profiles")
        .select("*")
        .eq("id", user.id)
        .maybe_single()
        .execute()
    )
    profile = profile_result.data if profile_result else None

    if not profile:
        insert_result = (
            db.table("profiles")
            .insert({"id": user.id, "display_name": user.email})
            .execute()
        )
        if not insert_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user profile",
            )
        profile = insert_result.data[0]

    workspace_id = profile.get("workspace_id")
    if not workspace_id:
        workspace_slug = f"personal-{user.id.replace('-', '')}"
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create workspace",
            )
        workspace_id = workspace_insert.data[0]["id"]

        profile_update = (
            db.table("profiles")
            .update({"workspace_id": workspace_id})
            .eq("id", user.id)
            .execute()
        )
        if not profile_update.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to link workspace to profile",
            )
        profile = profile_update.data[0]

    member_result = (
        db.table("workspace_members")
        .select("id")
        .eq("workspace_id", workspace_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if not member_result or not member_result.data:
        db.table("workspace_members").insert(
            {
                "workspace_id": workspace_id,
                "user_id": user.id,
                "role": "owner",
            }
        ).execute()

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
