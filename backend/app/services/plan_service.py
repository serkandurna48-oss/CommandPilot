import json
from datetime import date
from app.db.client import get_db
from app.models.plan import DailyPlanAI
from app.core.config import settings


def save_plan(
    user_id: str,
    checkin_id: str,
    plan: DailyPlanAI,
    raw_ai_response: str,
    plan_date: date | None = None,
    workspace_id: str | None = None,
    review_context_used: bool = False,
) -> dict:
    db = get_db()

    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "checkin_id": checkin_id,
        "plan_date": str(plan_date or date.today()),
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

    result = db.table("daily_plans").insert(payload).execute()
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
    return result.data


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
