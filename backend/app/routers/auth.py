from fastapi import APIRouter, Depends

from app.auth import CurrentUser, ensure_user_workspace, get_current_user

router = APIRouter()


@router.post("/bootstrap", response_model=dict)
def bootstrap_user(user: CurrentUser = Depends(get_current_user)):
    return ensure_user_workspace(user)
