import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user, require_owned_record
from app.models.plan import PlanGenerateRequest, PlanResponse
from app.services.ai_service import generate_daily_plan
from app.services.checkin_service import get_active_rules_for_user
from app.services.plan_service import (
    get_latest_plan_for_user,
    get_plans_for_user,
    save_plan,
)
from app.services.review_service import get_recent_review_for_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=PlanResponse)
async def generate_plan(
    req: PlanGenerateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    checkin = require_owned_record("daily_checkins", req.checkin_id, user)
    rules = get_active_rules_for_user(user.id)

    # Fetch recent review for context.
    # Any failure here is non-fatal — plan generation continues with review=None.
    recent_review = None
    try:
        checkin_date = (
            date.fromisoformat(checkin["checkin_date"])
            if checkin.get("checkin_date")
            else date.today()
        )
        recent_review = get_recent_review_for_user(user.id, checkin_date)
    except Exception:
        logger.warning("Review fetch failed for user %s — continuing without review context", user.id)

    try:
        plan, raw_json, review_context_used = await generate_daily_plan(
            checkin, rules, req.language, recent_review
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {e}")

    try:
        return save_plan(
            user_id=user.id,
            checkin_id=req.checkin_id,
            plan=plan,
            raw_ai_response=raw_json,
            plan_date=checkin.get("checkin_date"),
            workspace_id=user.workspace_id,
            review_context_used=review_context_used,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save plan: {e}")


@router.get("/me/latest", response_model=PlanResponse)
def fetch_latest_plan(user: CurrentUser = Depends(get_current_user)):
    plan = get_latest_plan_for_user(user.id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plans found")
    return plan


@router.get("/me", response_model=list[PlanResponse])
def fetch_my_plans(
    limit: int = 30,
    user: CurrentUser = Depends(get_current_user),
):
    return get_plans_for_user(user.id, limit)


@router.get("/{plan_id}", response_model=PlanResponse)
def fetch_plan(
    plan_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    return require_owned_record("daily_plans", plan_id, user)
