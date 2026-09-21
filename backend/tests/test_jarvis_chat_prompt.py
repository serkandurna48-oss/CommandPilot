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
