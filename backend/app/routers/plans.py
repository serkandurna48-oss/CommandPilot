import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user, require_owned_record
from app.models.plan import PlanGenerateRequest, PlanResponse
from app.services.ai_service import AIGenerationError, generate_daily_plan
from app.services.checkin_service import get_active_rules_for_user
from app.services.plan_service import (
    get_latest_plan_for_user,
    get_plans_for_user,
    save_plan,
)
from app.services.review_service import get_recent_review_for_user

logger = logging.getLogger(__name__)

router = APIRouter()

# User-facing messages for each AI error code
_AI_ERROR_MESSAGES: dict[str, str] = {
    "OPENAI_AUTH_FAILED": "Plan generation is unavailable: API key issue.",
    "OPENAI_RATE_LIMITED": "Plan generation is temporarily unavailable due to high demand. Please try again in a moment.",
    "OPENAI_QUOTA_EXCEEDED": "Plan generation is unavailable: API quota exceeded.",
    "AI_JSON_INVALID": "Plan generation failed: unexpected AI response format. Please try again.",
    "AI_SCHEMA_INVALID": "Plan generation failed: AI response had an unexpected structure. Please try again.",
    "UNKNOWN_AI_ERROR": "Plan generation failed. Please try again.",
}


@router.post("/generate", response_model=PlanResponse)
async def generate_plan(
    req: PlanGenerateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    # ── Step 0: Workspace integrity guard (fresh-user path) ─────────────────
    # user.workspace_id is resolved once at request start by get_current_user().
    # For a brand-new user whose profile was just created, it may be None even
    # after bootstrap if the DB write hasn't been reflected yet, or if bootstrap
    # was never called.  Re-run ensure_user_workspace to recover and use the
    # returned workspace_id for save_plan.
    effective_workspace_id = user.workspace_id
    if not effective_workspace_id:
        logger.info(
            "Fresh-user path: workspace_id absent on CurrentUser — running ensure_user_workspace | user_id=%s",
            user.id,
        )
        try:
            setup = ensure_user_workspace(user)
            effective_workspace_id = setup.get("workspace_id")
            logger.info(
                "Fresh-user setup complete | workspace_id_present=%s",
                bool(effective_workspace_id),
            )
        except HTTPException:
            raise  # Already a structured error from ensure_user_workspace
        except Exception as exc:
            logger.error(
                "ensure_user_workspace failed unexpectedly | %s: %s",
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

    # ── Step 1: Verify checkin ownership ────────────────────────────────────
    logger.info("Plan generation requested | checkin_id=%s", req.checkin_id)
    checkin = require_owned_record("daily_checkins", req.checkin_id, user)
    logger.info("Checkin verified | checkin_date=%s", checkin.get("checkin_date"))

    # ── Step 2: Load user rules ──────────────────────────────────────────────
    rules = get_active_rules_for_user(user.id)
    logger.info("Rules loaded | count=%d", len(rules) if rules else 0)

    # ── Step 3: Fetch recent review (non-fatal) ──────────────────────────────
    recent_review = None
    try:
        checkin_date = (
            date.fromisoformat(checkin["checkin_date"])
            if checkin.get("checkin_date")
            else date.today()
        )
        recent_review = get_recent_review_for_user(user.id, checkin_date)
        logger.info("Review lookup complete | found=%s", recent_review is not None)
    except Exception as exc:
        logger.warning(
            "Review fetch failed | %s: %s — continuing without review context",
            type(exc).__name__,
            str(exc)[:100],
        )

    # ── Step 4: Generate plan via AI ─────────────────────────────────────────
    logger.info("Calling AI service | language=%s", req.language)
    try:
        plan, raw_json, review_context_used = await generate_daily_plan(
            checkin, rules, req.language, recent_review
        )
    except AIGenerationError as exc:
        logger.error("AI generation failed | code=%s | %s", exc.code, str(exc))
        raise HTTPException(
            status_code=502,
            detail={
                "code": exc.code,
                "message": _AI_ERROR_MESSAGES.get(exc.code, "Plan generation failed. Please try again."),
            },
        )
    except Exception as exc:
        logger.error(
            "Unexpected error during plan generation | %s: %s",
            type(exc).__name__,
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "UNKNOWN_AI_ERROR",
                "message": "Plan generation failed. Please try again.",
            },
        )

    # ── Step 5: Save plan ────────────────────────────────────────────────────
    logger.info("Saving plan | review_context_used=%s", review_context_used)
    try:
        result = save_plan(
            user_id=user.id,
            checkin_id=req.checkin_id,
            plan=plan,
            raw_ai_response=raw_json,
            plan_date=checkin.get("checkin_date"),
            workspace_id=effective_workspace_id,
            review_context_used=review_context_used,
        )
        logger.info("Plan saved successfully")
        return result
    except Exception as exc:
        logger.error("Plan save failed | %s: %s", type(exc).__name__, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PLAN_SAVE_FAILED",
                "message": "Plan was generated but could not be saved. Please try again.",
            },
        )


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
