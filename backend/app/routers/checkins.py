from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user, require_owned_record
from app.models.checkin import CheckinCreate, CheckinResponse
from app.services.checkin_service import create_checkin, get_checkins_for_user

router = APIRouter()


@router.post("", response_model=CheckinResponse)
def post_checkin(
    data: CheckinCreate,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return create_checkin(data, user.id, user.workspace_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save check-in: {e}")


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
