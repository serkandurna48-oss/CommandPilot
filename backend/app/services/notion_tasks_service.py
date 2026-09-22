"""
CommandPilot — Notion Tasks Context (via Composio)

Surfaces open tasks from the user's Notion "My Tasks" database as a context
block in the same "### Quelle: ..." shape vault_service produces (see
google_calendar_service.py — same contract, mirrored here).

Requires COMPOSIO_API_KEY, COMPOSIO_USER_ID, and NOTION_TASKS_DATABASE_ID.
Any missing -> empty string, no network call. Any Composio API failure is
caught and logged — a broken Notion connection degrades Jarvis to "no task
context", never breaks the chat reply.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.composio_client import get_client

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_TOOL_SLUG = "NOTION_QUERY_DATABASE"


def _extract_title(props: dict) -> str:
    for value in props.values():
        if isinstance(value, dict) and value.get("type") == "title":
            rich = value.get("title") or []
            return "".join(t.get("plain_text", "") for t in rich).strip()
    return ""


def _extract_status(props: dict) -> str:
    # Detect by property `type`, not a hardcoded English name ("Status")
    # — same rationale as _extract_title: a user's database may name (or
    # translate) this field however they like ("Status" happens to be
    # unchanged in German too, but that's coincidence, not something to
    # depend on). Only the Notion `status` property type is unambiguous;
    # a `select` field could be anything (priority, effort, ...), so it's
    # not used as a fallback guess.
    for value in props.values():
        if isinstance(value, dict) and value.get("type") == "status":
            status = value.get("status")
            if isinstance(status, dict):
                return status.get("name", "")
    return ""


def _extract_due(props: dict) -> str:
    # Detect by property `type` ("date"), not a hardcoded English name
    # ("Due") — a user's database may call this "Fällig", "Deadline", etc.
    for value in props.values():
        if isinstance(value, dict) and value.get("type") == "date":
            date = value.get("date")
            if isinstance(date, dict):
                return date.get("start", "")
    return ""


def _format_task(page: dict) -> str | None:
    props = (page or {}).get("properties") or {}
    title = _extract_title(props)
    if not title:
        return None
    status = _extract_status(props)
    due = _extract_due(props)
    suffix_parts = [p for p in (status, f"fällig: {due}" if due else "") if p]
    suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
    return f"- {title}{suffix}"


def _extract_pages(result: dict | None) -> list[dict]:
    data = (result or {}).get("data") or {}
    pages = data.get("results") if isinstance(data, dict) else None
    if pages is None:
        logger.warning(
            "notion_tasks_service: unexpected Composio response shape, no results list found | keys=%s",
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )
        return []
    return pages


def _cap_lines_to_budget(lines: list[str], token_budget: int) -> list[str]:
    """Whole-line budget cap — see google_calendar_service._cap_lines_to_budget for
    why a truncated task line is worse than a dropped one."""
    budget_chars = max(token_budget, 0) * _CHARS_PER_TOKEN
    capped: list[str] = []
    used = 0
    for line in lines:
        used += len(line) + 1  # +1 for the joining newline
        if used > budget_chars:
            break
        capped.append(line)
    return capped


def get_context(token_budget: int = 500) -> tuple[str, list[dict]]:
    """
    Returns (block, sources): block is a formatted "### Quelle: Notion —
    Offene Aufgaben" block, capped to token_budget (chars // 4, same
    estimation vault_service uses) by dropping whole tasks, never truncating
    mid-line. sources is the same tasks as
    `[{"file": "Notion — Offene Aufgaben", "heading": <line>}, ...]` — the
    shape routers/jarvis.py turns into SourceRef for the UI's own "Notion"
    disclosure (see CLAUDE.md § Jarvis), separate from vault hit_sources.
    ("", []) on missing config, no connected account, no rows returned, or
    any Composio error. Never raises.
    """
    if not settings.COMPOSIO_API_KEY or not settings.COMPOSIO_USER_ID or not settings.NOTION_TASKS_DATABASE_ID:
        return "", []

    client = get_client()
    if client is None:
        return "", []

    try:
        result = client.tools.execute(
            _TOOL_SLUG,
            user_id=settings.COMPOSIO_USER_ID,
            arguments={
                "database_id": settings.NOTION_TASKS_DATABASE_ID,
                "page_size": 50,
            },
            # SDK requires an explicit toolkit version per call as of
            # composio==0.22.0 — "latest" + the skip flag is the documented
            # way to opt out of pinning one (see requirements.txt comment).
            version="latest",
            dangerously_skip_version_check=True,
        )
    except Exception as exc:
        logger.warning(
            "notion_tasks_service: Composio call failed | %s: %s — continuing without task context",
            type(exc).__name__, str(exc)[:200],
        )
        return "", []

    pages = _extract_pages(result)
    lines = [line for line in (_format_task(p) for p in pages) if line]
    if not lines:
        return "", []

    lines = _cap_lines_to_budget(lines, token_budget)
    if not lines:
        return "", []

    body = "\n".join(lines)
    block = f"### Quelle: Notion — Offene Aufgaben\n{body}"
    sources = [{"file": "Notion — Offene Aufgaben", "heading": line[2:]} for line in lines]  # strip "- " prefix
    return block, sources
