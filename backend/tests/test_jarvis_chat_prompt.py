"""
Tests for prompts/jarvis_chat.py (Jarvis v1, phase 4).

Pure prompt-string assertions — no OpenAI call. Per the "empty vault must not
hallucinate" requirement: we verify the built prompt/system-prompt instruct
the model to admit missing knowledge and never invent, and that an empty
vault context produces an explicit "context is empty" marker rather than a
silently missing section. Actual model behavior on an empty vault is a
manual check, not something a unit test can meaningfully assert.

Run:
    python -m pytest backend/tests/test_jarvis_chat_prompt.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts import jarvis_chat  # noqa: E402
from app.prompts.jarvis_chat import SYSTEM_PROMPT, build_chat_prompt, build_system_prompt  # noqa: E402


def test_system_prompt_instructs_no_hallucination():
    assert "Erfinde nichts" in SYSTEM_PROMPT
    assert "Deutsch" in SYSTEM_PROMPT


def test_build_system_prompt_defaults_to_german():
    assert build_system_prompt() == SYSTEM_PROMPT


def test_build_system_prompt_english_instructs_english_reply():
    prompt = build_system_prompt("en")
    assert "Antworte ausschließlich auf Englisch" in prompt
    assert "Antworte ausschließlich auf Deutsch." not in prompt
    # No-hallucination and no-sources-line rules must survive the language switch.
    assert "Erfinde nichts" in prompt
    assert "Quellen:" in prompt


def test_build_chat_prompt_english_language_instructs_english_reply():
    prompt = build_chat_prompt("What is my rehab status?", [], "", language="en")
    assert "Antworte auf Englisch" in prompt
    assert "Antworte auf Deutsch" not in prompt


def test_build_chat_prompt_defaults_to_german():
    prompt = build_chat_prompt("Wie ist mein Reha-Stand?", [], "")
    assert "Antworte auf Deutsch" in prompt


def test_system_prompt_forbids_inline_source_list():
    # JARVIS-A1, Aufgabe 5: the UI renders sources separately now — the model
    # must not also write a "Quellen:" line into the reply text itself.
    assert "KEINE" in SYSTEM_PROMPT or "keine" in SYSTEM_PROMPT
    assert "Quellen:" in SYSTEM_PROMPT  # named as the thing to avoid writing
    assert "Oberfläche zeigt die Quellen bereits separat" in SYSTEM_PROMPT


def test_trailing_instruction_does_not_ask_for_a_sources_line():
    prompt = build_chat_prompt("Was ist mein Reha-Stand?", [], "### Quelle: 40-Gesundheit.md\nRuhephase.")
    trailing = prompt.rsplit("AKTUELLE FRAGE:", 1)[1]
    assert "Nenne am Ende deiner Antwort die Quellen" not in trailing
    assert "keine eigene Quellenliste" in trailing


def test_empty_context_block_produces_explicit_empty_marker():
    prompt = build_chat_prompt("Woran sollte ich diese Woche arbeiten?", [], "")
    assert "leer" in prompt
    assert "nichts Passendes gefunden" in prompt or "nicht verfügbar" in prompt


def test_nonempty_context_block_is_included_verbatim():
    context = "### Quelle: Projekte/CommandPilot.md\nStatus: active, P3"
    prompt = build_chat_prompt("Was ist der Status von CommandPilot?", [], context)
    assert context in prompt
    assert "leer" not in prompt.split("SECOND-BRAIN-KONTEXT:")[1].split("\n\n")[0]


def test_date_line_advances_across_the_utc_midnight_boundary():
    # The one real risk in "just call datetime.now(timezone.utc)" is a caller
    # someday caching the date across a request boundary, or a future
    # timezone change reintroducing an off-by-one. Freeze time on both sides
    # of UTC midnight and assert the date line actually tracks it — this
    # would fail if HEUTIGES DATUM were ever computed once and reused.
    before_midnight = datetime(2026, 9, 23, 23, 59, 59, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 9, 24, 0, 0, 1, tzinfo=timezone.utc)

    class _FrozenDatetime(datetime):
        _now = before_midnight

        @classmethod
        def now(cls, tz=None):
            return cls._now

    with patch.object(jarvis_chat, "datetime", _FrozenDatetime):
        _FrozenDatetime._now = before_midnight
        prompt_before = build_chat_prompt("Was steht an?", [], "")
        _FrozenDatetime._now = after_midnight
        prompt_after = build_chat_prompt("Was steht an?", [], "")

    assert "HEUTIGES DATUM: 2026-09-23 (Mittwoch)" in prompt_before
    assert "HEUTIGES DATUM: 2026-09-24 (Donnerstag)" in prompt_after


def test_prompt_grounds_the_model_in_todays_date():
    # Found 23.09.2026 live in the browser: Jarvis said "heute" about a
    # calendar event that was actually the next day, because nothing in this
    # prompt ever told the model what "today" is (unlike daily_plan.py's
    # build_user_prompt(), which already includes checkin['checkin_date']).
    # Calendar/Notion context arrives as absolute ISO timestamps — without
    # this anchor the model cannot correctly reason about "heute"/"morgen".
    prompt = build_chat_prompt("Was steht heute an?", [], "")
    today = datetime.now(timezone.utc).date().isoformat()
    assert f"HEUTIGES DATUM: {today}" in prompt
    assert prompt.index("HEUTIGES DATUM") < prompt.index("SECOND-BRAIN-KONTEXT")


def test_history_is_rendered_in_order():
    history = [
        {"role": "user", "content": "Wer ist Volkan?"},
        {"role": "assistant", "content": "Volkan ist dein Trainingspartner."},
    ]
    prompt = build_chat_prompt("Und Enis?", history, "")
    user_idx = prompt.index("Nutzer: Wer ist Volkan?")
    assistant_idx = prompt.index("Jarvis: Volkan ist dein Trainingspartner.")
    question_idx = prompt.index("Und Enis?")
    assert user_idx < assistant_idx < question_idx
