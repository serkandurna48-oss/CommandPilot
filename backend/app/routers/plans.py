import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user, require_owned_record
from app.models.plan import PlanGenerateRequest, PlanResponse
from app.services.ai_service import AIGenerationError, generate_daily_plan
from app.services.checkin_service import get_active_rules_for_user
from app.services.plan_service import (
    PlanAlreadyExistsError,
    PlanSaveError,
    get_latest_plan_for_user,
    get_plan_for_date,
    get_plans_for_user,
    normalize_plan_date,
    save_plan,
)
from app.services.review_service import get_recent_review_for_user

logger = logging.getLogger(__name__)

router = APIRouter()

# User-facing messages for each AI error code
_AI_ERROR_MESSAGES: dict[str, str] = {
    "OPENAI_AUTH_FAILED": "Plan generation is unavailable: API key issue.",
    "OPENAI_CONNECTION_ERROR": "Plan generation failed: could not reach the AI service. Please try again in a moment.",
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
    # ── Step 0: Verify user workspace setup ─────────────────────────────────
    # Always call ensure_user_workspace — it guarantees profile, workspace, and
    # workspace_members exist and returns a verified workspace_id.
    # user.workspace_id (from CurrentUser) is resolved once at request start and
    # may be stale or None; we use the value returned here for save_plan instead.
    try:
        setup = ensure_user_workspace(user)
        effective_workspace_id = setup.get("workspace_id")
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

    # Language is always taken from the user's profile — the request body cannot
    # override it. profile.language is the single source of truth.
    _profile_lang = (setup.get("profile") or {}).get("language") or "en"
    effective_language = _profile_lang if _profile_lang in ("en", "de") else "en"
    logger.info("Effective language | language=%s | source=profile", effective_language)

    if not effective_workspace_id:
        logger.error(
            "workspace_id still None after ensure_user_workspace | user_id=%s",
            user.id,
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

    # ── Step 1.5: Resolve plan_date + pre-flight duplicate check ────────────
    _raw_date = checkin.get("checkin_date")
    if not _raw_date:
        logger.error("checkin has no checkin_date | checkin_id=%s", req.checkin_id)
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CHECKIN_MISSING_DATE",
                "message": "Check-in has no date — cannot generate a plan.",
            },
        )
    try:
        plan_date = normalize_plan_date(_raw_date)
    except (ValueError, TypeError) as exc:
        logger.error("checkin_date is invalid | checkin_id=%s | value=%r | %s", req.checkin_id, _raw_date, exc)
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CHECKIN_INVALID_DATE",
                "message": "Check-in has an invalid date — cannot generate a plan.",
            },
        )

    _existing = get_plan_for_date(user.id, plan_date)
    if _existing:
        logger.info(
            "Plan already exists — aborting before AI call | plan_id=%s | plan_date=%s",
            _existing["id"],
            plan_date,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PLAN_ALREADY_EXISTS",
                "plan_id": _existing["id"],
                "message": "A plan already exists for this date.",
            },
        )

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
    logger.info("Calling AI service | language=%s", effective_language)
    try:
        plan, raw_json, review_context_used = await generate_daily_plan(
            checkin, rules, effective_language, recent_review
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
            plan_date=plan_date,
            workspace_id=effective_workspace_id,
            review_context_used=review_context_used,
        )
        logger.info("Plan saved successfully")
        return result
    except PlanAlreadyExistsError as exc:
        # Race condition: two requests slipped past the pre-flight check simultaneously.
        logger.warning("Concurrent duplicate plan insert blocked by DB constraint | plan_id=%s", exc.plan_id)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PLAN_ALREADY_EXISTS",
                "plan_id": exc.plan_id,
                "message": "A plan already exists for this date.",
            },
        )
    except PlanSaveError as exc:
        # 23505 fired but re-read found nothing — degenerate state, already logged in service.
        logger.error("Plan save failed with unrecoverable constraint state | %s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PLAN_SAVE_FAILED",
                "message": "Plan was generated but could not be saved. Please try again.",
            },
        )
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
