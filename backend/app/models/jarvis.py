from typing import Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class SourceRef(BaseModel):
    source_file: str
    source_heading: str = ""


# Shaped to match app/models/work_order.py's WorkOrderCreate fields it will
# eventually seed (title, team_type default, target_repo_name) plus the
# approval-relevant fields a future command-layer will need (risk,
# requires_approval) — see app/core/safety_rules.py for the real enforcement
# those will hook into. v1 never populates this: suggested_actions is always
# []. The shape exists so the response contract is stable before the
# command layer (Produktrichtung Schritt 2) uses it.
class SuggestedAction(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    team_type: str = Field("development", min_length=1, max_length=100)
    target_repo_name: Optional[str] = Field(None, max_length=200)
    risk: Literal["low", "medium", "high"]
    requires_approval: bool
    sources: list[SourceRef] = []


class JarvisChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class JarvisChatResponse(BaseModel):
    reply: str
    # Only the vault sections that actually carried the answer (JARVIS-A1,
    # Aufgabe 5) — this is what a UI should show by default.
    sources: list[SourceRef] = []
    # The always-present map-of-the-vault entries (00-Index.md + one line per
    # entity note) that were sent to the model alongside `sources` but did
    # not themselves feed the answer. Not shown by default — present for
    # transparency/debugging and for a future "show more" affordance.
    base_sources: list[SourceRef] = []
    suggested_actions: list[SuggestedAction] = []
