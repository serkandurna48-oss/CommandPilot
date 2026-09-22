"""
Tests for outlook_calendar_service.py (Jarvis external context, 22.09.2026).

Pytest-native (uses monkeypatch), mirrors test_google_calendar_service.py's
never-raises-on-missing-config assertions, plus a Composio-call mock for the
formatting path — no real network/Composio call is ever made.

Run:
    python -m pytest backend/tests/test_outlook_calendar_service.py
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

from app.services import outlook_calendar_service  # noqa: E402


def test_missing_api_key_returns_empty_without_calling_composio(monkeypatch):
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_API_KEY", "")
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_USER_ID", "composio-user-1")
    monkeypatch.setattr(outlook_calendar_service, "get_client", MagicMock(side_effect=AssertionError("must not be called")))
    assert outlook_calendar_service.get_context() == ("", [])


def test_missing_user_id_returns_empty_without_calling_composio(monkeypatch):
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_API_KEY", "key")
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_USER_ID", "")
    monkeypatch.setattr(outlook_calendar_service, "get_client", MagicMock(side_effect=AssertionError("must not be called")))
    assert outlook_calendar_service.get_context() == ("", [])


def test_composio_error_returns_empty_never_raises(monkeypatch):
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_API_KEY", "key")
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_USER_ID", "composio-user-1")

    fake_client = MagicMock()
    fake_client.tools.execute.side_effect = RuntimeError("connection reset")
    monkeypatch.setattr(outlook_calendar_service, "get_client", lambda: fake_client)

    assert outlook_calendar_service.get_context() == ("", [])


def test_no_events_returns_empty(monkeypatch):
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_API_KEY", "key")
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_USER_ID", "composio-user-1")

    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {"data": {"value": []}}
    monkeypatch.setattr(outlook_calendar_service, "get_client", lambda: fake_client)

    assert outlook_calendar_service.get_context() == ("", [])


def test_events_are_formatted_as_quelle_block_and_sources(monkeypatch):
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_API_KEY", "key")
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_USER_ID", "composio-user-1")

    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {
        "data": {
            "value": [
                {
                    "subject": "VW-Job Schicht",
                    "start": {"dateTime": "2026-09-22T10:00:00.0000000", "timeZone": "UTC"},
                    "end": {"dateTime": "2026-09-22T11:00:00.0000000", "timeZone": "UTC"},
                },
                {"subject": "Ohne Startzeit"},  # missing start -> skipped, not crashed
            ]
        }
    }
    monkeypatch.setattr(outlook_calendar_service, "get_client", lambda: fake_client)

    block, sources = outlook_calendar_service.get_context()
    assert block.startswith("### Quelle: Kalender – Outlook")
    assert "VW-Job Schicht" in block
    assert "Ohne Startzeit" not in block
    assert len(sources) == 1
    assert sources[0]["file"] == "Kalender – Outlook"
    assert "VW-Job Schicht" in sources[0]["heading"]
    fake_client.tools.execute.assert_called_once()
    assert fake_client.tools.execute.call_args.args[0] == "OUTLOOK_GET_CALENDAR_VIEW"
    assert fake_client.tools.execute.call_args.kwargs["user_id"] == "composio-user-1"
    assert fake_client.tools.execute.call_args.kwargs["arguments"]["timezone"] == "Europe/Berlin"


def test_token_budget_drops_whole_events_not_mid_line(monkeypatch):
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_API_KEY", "key")
    monkeypatch.setattr(outlook_calendar_service.settings, "COMPOSIO_USER_ID", "composio-user-1")

    fake_client = MagicMock()
    fake_client.tools.execute.return_value = {
        "data": {
            "value": [
                {
                    "subject": "Event " + str(i),
                    "start": {"dateTime": f"2026-09-22T{i:02d}:00:00.0000000", "timeZone": "UTC"},
                    "end": {"dateTime": f"2026-09-22T{i:02d}:30:00.0000000", "timeZone": "UTC"},
                }
                for i in range(20)
            ]
        }
    }
    monkeypatch.setattr(outlook_calendar_service, "get_client", lambda: fake_client)

    block, sources = outlook_calendar_service.get_context(token_budget=20)  # ~80 chars
    assert len(block) < 300
    assert len(sources) < 20
    # Every kept source is a complete, untruncated event heading.
    assert all(not s["heading"].endswith("…") for s in sources)
