"""
Tests for notion_tasks_service.py (Jarvis external context, 22.09.2026).

Pytest-native (uses monkeypatch), mirrors test_calendar_service.py's
never-raises-on-missing-config assertions, plus a Composio-call mock for the
formatting path — no real network/Composio call is ever made.

Run:
    python -m pytest backend/tests/test_notion_tasks_service.py
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

from app.services import notion_tasks_service  # noqa: E402


def _set_full_config(monkeypatch, **overrides):
    monkeypatch.setattr(notion_tasks_service.settings, "COMPOSIO_API_KEY", overrides.get("api_key", "key"))
    monkeypatch.setattr(notion_tasks_service.settings, "COMPOSIO_USER_ID", overrides.get("user_id", "composio-user-1"))
    monkeypatch.setattr(notion_tasks_service.settings, "NOTION_TASKS_DATABASE_ID", overrides.get("db_id", "db-1"))


def test_missing_database_id_returns_empty_without_calling_composio(monkeypatch):
    _set_full_config(monkeypatch, db_id="")
    monkeypatch.setattr(notion_tasks_service, "get_client", MagicMock(side_effect=AssertionError("must not be called")))
    assert notion_tasks_service.get_context() == ("", [])


def test_missing_api_key_returns_empty_without_calling_composio(monkeypatch):
    _set_full_config(monkeypatch, api_key="")
    monkeypatch.setattr(notion_tasks_service, "get_client", MagicMock(side_effect=AssertionError("must not be called")))
    assert notion_tasks_service.get_context() == ("", [])


def test_composio_error_returns_empty_never_raises(monkeypatch):
    _set_full_config(monkeypatch)
    fake_client = MagicMock()
    fake_client.tools.execute.side_effect = RuntimeError("connection reset")
    monkeypatch.setattr(notion_tasks_service, "get_client", lambda: fake_client)

    assert notion_tasks_service.get_context() == ("", [])


def test_no_rows_returns_empty(monkeypatch):
    _set_full_config(monkeypatch)
    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {"data": {"results": []}}
    monkeypatch.setattr(notion_tasks_service, "get_client", lambda: fake_client)

    assert notion_tasks_service.get_context() == ("", [])


def test_tasks_are_formatted_as_quelle_block_and_sources(monkeypatch):
    _set_full_config(monkeypatch)
    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {
        "data": {
            "results": [
                {
                    "properties": {
                        "Task name": {
                            "type": "title",
                            "title": [{"plain_text": "Bewerbung Praktikum schreiben"}],
                        },
                        "Status": {"type": "status", "status": {"name": "To-do"}},
                        "Due": {"type": "date", "date": {"start": "2026-09-25"}},
                    }
                },
                {"properties": {}},  # no title -> skipped, not crashed
            ]
        }
    }
    monkeypatch.setattr(notion_tasks_service, "get_client", lambda: fake_client)

    block, sources = notion_tasks_service.get_context()
    assert block.startswith("### Quelle: Notion")
    assert "Bewerbung Praktikum schreiben" in block
    assert "To-do" in block
    assert "2026-09-25" in block
    assert len(sources) == 1
    assert sources[0]["file"] == "Notion — Offene Aufgaben"
    assert "Bewerbung Praktikum schreiben" in sources[0]["heading"]
    fake_client.tools.execute.assert_called_once()
    assert fake_client.tools.execute.call_args.args[0] == "NOTION_QUERY_DATABASE"
    assert fake_client.tools.execute.call_args.kwargs["arguments"]["database_id"] == "db-1"


def test_status_and_due_detected_by_type_not_english_property_name(monkeypatch):
    # Regression: a real database can name these fields in any language
    # ("Aufgabe"/"Fällig" instead of "Task name"/"Due") — detection must go
    # by Notion's own `type` key ("status"/"date"), never a hardcoded name.
    # Also includes an unrelated `select` field ("Priorität") to confirm it
    # is never mistaken for the status field.
    _set_full_config(monkeypatch)
    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {
        "data": {
            "results": [
                {
                    "properties": {
                        "Aufgabe": {
                            "type": "title",
                            "title": [{"plain_text": "Befund"}],
                        },
                        "Priorität": {"type": "select", "select": {"name": "Hoch"}},
                        "Status": {"type": "status", "status": {"name": "Wating"}},
                        "Fällig": {"type": "date", "date": {"start": "2026-09-30"}},
                    }
                },
            ]
        }
    }
    monkeypatch.setattr(notion_tasks_service, "get_client", lambda: fake_client)

    block, sources = notion_tasks_service.get_context()
    assert "Befund" in block
    assert "Wating" in block
    assert "2026-09-30" in block
    assert "Hoch" not in block


def test_token_budget_drops_whole_tasks_not_mid_line(monkeypatch):
    _set_full_config(monkeypatch)
    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {
        "data": {
            "results": [
                {
                    "properties": {
                        "Task name": {
                            "type": "title",
                            "title": [{"plain_text": f"Task {i}"}],
                        },
                    }
                }
                for i in range(20)
            ]
        }
    }
    monkeypatch.setattr(notion_tasks_service, "get_client", lambda: fake_client)

    block, sources = notion_tasks_service.get_context(token_budget=10)  # ~40 chars
    assert len(block) < 200
    assert len(sources) < 20
    assert all(not s["heading"].endswith("…") for s in sources)
