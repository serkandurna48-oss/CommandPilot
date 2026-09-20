import logging
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class SourceRef(BaseModel):
    source_file: str
    source_heading: str = ""


# Shaped to match app/models/work_order.py's WorkOrderCreate fields it seeds
# (title, team_type default, target_repo_name) plus the approval-relevant
# fields the Command Layer needs (risk, requires_approval) — see
# app/core/safety_rules.py for the real enforcement those hook into via
# app/services/suggested_action_service.py. A SuggestedAction is a proposal
# ONLY — it is never itself persisted; it becomes a real work order exactly
# when a human confirms it (see SuggestedActionDecisionRequest below). This
# structure is intentionally unchanged since it was first shaped in Phase 4
# (JARVIS-C1) — do not add fields here; idempotency/decision-tracking fields
# (request_id, decision) live on the wrapping request/response models
# instead, so a proposal itself never carries persistence concerns.
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
    # JARVIS-C1: populated with exactly two entries when the message
    # described a goal, empty for ordinary knowledge questions. Never
    # persisted by the chat endpoint itself — see JarvisChatAI below and
    # app/routers/jarvis.py's confirm/reject endpoints for where a proposal
    # actually becomes (or explicitly does not become) a work order.
    suggested_actions: list[SuggestedAction] = []


# Raw structured AI output for POST /api/jarvis/chat (JARVIS-C1, Phase 3) —
# reply + suggested_actions come back from one OpenAI call (structured
# outputs, same strict-schema pattern as app/prompts/daily_plan.py), not two
# separate calls or a fragile freetext extraction. See
# app/prompts/jarvis_chat.py's JSON_SCHEMA for the wire shape and
# app/services/ai_service.py's generate_chat_reply() for where this is
# parsed. Never returned directly to the frontend — JarvisChatResponse is.
class JarvisChatAI(BaseModel):
    reply: str
    suggested_actions: list[SuggestedAction] = []

    @model_validator(mode="after")
    def _enforce_two_or_none(self):
        # The system prompt instructs the model to return exactly two
        # suggestions or none — a lone stray suggestion breaks that
        # invariant (a UI showing "confirm this one goal-sized proposal,
        # alone" is not the reviewed pair the product calls for) and must
        # never reach the caller. Dropping to [] rather than raising: a
        # malformed suggestion set should degrade to "no proposals this
        # turn," not fail the whole chat reply.
        if len(self.suggested_actions) == 1:
            logger.warning(
                "Jarvis returned exactly one suggested_action — dropping to enforce the two-or-none invariant"
            )
            self.suggested_actions = []
        return self


# ─── Suggested Action confirm/reject (JARVIS-C1, Phase 5) ───────────────────────
class SuggestedActionDecisionRequest(BaseModel):
    # The full, unmodified proposal as shown in the UI — the backend never
    # trusts a client-supplied work_order_id/user_id, but it does need the
    # proposal's own content again here because suggested_actions are never
    # persisted at chat time (see JarvisChatResponse above), so there is
    # nothing server-side to look this proposal up by.
    action: SuggestedAction
    # Client-generated idempotency token, one per suggested-action card in
    # the UI, reused across retries of the *same* click — never a
    # server-assigned id. See supabase/migrations/013_suggested_action_decisions.sql
    # for how this actually prevents a double-click/retry from creating two
    # work orders for one proposal.
    request_id: str = Field(..., min_length=1, max_length=128)


class SuggestedActionDecisionResponse(BaseModel):
    decision: Literal["confirmed", "rejected"]
    work_order_id: Optional[str] = None
    # True when this call replayed an already-recorded decision for the same
    # request_id (idempotent retry) rather than performing a fresh write.
    already_decided: bool = False
