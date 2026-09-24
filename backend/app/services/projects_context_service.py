"""
CommandPilot — Projects Context (CommandPilot's own database)

Surfaces the user's own CommandPilot Projects (status, next_action, risk —
the same fields frontend/components/dashboard/ProjectCards.tsx renders on
Home) as a context block in the same "### Quelle: ..." shape vault_service
produces. Same reasoning as work_orders_context_service.py: this reads
CommandPilot's own database directly, not an external system.

Without this, Jarvis had no direct view of live project status at all —
only whatever happened to be written in the Obsidian vault, a separate
system that isn't guaranteed to be kept in sync with the Projects UI
(CLAUDE.md: "CommandPilot liest das Vault, nie umgekehrt" — the vault is
a personal knowledge base, not a mirror of this table). A user editing a
project's next_action/risk in the app would otherwise see Jarvis answer
from stale vault text — exactly the kind of manual handoff this service
closes.

Missing user_id, no non-archived/done projects on file, or any DB error
-> ("", []). Never raises — same contract as every other context source.
"""
from __future__ import annotations

import logging

from app.services import project_service

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_MAX_PROJECTS = 15
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _format_project(project: dict) -> str:
    name = project.get("name") or "(ohne Namen)"
    status = project.get("status") or "unknown"
    next_action = project.get("next_action")
    risk = project.get("risk")
    parts = [f"- {name} — Status: {status}"]
    if next_action:
        parts.append(f"Nächste Aufgabe: {next_action}")
    if risk:
        parts.append(f"Blocker: {risk}")
    return " | ".join(parts)


def _cap_lines_to_budget(lines: list[str], token_budget: int) -> list[str]:
    """Whole-line budget cap — see google_calendar_service._cap_lines_to_budget
    for why a truncated project line is worse than a dropped one."""
    budget_chars = max(token_budget, 0) * _CHARS_PER_TOKEN
    capped: list[str] = []
    used = 0
    for line in lines:
        used += len(line) + 1  # +1 for the joining newline
        if used > budget_chars:
            break
        capped.append(line)
    return capped


def get_context(user_id: str, token_budget: int = 600) -> tuple[str, list[dict]]:
    """
    Returns (block, sources): the user's non-done/non-archived Projects
    (same scope as ProjectCards.tsx on Home — "active"/"waiting"/"paused"/
    "backlog"), sorted by priority high->low, capped to _MAX_PROJECTS
    entries and token_budget by dropping whole entries, never truncating
    mid-line. sources shaped
    `[{"file": "Projekte (CommandPilot)", "heading": <line>}, ...]` — same
    shape routers/jarvis.py turns into SourceRef for every other context
    source.
    ("", []) if the user has no such projects on file, user_id is missing,
    or any DB error occurs. Never raises.
    """
    if not user_id:
        return "", []

    try:
        projects = project_service.get_projects_for_user(user_id)
    except Exception as exc:
        logger.warning(
            "projects_context_service: DB call failed | %s: %s — continuing without project context",
            type(exc).__name__, str(exc)[:200],
        )
        return "", []

    live = [p for p in projects if p.get("status") not in ("done", "archived")]
    if not live:
        return "", []

    live.sort(key=lambda p: _PRIORITY_RANK.get(p.get("priority"), 1))
    lines = [_format_project(p) for p in live[:_MAX_PROJECTS]]
    lines = _cap_lines_to_budget(lines, token_budget)
    if not lines:
        return "", []

    body = "\n".join(lines)
    block = f"### Quelle: Projekte (CommandPilot)\n{body}"
    sources = [{"file": "Projekte (CommandPilot)", "heading": line[2:]} for line in lines]  # strip "- " prefix
    return block, sources
