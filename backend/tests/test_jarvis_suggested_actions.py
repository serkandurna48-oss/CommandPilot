"""
Tests for JarvisChatAI's server-side guard on suggested_actions (J1, 01.10.2026).

A suggested action without acceptance_criteria can never become a work order
(WorkOrderCreate mandates >=1 — see app/models/work_order.py and the confirm
path in app/services/suggested_action_service.py). JarvisChatAI therefore drops
such proposals before they ever reach the UI, so a card the user clicks can
always be confirmed. This is belt-and-suspenders beside the prompt rule and the
JSON schema's minItems:1 on acceptance_criteria (app/prompts/jarvis_chat.py).

Run:
    python -m pytest backend/tests/test_jarvis_suggested_actions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.models.jarvis import JarvisChatAI  # noqa: E402


def _action(title: str, criteria: list[str]) -> dict:
    return {
        "title": title,
        "description": f"Do {title}",
        "team_type": "development",
        "target_repo_name": "commandpilot",
        "risk": "low",
        "requires_approval": True,
        "acceptance_criteria": criteria,
        "sources": [],
    }


def test_suggestion_with_criteria_is_kept():
    ai = JarvisChatAI(
        reply="ok",
        suggested_actions=[_action("A", ["Die README erwähnt X"])],
    )
    assert len(ai.suggested_actions) == 1
    assert ai.suggested_actions[0].title == "A"


def test_suggestion_without_criteria_is_dropped():
    ai = JarvisChatAI(
        reply="ok",
        suggested_actions=[_action("A", [])],
    )
    assert ai.suggested_actions == []


def test_only_suggestions_without_criteria_are_dropped():
    # Mixed batch: the one with criteria survives, the empty one is dropped.
    ai = JarvisChatAI(
        reply="ok",
        suggested_actions=[
            _action("WithCriteria", ["Es gibt einen Test, der Y abdeckt"]),
            _action("NoCriteria", []),
        ],
    )
    titles = [a.title for a in ai.suggested_actions]
    assert titles == ["WithCriteria"]


def test_drop_runs_before_cap_at_two():
    # Three proposals, two valid + one empty: the empty one is dropped first,
    # leaving exactly two valid ones (so the <=2 cap is not what trimmed it).
    ai = JarvisChatAI(
        reply="ok",
        suggested_actions=[
            _action("One", ["c1"]),
            _action("Empty", []),
            _action("Two", ["c2"]),
        ],
    )
    titles = [a.title for a in ai.suggested_actions]
    assert titles == ["One", "Two"]
