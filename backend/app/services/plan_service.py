import json
import logging
from datetime import date, datetime
from postgrest.exceptions import APIError
from app.db.client import get_db
from app.models.plan import DailyPlanAI
from app.core.config import settings
from app.services import vault_service

logger = logging.getLogger(__name__)

_UNIQUE_CONSTRAINT = "daily_plans_user_id_plan_date_key"


class PlanAlreadyExistsError(Exception):
    def __init__(self, plan_id: str):
        self.plan_id = plan_id
        super().__init__(f"Plan already exists for this date: {plan_id}")


class PlanSaveError(Exception):
    """Raised when the INSERT hits a constraint violation but re-read finds nothing recoverable."""
    pass


def normalize_plan_date(value) -> str:
    """Return a YYYY-MM-DD string. Validates strictly — no today-fallback.
    datetime is handled before date because datetime is a subclass of date.
    """
    if value is None:
        raise ValueError("plan_date is required")
    if isinstance(value, datetime):         # must precede date check
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return date.fromisoformat(value).isoformat()  # raises ValueError on bad input
    raise TypeError(f"Unsupported plan_date type: {type(value).__name__}")


def build_vault_query(checkin: dict) -> str:
    """
    Build the second-brain retrieval query from a checkin: raw morning input
    plus the titles of important tasks. Empty checkin fields → empty query
    (get_vault_context_for_checkin still returns base context in that case).
    """
    parts: list[str] = []
    raw_input = (checkin.get("raw_input") or "").strip()
    if raw_input:
        parts.append(raw_input)
    tasks = checkin.get("important_tasks") or []
    if isinstance(tasks, list) and tasks:
        parts.append(" ".join(str(t) for t in tasks))
    return " ".join(parts)


def get_vault_context_for_checkin(
    checkin: dict, user_id: str | None = None
) -> tuple[str, list[dict], list[dict]]:
    """
    Retrieve second-brain context relevant to a checkin, for injection into
    the daily-plan prompt. Returns (block, hit_sources, base_sources) — see
    vault_service.get_context_for_query for what the split means; the daily
    plan only uses block today, the source lists exist for logging/parity
    with the chat path. Never raises — vault_service guarantees an empty
    result on a missing/unreadable vault. user_id is passed straight through
    to vault_service's ownership gate (JARVIS-A1, Aufgabe 2) — the caller
    must supply the requesting CurrentUser.id, never assume the vault
    belongs to whoever is asking.
    """
    query = build_vault_query(checkin)
    return vault_service.get_context_for_query(query, user_id)


def get_plan_for_date(user_id: str, plan_date: str) -> dict | None:
    """Return the existing plan row (id only) for a user/date, or None."""
    db = get_db()
    result = (
        db.table("daily_plans")
        .select("id")
        .eq("user_id", user_id)
        .eq("plan_date", plan_date)
        .limit(1)
        .maybe_single()
        .execute()
    )
    return result.data if result else None  # maybe_single returns None (not .data=None) on 0 rows


def save_plan(
    user_id: str,
    checkin_id: str,
    plan: DailyPlanAI,
    raw_ai_response: str,
    plan_date: str,
    workspace_id: str | None = None,
    review_context_used: bool = False,
) -> dict:
    db = get_db()

    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "checkin_id": checkin_id,
        "plan_date": plan_date,
        "status_summary": plan.status_summary,
        "day_mode": plan.day_mode,
        "main_win": plan.main_win,
        "top_priorities": [p.model_dump() for p in plan.top_priorities],
        "time_blocks": [b.model_dump() for b in plan.time_blocks],
        "energy_strategy": plan.energy_strategy,
        "not_today_list": plan.not_today_list,
        "evening_review_questions": plan.evening_review_questions,
        "motivational_closing": plan.motivational_closing,
        "raw_ai_response": json.loads(raw_ai_response),
        "model_used": settings.OPENAI_MODEL,
        "review_context_used": review_context_used,
    }

    try:
        result = db.table("daily_plans").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505" and _UNIQUE_CONSTRAINT in (exc.message or ""):
            existing = get_plan_for_date(user_id, plan_date)
            if existing:
                raise PlanAlreadyExistsError(plan_id=existing["id"]) from exc
            # 23505 fired but re-read found nothing — degenerate state, don't guess
            logger.error(
                "23505 constraint violation but re-read returned no row "
                "| user_id=%s | plan_date=%s | orig_error=%s",
                user_id, plan_date, str(exc)[:300],
                exc_info=True,
            )
            raise PlanSaveError(
                "Plan could not be saved: unique constraint violation with no recoverable state"
            ) from exc
        raise
    if not result.data:
        raise RuntimeError("Plan insert returned no data")
    return result.data[0]


def get_plan(plan_id: str) -> dict | None:
    db = get_db()
    result = (
        db.table("daily_plans")
        .select("*")
        .eq("id", plan_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


def get_plans_for_user(user_id: str, limit: int = 30) -> list[dict]:
    db = get_db()
    result = (
        db.table("daily_plans")
        .select("*")
        .eq("user_id", user_id)
        .order("plan_date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def get_latest_plan_for_user(user_id: str) -> dict | None:
    db = get_db()
    result = (
        db.table("daily_plans")
        .select("*")
        .eq("user_id", user_id)
        .order("plan_date", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
