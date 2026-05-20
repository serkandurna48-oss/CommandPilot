from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user, require_owned_record
from app.db.client import get_db
from app.models.review import ReviewCreate, ReviewResponse

router = APIRouter()


@router.post("", response_model=ReviewResponse)
def post_review(
    data: ReviewCreate,
    user: CurrentUser = Depends(get_current_user),
):
    db = get_db()
    review_date = str(data.review_date or date.today())

    if data.plan_id:
        require_owned_record("daily_plans", data.plan_id, user)

    payload = {
        "user_id": user.id,
        "workspace_id": user.workspace_id,
        "plan_id": data.plan_id,
        "review_date": review_date,
        "completed_items": data.completed_items,
        "missed_items": data.missed_items,
        "energy_end": data.energy_end,
        "biggest_win": data.biggest_win,
        "lessons": data.lessons,
        "carry_over_to_tomorrow": data.carry_over_to_tomorrow,
        "raw_reflection": data.raw_reflection,
        "overall_day_rating": data.overall_day_rating,
    }

    try:
        result = (
            db.table("evening_reviews")
            .upsert(payload, on_conflict="user_id,review_date")
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save review: {e}")

    if not result.data:
        raise HTTPException(status_code=500, detail="Review upsert returned no data")
    return result.data[0]


@router.get("/me", response_model=list[ReviewResponse])
def fetch_my_reviews(
    limit: int = 30,
    user: CurrentUser = Depends(get_current_user),
):
    db = get_db()
    result = (
        db.table("evening_reviews")
        .select("*")
        .eq("user_id", user.id)
        .order("review_date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@router.get("/{review_id}", response_model=ReviewResponse)
def fetch_review(
    review_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    return require_owned_record("evening_reviews", review_id, user)
