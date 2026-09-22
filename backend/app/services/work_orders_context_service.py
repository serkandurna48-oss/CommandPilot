"""
CommandPilot — Work Orders Context (CommandPilot's own database)

Surfaces the user's own CommandPilot Work Orders (Operator Control Plane —
see work_order_service.py) as a context block in the same "### Quelle: ..."
shape vault_service produces. This is the one Jarvis context source that
reads CommandPilot's own database directly rather than an external system —
Work Orders live only here, there is nothing external to ask. Without this,
Jarvis had no way to know about real work orders at all and would answer
"Work Order" questions from whatever happened to be worded similarly in the
vault/Notion tasks — wrong source, wrong answer.

Missing user_id, no work orders on file, or any DB error -> ("", []). Never
raises — same contract as the other context sources (google_calendar_service
etc.): a broken lookup degrades Jarvis to "no work order context", never
breaks the chat reply.
"""
from __future__ import annotations

import logging

from app.services import work_order_service

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_MAX_ORDERS = 10


def _format_order(order: dict) -> str:
    title = order.get("title") or "(ohne Titel)"
    status = order.get("status") or "unknown"
    repo = order.get("repo")
    repo_suffix = f" [{repo}]" if repo and repo != "commandpilot" else ""
    return f"- {title}{repo_suffix} — Status: {status}"


def _cap_lines_to_budget(lines: list[str], token_budget: int) -> list[str]:
    """Whole-line budget cap — see google_calendar_service._cap_lines_to_budget
    for why a truncated work order line is worse than a dropped one."""
    budget_chars = max(token_budget, 0) * _CHARS_PER_TOKEN
    capped: list[str] = []
    used = 0
    for line in lines:
        used += len(line) + 1  # +1 for the joining newline
        if used > budget_chars:
            break
        capped.append(line)
    return capped


def get_context(user_id: str, token_budget: int = 500) -> tuple[str, list[dict]]:
    """
    Returns (block, sources): the user's Work Orders, newest first
    (get_work_orders_for_user already orders by created_at desc), capped to
    _MAX_ORDERS entries and token_budget by dropping whole entries, never
    truncating mid-line. sources shaped
    `[{"file": "Work Orders (CommandPilot)", "heading": <line>}, ...]` — the
    shape routers/jarvis.py turns into SourceRef for the UI's own source
    disclosure, same as the other context sources.
    ("", []) if the user has no work orders on file, user_id is missing, or
    any DB error occurs. Never raises.
    """
    if not user_id:
        return "", []

    try:
        orders = work_order_service.get_work_orders_for_user(user_id)
    except Exception as exc:
        logger.warning(
            "work_orders_context_service: DB call failed | %s: %s — continuing without work order context",
            type(exc).__name__, str(exc)[:200],
        )
        return "", []

    if not orders:
        return "", []

    lines = [_format_order(o) for o in orders[:_MAX_ORDERS]]
    lines = _cap_lines_to_budget(lines, token_budget)
    if not lines:
        return "", []

    body = "\n".join(lines)
    block = f"### Quelle: Work Orders (CommandPilot)\n{body}"
    sources = [{"file": "Work Orders (CommandPilot)", "heading": line[2:]} for line in lines]  # strip "- " prefix
    return block, sources
