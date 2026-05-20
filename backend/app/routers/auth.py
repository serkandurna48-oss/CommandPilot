import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, ensure_user_workspace, get_current_user

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
