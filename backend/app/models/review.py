from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class ReviewCreate(BaseModel):
    user_id: Optional[str] = None
    plan_id: Optional[str] = None
    review_date: Optional[date] = None
    completed_items: List[str] = []
    missed_items: List[str] = []
    energy_end: Optional[int] = Field(None, ge=1, le=10)
    biggest_win: Optional[str] = None
    lessons: Optional[str] = None
    carry_over_to_tomorrow: List[str] = []
    raw_reflection: Optional[str] = None
    overall_day_rating: Optional[int] = Field(None, ge=1, le=10)


class ReviewResponse(BaseModel):
    id: str
    user_id: str
    plan_id: Optional[str] = None
    review_date: str
    completed_items: List[str] = []
    missed_items: List[str] = []
    energy_end: Optional[int] = None
    biggest_win: Optional[str] = None
    lessons: Optional[str] = None
    carry_over_to_tomorrow: List[str] = []
    raw_reflection: Optional[str] = None
    overall_day_rating: Optional[int] = None
    created_at: str
