from datetime import date, timedelta
from app.db.client import get_db


def get_recent_review_for_user(user_id: str, reference_date: date) -> dict | None:
    """
    Return the most recent evening review for a user relative to reference_date.
    Prefers yesterday's review; falls back to any review in the last 3 days.
    Returns None if no review exists in that window.
    Ownership is enforced by filtering on user_id.
    """
    db = get_db()
    cutoff = reference_date - timedelta(days=3)

    result = (
        db.table("evening_reviews")
        .select("review_date,completed_items,missed_items,raw_reflection,biggest_win,lessons,carry_over_to_tomorrow,energy_end,overall_day_rating")
        .eq("user_id", user_id)
        .gte("review_date", str(cutoff))
        .lt("review_date", str(reference_date))  # exclude today's review
        .order("review_date", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
