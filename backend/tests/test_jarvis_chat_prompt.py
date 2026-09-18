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
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.jarvis_chat import SYSTEM_PROMPT, build_chat_prompt  # noqa: E402


def test_system_prompt_instructs_no_hallucination_and_source_citation():
    assert "Erfinde nichts" in SYSTEM_PROMPT
    assert "Quellen" in SYSTEM_PROMPT
    assert "Deutsch" in SYSTEM_PROMPT


def test_empty_context_block_produces_explicit_empty_marker():
    prompt = build_chat_prompt("Woran sollte ich diese Woche arbeiten?", [], "")
    assert "leer" in prompt
    assert "nichts Passendes gefunden" in prompt or "nicht verfügbar" in prompt


def test_nonempty_context_block_is_included_verbatim():
    context = "### Quelle: Projekte/CommandPilot.md\nStatus: active, P3"
    prompt = build_chat_prompt("Was ist der Status von CommandPilot?", [], context)
    assert context in prompt
    assert "leer" not in prompt.split("SECOND-BRAIN-KONTEXT:")[1].split("\n\n")[0]


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
