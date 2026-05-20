from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date


class TimeBlock(BaseModel):
    start_time: str
    end_time: str
    title: str
    description: str
    life_area: str
    block_type: str


class Priority(BaseModel):
    title: str
    description: str
    life_area: str
    why: str


class DailyPlanAI(BaseModel):
    """Structured output from the AI — matches the JSON schema in the prompt."""
    status_summary: str
    day_mode: str
    main_win: str
    top_priorities: List[Priority]
    time_blocks: List[TimeBlock]
    energy_strategy: str
    not_today_list: List[str]
    evening_review_questions: List[str]
    motivational_closing: str


class PlanGenerateRequest(BaseModel):
    checkin_id: str
    user_id: Optional[str] = None
    # language is intentionally omitted — the backend always uses profile.language.
    # Extra fields sent by old clients are silently ignored by Pydantic.


class PlanResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    user_id: str
    checkin_id: Optional[str] = None
    plan_date: str
    status_summary: Optional[str] = None
    day_mode: Optional[str] = None
    main_win: Optional[str] = None
    top_priorities: List[Priority] = []
    time_blocks: List[TimeBlock] = []
    energy_strategy: Optional[str] = None
    not_today_list: List[str] = []
    evening_review_questions: List[str] = []
    motivational_closing: Optional[str] = None
    model_used: Optional[str] = None
    generated_at: Optional[str] = None
    created_at: str
    review_context_used: bool = False
