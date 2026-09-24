"""Independent local review, 2026-09-23. No network or production writes.

Run from repo root: .venv/Scripts/python.exe -m pytest
docs/reviews/test_review_regressions.py -q -rx
Known defects are strict xfails: XPASS requires independent re-review.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend/tests"), str(ROOT / "scripts")]
os.environ.update(SUPABASE_URL="http://127.0.0.1:54321", SUPABASE_SERVICE_ROLE_KEY="review-fake",
                  OPENAI_API_KEY="review-fake", COMPOSIO_API_KEY="", COMPOSIO_USER_ID="", VAULT_PATH="")

from app import auth
from app.models.jarvis import JarvisChatAI, JarvisChatRequest
from app.prompts import jarvis_chat
from app.routers import jarvis
from app.services import suggested_action_service as suggestions
from app.services import runner_connection_service as runners
from test_suggested_action_service import _FakeDB, _ACTION
from test_runner_connection_service import _FakeDB as RunnerDB


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    real_connect = socket.socket.connect

    def blocked(self, address, *args, **kwargs):
        # Loopback is exempted: asyncio's ProactorEventLoop (Windows) opens
        # a real loopback socket pair internally as its self-pipe on every
        # asyncio.run() — found the hard way when de-xfailing CMD-001 here
        # made that plumbing detail surface as a hard failure instead of
        # being silently absorbed by strict xfail. Not the "network access
        # by code under test" this fixture exists to catch.
        host = address[0] if isinstance(address, tuple) else address
        if host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("Review tests must never open network connections")

    monkeypatch.setattr(socket.socket, "connect", blocked)


# CMD-001 fixed: is_personal_integrations_owner() (app/core/config.py) now
# gates google_calendar_service/outlook_calendar_service/notion_tasks_service
# in routers/jarvis.py — a non-owner user_id never reaches get_context() at all.
def test_external_context_is_not_shared_with_another_user():
    google = jarvis.google_calendar_service
    client = MagicMock()
    client.tools.execute.return_value = {"data": {"items": [
        {"summary": "SYNTHETIC OWNER EVENT", "start": {"dateTime": "2026-09-23T12:00:00Z"}}
    ]}}
    with patch.object(google.settings, "COMPOSIO_API_KEY", "review-fake"), \
         patch.object(google.settings, "COMPOSIO_USER_ID", "external-owner"), \
         patch.object(google, "get_client", return_value=client), \
         patch.object(jarvis, "ensure_user_workspace", return_value={"workspace_id": "other-ws", "profile": {}}), \
         patch.object(jarvis, "check_daily_cap"), \
         patch.object(jarvis, "log_ai_usage"), \
         patch.object(jarvis.vault_service, "get_context_for_query", return_value=("", [], [])), \
         patch.object(jarvis.outlook_calendar_service, "get_context", return_value=("", [])), \
         patch.object(jarvis.notion_tasks_service, "get_context", return_value=("", [])), \
         patch.object(jarvis.work_orders_context_service, "get_context", return_value=("", [])), \
         patch.object(jarvis, "generate_chat_reply", new=AsyncMock(return_value=(JarvisChatAI(reply="test"), 1, 1))):
        result = asyncio.run(jarvis.chat(JarvisChatRequest(message="today?"), auth.CurrentUser("another-user", None, "other-ws")))
    assert result.calendar_sources == []


# CMD-002 fixed: get_current_user (app/auth.py) is now browser-session-only
# by default — a runner token is only accepted by get_current_user_or_runner,
# which just routers/work_orders.py uses. projects.py never switched to it,
# so a runner token no longer authenticates there at all: 401 (the token
# doesn't resolve to any recognized session for this endpoint), not 403
# (which would imply a recognized-but-insufficiently-privileged identity).
def test_runner_cannot_access_personal_projects():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import projects
    db = RunnerDB()
    app = FastAPI()
    app.include_router(projects.router, prefix="/projects")
    with patch.object(runners, "get_db", return_value=db), patch.object(auth, "get_db", return_value=db), \
         patch.object(projects.project_service, "get_projects_for_user", return_value=[]):
        pairing = runners.create_pairing_request("test")
        runners.approve_pairing("owner", "workspace", pairing["user_code"], None)
        response = TestClient(app).get("/projects/me", headers={"Authorization": "Bearer " + pairing["runner_token"]})
    assert response.status_code == 401


@pytest.mark.xfail(strict=True, reason="CMD-003: audit failure removes claim but leaves created order; retry duplicates")
def test_confirm_retry_after_audit_failure_creates_only_one_order():
    db = _FakeDB()
    with patch.object(suggestions, "get_db", return_value=db), \
         patch.object(suggestions.work_order_service, "create_work_order", side_effect=[{"id": "wo-1"}, {"id": "wo-2"}]) as create, \
         patch.object(suggestions.work_order_service, "append_activity_log", side_effect=[RuntimeError("injected audit failure"), {}]):
        with pytest.raises(RuntimeError, match="injected audit failure"):
            suggestions.confirm_suggested_action("owner", "ws", "Reviewer", _ACTION, "same-click")
        suggestions.confirm_suggested_action("owner", "ws", "Reviewer", _ACTION, "same-click")
    assert create.call_count == 1


@pytest.mark.xfail(strict=True, reason="CMD-003: incomplete claim is returned as confirmed without work order")
def test_incomplete_confirmation_is_not_success():
    db = _FakeDB()
    with patch.object(suggestions, "get_db", return_value=db):
        suggestions._claim_request_id("owner", "ws", "same-click", "confirmed", _ACTION)
        response = suggestions.confirm_suggested_action("owner", "ws", "Reviewer", _ACTION, "same-click")
    assert response["decision"] != "confirmed" or response["work_order_id"] is not None


@pytest.mark.xfail(strict=True, reason="CMD-004: daemon claim is unconditional, two callers both succeed")
def test_two_daemon_claims_have_only_one_winner():
    import run_work_order_daemon as daemon
    session = daemon.TokenSession("synthetic-token")
    with patch.object(daemon, "call_api", return_value={"id": "wo", "daemon_run_requested_at": None}):
        winners = [daemon.claim("http://invalid.test", session, "wo") for _ in range(2)]
    assert sum(winners) == 1


@pytest.mark.xfail(strict=True, reason="CMD-005: UTC yesterday is labelled today after Berlin midnight")
def test_today_is_berlin_date_at_local_midnight():
    with patch.object(jarvis_chat, "datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 23, 22, 30, tzinfo=timezone.utc)
        prompt = jarvis_chat.build_chat_prompt("today?", [], "")
    assert prompt.startswith("HEUTIGES DATUM: 2026-09-24")
