from datetime import date
from app.db.client import get_db
from app.models.checkin import CheckinCreate


def create_checkin(data: CheckinCreate, user_id: str, workspace_id: str | None = None) -> dict:
    db = get_db()
    checkin_date = str(data.checkin_date or date.today())

    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "checkin_date": checkin_date,
        "wake_time": data.wake_time,
        "sleep_quality": data.sleep_quality,
        "energy_level": data.energy_level,
        "body_status": data.body_status,
        "mood": data.mood,
        "fixed_events": [e.model_dump() for e in data.fixed_events],
        "important_tasks": data.important_tasks,
        "raw_input": data.raw_input,
        "available_hours": data.available_hours,
        "day_constraints": data.day_constraints,
    }

    result = (
        db.table("daily_checkins")
        .upsert(payload, on_conflict="user_id,checkin_date")
        .execute()
    )
    if not result.data:
        raise RuntimeError("Check-in upsert returned no data")
    return result.data[0]


def get_checkin(checkin_id: str) -> dict | None:
    db = get_db()
    result = (
        db.table("daily_checkins")
        .select("*")
        .eq("id", checkin_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


def get_checkins_for_user(user_id: str, limit: int = 30) -> list[dict]:
    db = get_db()
    result = (
        db.table("daily_checkins")
        .select("*")
        .eq("user_id", user_id)
        .order("checkin_date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def get_active_rules_for_user(user_id: str) -> list[dict]:
    db = get_db()
    result = (
        db.table("user_rules")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("priority", desc=True)
        .execute()
    )
    return result.data
