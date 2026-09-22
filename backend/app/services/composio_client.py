"""
CommandPilot — Composio Client

Thin lazy singleton around the Composio SDK client, used by
google_calendar_service, outlook_calendar_service, and notion_tasks_service
to reach Google Calendar / Outlook / Notion server-side. Composio manages
OAuth for all three toolkits; this module only owns client construction — no
toolkit-specific logic (see those three modules for that).

Missing COMPOSIO_API_KEY -> get_client() returns None. Callers treat that
exactly like vault_service treats an unset VAULT_PATH: empty context, one
log line, never an exception.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from composio import Composio

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> Composio | None:
    if not settings.COMPOSIO_API_KEY:
        logger.info("composio_client: COMPOSIO_API_KEY not configured — external context disabled")
        return None
    return Composio(api_key=settings.COMPOSIO_API_KEY)
