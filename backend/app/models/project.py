from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

ProjectStatusLiteral = Literal["active", "waiting", "paused", "backlog", "done", "archived"]
ProjectPriorityLiteral = Literal["high", "medium", "low"]


def _validate_website_url(value: Optional[str]) -> Optional[str]:
    # Light sanity check, not a full URL parser — this becomes a clickable
    # external link (ProductWebsites card grid), so catching an obviously
    # malformed value here beats surfacing a broken link in the UI later.
    if value is None or value == "":
        return None
    if not (value.startswith("http://") or value.startswith("https://")):
        raise ValueError("website_url must start with http:// or https://")
    return value


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: ProjectStatusLiteral = "active"
    priority: ProjectPriorityLiteral = "medium"
    next_action: Optional[str] = Field(None, max_length=500)
    risk: Optional[str] = Field(None, max_length=300)
    website_url: Optional[str] = Field(None, max_length=500)

    _validate_website_url = field_validator("website_url")(_validate_website_url)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[ProjectStatusLiteral] = None
    priority: Optional[ProjectPriorityLiteral] = None
    next_action: Optional[str] = Field(None, max_length=500)
    risk: Optional[str] = Field(None, max_length=300)
    website_url: Optional[str] = Field(None, max_length=500)

    _validate_website_url = field_validator("website_url")(_validate_website_url)


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    status: str
    priority: str
    next_action: Optional[str] = None
    risk: Optional[str] = None
    website_url: Optional[str] = None
    created_at: str
    updated_at: str
