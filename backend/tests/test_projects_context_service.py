"""
Tests for projects_context_service.py (Jarvis context source, 24.09.2026).

Pytest-native (uses monkeypatch), mirrors test_work_orders_context_service.py's
structure — mocks project_service.get_projects_for_user directly (CommandPilot's
own DB call), no external API involved.

Run:
    python -m pytest backend/tests/test_projects_context_service.py
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

from app.services import projects_context_service  # noqa: E402


def test_missing_user_id_returns_empty_without_calling_db(monkeypatch):
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(side_effect=AssertionError("must not be called")),
    )
    assert projects_context_service.get_context("") == ("", [])


def test_db_error_returns_empty_never_raises(monkeypatch):
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(side_effect=RuntimeError("connection reset")),
    )
    assert projects_context_service.get_context("user-1") == ("", [])


def test_no_live_projects_returns_empty(monkeypatch):
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(return_value=[{"name": "Old thing", "status": "done", "priority": "low"}]),
    )
    assert projects_context_service.get_context("user-1") == ("", [])


def test_done_and_archived_are_excluded_but_others_are_not(monkeypatch):
    projects = [
        {"name": "Softwarebusiness", "status": "active", "priority": "high", "next_action": "Ship v1", "risk": None},
        {"name": "Old thing", "status": "done", "priority": "high", "next_action": None, "risk": None},
        {"name": "Shelved", "status": "archived", "priority": "high", "next_action": None, "risk": None},
        {"name": "Gartenzaun", "status": "waiting", "priority": "medium", "next_action": "Material kaufen", "risk": "Mangelnde Zeit"},
    ]
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(return_value=projects),
    )
    block, sources = projects_context_service.get_context("user-1")
    assert "Softwarebusiness" in block
    assert "Gartenzaun" in block
    assert "Old thing" not in block
    assert "Shelved" not in block
    assert len(sources) == 2


def test_sorted_high_priority_first(monkeypatch):
    projects = [
        {"name": "Low prio", "status": "active", "priority": "low", "next_action": None, "risk": None},
        {"name": "High prio", "status": "active", "priority": "high", "next_action": None, "risk": None},
        {"name": "Medium prio", "status": "active", "priority": "medium", "next_action": None, "risk": None},
    ]
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(return_value=projects),
    )
    block, _ = projects_context_service.get_context("user-1")
    assert block.index("High prio") < block.index("Medium prio") < block.index("Low prio")


def test_next_action_and_risk_are_included_when_set(monkeypatch):
    projects = [
        {"name": "Camp business", "status": "active", "priority": "high",
         "next_action": "Zusammenarbeit mit JK Academy starten", "risk": "Sinkende Nachfrage"},
    ]
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(return_value=projects),
    )
    block, sources = projects_context_service.get_context("user-1")
    assert "Zusammenarbeit mit JK Academy starten" in block
    assert "Sinkende Nachfrage" in block
    assert "Nächste Aufgabe:" in block
    assert "Blocker:" in block
    assert sources[0]["file"] == "Projekte (CommandPilot)"


def test_token_budget_drops_whole_projects_not_mid_line(monkeypatch):
    projects = [
        {"name": f"Project {i}", "status": "active", "priority": "high",
         "next_action": "x" * 200, "risk": None}
        for i in range(20)
    ]
    monkeypatch.setattr(
        projects_context_service.project_service, "get_projects_for_user",
        MagicMock(return_value=projects),
    )
    block, sources = projects_context_service.get_context("user-1", token_budget=50)
    assert all(not s["heading"].endswith("…") for s in sources)
    assert len(sources) < len(projects)
