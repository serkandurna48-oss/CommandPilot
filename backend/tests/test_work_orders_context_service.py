"""
Tests for work_orders_context_service.py (Jarvis context source, 22.09.2026).

Pytest-native (uses monkeypatch), mirrors the other context-source test
files' never-raises contract — but this one mocks work_order_service.get_work_orders_for_user
directly (CommandPilot's own DB call) rather than a Composio client, since
this is the one context source with no external API involved.

Run:
    python -m pytest backend/tests/test_work_orders_context_service.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.services import work_orders_context_service  # noqa: E402


def test_missing_user_id_returns_empty_without_calling_db(monkeypatch):
    monkeypatch.setattr(
        work_orders_context_service.work_order_service, "get_work_orders_for_user",
        MagicMock(side_effect=AssertionError("must not be called")),
    )
    assert work_orders_context_service.get_context("") == ("", [])


def test_db_error_returns_empty_never_raises(monkeypatch):
    monkeypatch.setattr(
        work_orders_context_service.work_order_service, "get_work_orders_for_user",
        MagicMock(side_effect=RuntimeError("connection reset")),
    )
    assert work_orders_context_service.get_context("user-1") == ("", [])


def test_no_orders_returns_empty(monkeypatch):
    monkeypatch.setattr(
        work_orders_context_service.work_order_service, "get_work_orders_for_user",
        MagicMock(return_value=[]),
    )
    assert work_orders_context_service.get_context("user-1") == ("", [])


def test_orders_are_formatted_as_quelle_block_and_sources(monkeypatch):
    monkeypatch.setattr(
        work_orders_context_service.work_order_service, "get_work_orders_for_user",
        MagicMock(return_value=[
            {"id": "wo-1", "title": "Update KSV Baunatal", "status": "needs_approval", "repo": "camppilot"},
            {"id": "wo-2", "title": "Signalübertragung Lernmaterialien", "status": "running", "repo": "commandpilot"},
        ]),
    )

    block, sources = work_orders_context_service.get_context("user-1")
    assert block.startswith("### Quelle: Work Orders (CommandPilot)")
    assert "Update KSV Baunatal" in block
    assert "[camppilot]" in block
    assert "needs_approval" in block
    # commandpilot is the default repo — not called out, matches google/outlook
    # calendar's convention of only annotating the non-default case.
    assert "[commandpilot]" not in block
    assert len(sources) == 2
    assert sources[0]["file"] == "Work Orders (CommandPilot)"
    assert "Update KSV Baunatal" in sources[0]["heading"]


def test_token_budget_drops_whole_orders_not_mid_line(monkeypatch):
    monkeypatch.setattr(
        work_orders_context_service.work_order_service, "get_work_orders_for_user",
        MagicMock(return_value=[
            {"id": f"wo-{i}", "title": f"Order {i}", "status": "queued", "repo": "commandpilot"}
            for i in range(20)
        ]),
    )

    block, sources = work_orders_context_service.get_context("user-1", token_budget=10)  # ~40 chars
    assert len(block) < 200
    assert len(sources) < 20
    assert all(not s["heading"].endswith("…") for s in sources)


def test_caps_at_ten_orders_even_within_budget(monkeypatch):
    monkeypatch.setattr(
        work_orders_context_service.work_order_service, "get_work_orders_for_user",
        MagicMock(return_value=[
            {"id": f"wo-{i}", "title": f"Order {i}", "status": "queued", "repo": "commandpilot"}
            for i in range(30)
        ]),
    )

    block, sources = work_orders_context_service.get_context("user-1", token_budget=10_000)
    assert len(sources) == 10
