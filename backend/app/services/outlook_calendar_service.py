"""
CommandPilot — Outlook Calendar Context (via Composio)

One of two calendar sources (see google_calendar_service.py for the other) —
both are merged by their callers (routers/jarvis.py, routers/plans.py), never
imported by each other. Same window and contract as google_calendar_service:
yesterday through the day after tomorrow, formatted as a "### Quelle: ..."
block matching vault_service's shape.

Requires COMPOSIO_API_KEY and COMPOSIO_USER_ID — the same Composio user_id
google_calendar_service and notion_tasks_service use (single-tenant, mirrors
vault_service's VAULT_OWNER_USER_ID). Either unset -> empty string, no
network call. No connected Outlook account for that user_id, or any other
Composio API failure, is caught and logged the same way — a missing/broken
Outlook connection must degrade Jarvis to "no Outlook calendar context",
never break the chat reply. If only one of Google/Outlook is actually
connected, the other simply contributes nothing — this module does not know
or care which.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.services.composio_client import get_client

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_TOOL_SLUG = "OUTLOOK_GET_CALENDAR_VIEW"
_WINDOW_PAST = timedelta(days=1)
_WINDOW_FUTURE = timedelta(days=2)


def _format_event(event: dict) -> str | None:
    start = (event or {}).get("start") or {}
    end = (event or {}).get("end") or {}
    start_str = start.get("dateTime")
    end_str = end.get("dateTime")
    subject = (event or {}).get("subject") or "(ohne Titel)"
    if not start_str:
        return None
    return f"- {start_str} bis {end_str or start_str}: {subject}"


def _extract_events(result: dict | None) -> list[dict]:
    data = (result or {}).get("data") or {}
    events = data.get("value") if isinstance(data, dict) else None
    if events is None:
        logger.warning(
            "outlook_calendar_service: unexpected Composio response shape, no 'value' list found | keys=%s",
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )
        return []
    return events


def _cap_lines_to_budget(lines: list[str], token_budget: int) -> list[str]:
    """Whole-line budget cap — see google_calendar_service._cap_lines_to_budget
    for why a truncated event line is worse than a dropped one."""
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
    Returns (block, sources): block is a formatted "### Quelle: Kalender –
    Outlook" block covering roughly yesterday through the day after
    tomorrow, capped to token_budget (chars // 4, same estimation
    vault_service uses) by dropping whole events, never truncating mid-line.
    sources is the same events as
    `[{"file": "Kalender – Outlook", "heading": <line>}, ...]` — the shape
    routers/jarvis.py turns into SourceRef for the UI's own "Kalender"
    disclosure (see CLAUDE.md § Jarvis), separate from vault hit_sources.
    ("", []) on missing config, no connected account, no events in the
    window, or any Composio error. Never raises.
    """
    if not settings.COMPOSIO_API_KEY or not settings.COMPOSIO_USER_ID:
        return "", []

    client = get_client()
    if client is None:
        return "", []

    now = datetime.now(timezone.utc)
    time_min = (now - _WINDOW_PAST).replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = (now + _WINDOW_FUTURE).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        result = client.tools.execute(
            _TOOL_SLUG,
            user_id=settings.COMPOSIO_USER_ID,
            arguments={
                "start_datetime": time_min.isoformat(),
                "end_datetime": time_max.isoformat(),
                "timezone": "Europe/Berlin",
            },
            # SDK requires an explicit toolkit version per call as of
            # composio==0.22.0 — "latest" + the skip flag is the documented
            # way to opt out of pinning one (see requirements.txt comment).
            version="latest",
            dangerously_skip_version_check=True,
        )
    except Exception as exc:
        logger.warning(
            "outlook_calendar_service: Composio call failed | %s: %s — continuing without calendar context",
            type(exc).__name__, str(exc)[:200],
        )
        return "", []

    events = _extract_events(result)
    lines = [line for line in (_format_event(e) for e in events) if line]
    if not lines:
        return "", []

    lines = _cap_lines_to_budget(lines, token_budget)
    if not lines:
        return "", []

    body = "\n".join(lines)
    block = f"### Quelle: Kalender – Outlook ({time_min.date()} – {time_max.date()})\n{body}"
    sources = [{"file": "Kalender – Outlook", "heading": line[2:]} for line in lines]  # strip "- " prefix
    return block, sources
