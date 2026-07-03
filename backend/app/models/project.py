from typing import Literal, Optional
from pydantic import BaseModel, Field

ProjectStatusLiteral = Literal["active", "waiting", "paused", "backlog", "done", "archived"]
ProjectPriorityLiteral = Literal["high", "medium", "low"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: ProjectStatusLiteral = "active"
    priority: ProjectPriorityLiteral = "medium"
    next_action: Optional[str] = Field(None, max_length=500)
    risk: Optional[str] = Field(None, max_length=300)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[ProjectStatusLiteral] = None
    priority: Optional[ProjectPriorityLiteral] = None
    next_action: Optional[str] = Field(None, max_length=500)
    risk: Optional[str] = Field(None, max_length=300)


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    status: str
    priority: str
    next_action: Optional[str] = None
    risk: Optional[str] = None
    created_at: str
    updated_at: str
