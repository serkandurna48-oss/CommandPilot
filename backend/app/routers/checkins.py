import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user, require_owned_record
from app.models.checkin import CheckinCreate, CheckinResponse
from app.services.checkin_service import create_checkin, get_checkins_for_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=CheckinResponse)
def post_checkin(
    data: CheckinCreate,
    user: CurrentUser = Depends(get_current_user),
):
    # Guarantee profile + workspace + membership exist and obtain a verified workspace_id
    # before writing the check-in row.  Fresh users must not get workspace_id = NULL.
    try:
        setup = ensure_user_workspace(user)
        verified_workspace_id = setup.get("workspace_id")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "ensure_user_workspace failed in post_checkin | %s: %s",
            type(exc).__name__,
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "USER_SETUP_FAILED",
                "message": "Account setup is incomplete. Please refresh the page and try again.",
            },
        )

    try:
        return create_checkin(data, user.id, verified_workspace_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save check-in: {exc}")


@router.get("/me", response_model=list[CheckinResponse])
def fetch_my_checkins(
    limit: int = 30,
    user: CurrentUser = Depends(get_current_user),
):
    return get_checkins_for_user(user.id, limit)


@router.get("/{checkin_id}", response_model=CheckinResponse)
def fetch_checkin(
    checkin_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    return require_owned_record("daily_checkins", checkin_id, user)
