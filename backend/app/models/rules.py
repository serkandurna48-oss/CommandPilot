from pydantic import BaseModel, Field
from typing import Optional


class RuleCreate(BaseModel):
    user_id: Optional[str] = None
    title: str
    rule_text: str
    category: Optional[str] = None      # e.g. "scheduling", "energy", "focus"
    life_area_id: Optional[str] = None
    is_active: bool = True
    priority: int = Field(default=5, ge=1, le=10)


class RuleUpdate(BaseModel):
    title: Optional[str] = None
    rule_text: Optional[str] = None
    category: Optional[str] = None
    life_area_id: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=10)


class RuleResponse(BaseModel):
    id: str
    user_id: str
    title: str
    rule_text: str
    category: Optional[str] = None
    life_area_id: Optional[str] = None
    is_active: bool
    priority: int
    created_at: str
    updated_at: str
