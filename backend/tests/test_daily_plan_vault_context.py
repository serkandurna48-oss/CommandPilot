"""
Tests for the vault-context block in prompts/daily_plan.py (Jarvis v1, phase 3).

Pure prompt-string assertions — no OpenAI call, no DB, no env vars needed.

Run:
    python -m pytest backend/tests/test_daily_plan_vault_context.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.daily_plan import build_user_prompt  # noqa: E402

_CHECKIN = {
    "checkin_date": "2026-09-18",
    "wake_time": "07:00",
    "sleep_quality": 7,
    "energy_level": 6,
    "body_status": "fine",
    "mood": "focused",
    "available_hours": 8,
    "day_constraints": "none",
}


def test_plan_generation_unchanged_without_vault_context():
    prompt_no_arg, used_no_arg = build_user_prompt(_CHECKIN, rules=[], language="en")
    prompt_empty, used_empty = build_user_prompt(_CHECKIN, rules=[], language="en", vault_context="")
    assert prompt_no_arg == prompt_empty
    assert used_no_arg == used_empty
    assert "SECOND-BRAIN CONTEXT" not in prompt_no_arg


def test_vault_context_appended_as_delimited_block():
    prompt, _ = build_user_prompt(
        _CHECKIN, rules=[], language="en",
        vault_context="### Quelle: Projekte/CommandPilot.md\nStatus: active, P3",
    )
    assert "SECOND-BRAIN CONTEXT" in prompt
    assert "do not invent" in prompt.lower()
    assert "Projekte/CommandPilot.md" in prompt
    assert "Status: active, P3" in prompt
