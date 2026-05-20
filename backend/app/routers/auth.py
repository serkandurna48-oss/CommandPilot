import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import CurrentUser, ensure_user_workspace, get_current_user
from app.db.client import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/bootstrap", response_model=dict)
def bootstrap_user(user: CurrentUser = Depends(get_current_user)):
    try:
        return ensure_user_workspace(user)
    except HTTPException:
        raise  # Already structured — pass through as-is
    except Exception as exc:
        logger.error(
            "bootstrap unexpected failure | %s: %s",
            type(exc).__name__,
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "USER_SETUP_FAILED",
                "message": "Account setup could not be completed. Please try again.",
            },
        )


class ProfileUpdate(BaseModel):
    language: str


@router.patch("/profile", response_model=dict)
def update_profile(
    data: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Update mutable profile fields. Currently only language is supported."""
    if data.language not in ("en", "de"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_LANGUAGE",
                "message": "Language must be 'en' or 'de'.",
            },
        )

    db = get_db()
    result = (
        db.table("profiles")
        .update({"language": data.language})
        .eq("id", user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "PROFILE_UPDATE_FAILED",
                "message": "Failed to update profile.",
            },
        )

    logger.info(
        "profile language updated | user_id=%s | language=%s",
        user.id,
        data.language,
    )
    return {"language": data.language}
