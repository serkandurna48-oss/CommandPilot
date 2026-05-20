from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class FixedEvent(BaseModel):
    title: str
    time: Optional[str] = None          # e.g. "18:00"
    duration_minutes: Optional[int] = None
    life_area: Optional[str] = None


class CheckinCreate(BaseModel):
    user_id: Optional[str] = None
    checkin_date: Optional[date] = None
    wake_time: Optional[str] = None     # e.g. "07:30"
    sleep_quality: Optional[int] = Field(None, ge=1, le=10)
    energy_level: Optional[int] = Field(None, ge=1, le=10)
    body_status: Optional[str] = None
    mood: Optional[str] = None
    fixed_events: List[FixedEvent] = []
    important_tasks: List[str] = []
    raw_input: Optional[str] = None
    available_hours: Optional[float] = None
    day_constraints: Optional[str] = None


class CheckinResponse(BaseModel):
    id: str
    user_id: str
    checkin_date: str
    wake_time: Optional[str] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    body_status: Optional[str] = None
    mood: Optional[str] = None
    fixed_events: List[dict] = []
    important_tasks: List[str] = []
    raw_input: Optional[str] = None
    available_hours: Optional[float] = None
    day_constraints: Optional[str] = None
    created_at: str
