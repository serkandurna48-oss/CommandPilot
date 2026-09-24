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
    # Live calendar events for the query window (yesterday through the day
    # after tomorrow), merged from google_calendar_service and
    # outlook_calendar_service — see CLAUDE.md § Jarvis, external context.
    # Empty when Composio isn't configured, no account of either kind is
    # connected, or no events matched. Kept separate from `sources` (vault
    # hits): different provenance, own "Kalender" disclosure in the UI.
    calendar_sources: list[SourceRef] = []
    # Live open tasks from the Notion "My Tasks" database, via
    # notion_tasks_service. Same empty-on-not-configured contract as
    # calendar_sources, own "Notion" disclosure in the UI.
    task_sources: list[SourceRef] = []
    # The user's real CommandPilot Work Orders (Operator Control Plane —
    # work_order_service.py), via work_orders_context_service. The one
    # context source that reads CommandPilot's own database, not an external
    # system — added 22.09.2026 after Jarvis answered a "go through my
    # newest work order" question from a similarly-worded Notion task
    # instead of an actual work order, because no work-order context existed
    # at all. Empty when the user has no work orders on file.
    work_order_sources: list[SourceRef] = []
    # The user's real CommandPilot Projects (status/next_action/risk — the
    # same fields ProjectCards.tsx renders on Home), via
    # projects_context_service. Added 24.09.2026 so "where do we stand"
    # answers ground in the live Projects table rather than whatever
    # happens to be written in the (separate, not-guaranteed-in-sync)
    # Obsidian vault. Empty when the user has no active/waiting/paused/
    # backlog projects on file.
    project_sources: list[SourceRef] = []
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
    def _cap_at_two(self):
        # The system prompt asks for one or two suggestions, never more.
        # Previously a lone suggestion was dropped to enforce a strict
        # "two or none" invariant — but GPT-4o repeatedly returned exactly
        # one on real messages, so that invariant just meant "the user
        # never sees a proposal" more often than not. A single reviewed
        # proposal is still a reviewed proposal; only cap on the >2 side,
        # which would exceed what the UI is built to show.
        if len(self.suggested_actions) > 2:
            logger.warning(
                "Jarvis returned %d suggested_actions — capping at 2", len(self.suggested_actions)
            )
            self.suggested_actions = self.suggested_actions[:2]
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


# ─── Suggested Action decision history ───────────────────────────────────────────
# Read-only view over suggested_action_decisions (013_suggested_action_decisions.sql)
# — every proposal a human has ever confirmed or rejected, confirmed ones
# linking to the real work order they became. Denormalized snapshot fields
# (title/risk/etc.) come straight from the row, not a live join against
# work_orders, so a decision's audit trail stands even if that work order is
# later edited — same rationale as the migration's own header comment.
class SuggestedActionDecisionListItem(BaseModel):
    id: str
    decision: Literal["confirmed", "rejected"]
    title: str
    team_type: Optional[str] = None
    target_repo_name: Optional[str] = None
    risk: Optional[Literal["low", "medium", "high"]] = None
    requires_approval: Optional[bool] = None
    sources: list[SourceRef] = []
    work_order_id: Optional[str] = None
    created_at: str


class SuggestedActionDecisionListResponse(BaseModel):
    decisions: list[SuggestedActionDecisionListItem] = []
