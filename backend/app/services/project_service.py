from datetime import datetime, timezone

from app.db.client import get_db

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _sort_projects(rows: list[dict]) -> list[dict]:
    rows.sort(
        key=lambda p: (
            _PRIORITY_ORDER.get(p.get("priority", "medium"), 1),
            (p.get("name") or "").lower(),
        )
    )
    return rows


def get_projects_for_user(user_id: str) -> list[dict]:
    db = get_db()
    result = (
        db.table("projects")
        .select("*")
        .eq("user_id", user_id)
        .neq("status", "archived")
        .execute()
    )
    return _sort_projects(result.data or [])


def get_active_projects_for_morning(user_id: str) -> list[dict]:
    """Returns up to 5 projects for morning plan context: 3 active + 2 waiting, sorted high→low priority."""
    db = get_db()
    result = (
        db.table("projects")
        .select("id, name, status, priority, next_action, risk")
        .eq("user_id", user_id)
        .in_("status", ["active", "waiting"])
        .execute()
    )
    rows = result.data or []
    active = _sort_projects([r for r in rows if r.get("status") == "active"])[:3]
    waiting = _sort_projects([r for r in rows if r.get("status") == "waiting"])[:2]
    return active + waiting


def create_project(user_id: str, workspace_id: str | None, data) -> dict:
    db = get_db()
    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "name": data.name,
        "description": data.description,
        "status": data.status,
        "priority": data.priority,
        "next_action": data.next_action,
        "risk": data.risk,
    }
    result = db.table("projects").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Project insert returned no data")
    return result.data[0]


def update_project(project_id: str, user_id: str, updates: dict) -> dict | None:
    db = get_db()
    updates = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}
    result = (
        db.table("projects")
        .update(updates)
        .eq("id", project_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None
