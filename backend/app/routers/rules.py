from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db.client import get_db
from app.models.rules import RuleCreate, RuleResponse, RuleUpdate

router = APIRouter()


@router.post("", response_model=RuleResponse)
def create_rule(
    data: RuleCreate,
    user: CurrentUser = Depends(get_current_user),
):
    db = get_db()
    payload = {
        "user_id": user.id,
        "workspace_id": user.workspace_id,
        "title": data.title,
        "rule_text": data.rule_text,
        "category": data.category,
        "life_area_id": data.life_area_id,
        "is_active": data.is_active,
        "priority": data.priority,
    }
    try:
        result = db.table("user_rules").insert(payload).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {e}")

    if not result.data:
        raise HTTPException(status_code=500, detail="Rule insert returned no data")
    return result.data[0]


@router.get("/me", response_model=list[RuleResponse])
def fetch_my_rules(user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    result = (
        db.table("user_rules")
        .select("*")
        .eq("user_id", user.id)
        .order("priority", desc=True)
        .execute()
    )
    return result.data


@router.patch("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: str,
    data: RuleUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    db = get_db()
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = (
            db.table("user_rules")
            .update(updates)
            .eq("id", rule_id)
            .eq("user_id", user.id)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {e}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result.data[0]


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    db = get_db()
    try:
        result = (
            db.table("user_rules")
            .delete()
            .eq("id", rule_id)
            .eq("user_id", user.id)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {e}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True, "id": rule_id}
