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


# CMD-003 fixed: confirm_suggested_action() now updates the claim with the
# real work_order_id immediately after create_work_order() succeeds, before
# the (non-essential) activity log is even attempted — only a
# create_work_order() failure itself releases the claim. A failed activity
# log write is logged and swallowed, not fatal, so it can no longer trigger
# a claim release that lets a retry create a duplicate work order. The
# original assertion here (`pytest.raises(RuntimeError, ...)` on the first
# call) assumed the old, wrong behavior where an audit-log failure aborted
# the whole confirmation — the fixed, correct behavior is that it doesn't.
def test_confirm_survives_an_activity_log_failure_without_duplicating_the_work_order():
    db = _FakeDB()
    with patch.object(suggestions, "get_db", return_value=db), \
         patch.object(suggestions.work_order_service, "create_work_order", side_effect=[{"id": "wo-1"}, {"id": "wo-2"}]) as create, \
         patch.object(suggestions.work_order_service, "append_activity_log", side_effect=[RuntimeError("injected audit failure"), {}]):
        first = suggestions.confirm_suggested_action("owner", "ws", "Reviewer", _ACTION, "same-click")
        second = suggestions.confirm_suggested_action("owner", "ws", "Reviewer", _ACTION, "same-click")
    assert first["work_order_id"] == "wo-1"
    assert second["work_order_id"] == "wo-1"
    assert create.call_count == 1


# CMD-003 fixed: a "confirmed" decision row whose work_order_id is still
# None (the process died between claiming and creating/recording the work
# order) is no longer trusted as proof of a completed confirmation — it is
# resumed using the existing claim row instead, so the caller always gets a
# real work_order_id back. The original test never mocked
# work_order_service.create_work_order/append_activity_log, so exercising
# the fixed (resuming) code path here needs the same mocks as the test
# above — without this fix, the original test never actually reached that
# code, since the old code returned early on any "confirmed" row.
def test_incomplete_confirmation_resumes_instead_of_returning_a_null_work_order():
    db = _FakeDB()
    with patch.object(suggestions, "get_db", return_value=db), \
         patch.object(suggestions.work_order_service, "create_work_order", return_value={"id": "wo-resumed"}), \
         patch.object(suggestions.work_order_service, "append_activity_log", return_value={}):
        suggestions._claim_request_id("owner", "ws", "same-click", "confirmed", _ACTION)
        response = suggestions.confirm_suggested_action("owner", "ws", "Reviewer", _ACTION, "same-click")
    assert response["decision"] != "confirmed" or response["work_order_id"] is not None
    assert response["work_order_id"] == "wo-resumed"


# CMD-004 fixed, backend side: work_order_service.claim_daemon_run() is now
# an atomic compare-and-set (UPDATE ... WHERE daemon_run_requested_at IS NOT
# NULL) instead of an unconditional PATCH — see routers/work_orders.py's
# special-cased handling for {"daemon_run_requested_at": None} updates. The
# original test here mocked call_api() to unconditionally succeed for BOTH
# calls, which can never exercise this fix: the actual winner-decision logic
# is entirely server-side (this daemon function has none of its own beyond
# "did call_api raise or not"). Corrected to simulate what the real atomic
# backend produces for two racing callers: the first PATCH succeeds, the
# second gets HTTP 409 (already claimed) -> DaemonApiError -> claim()
# already correctly turns that into False (see claim()'s own except clause,
# unchanged) — this test now actually verifies that translation.
def test_two_daemon_claims_have_only_one_winner():
    import run_work_order_daemon as daemon
    session = daemon.TokenSession("synthetic-token")
    with patch.object(
        daemon, "call_api",
        side_effect=[
            {"id": "wo", "daemon_run_requested_at": None},
            daemon.DaemonApiError("PATCH /api/work-orders/wo -> HTTP 409: Work order already claimed"),
        ],
    ):
        winners = [daemon.claim("http://invalid.test", session, "wo") for _ in range(2)]
    assert sum(winners) == 1


# CMD-005 fixed: HEUTIGES DATUM now resolves Europe/Berlin via zoneinfo
# (backend/requirements.txt gained tzdata so this also works on Windows dev
# machines, not just Render's Linux runtime) instead of raw UTC — 22:30 UTC
# is already past local midnight in Berlin during CEST.
def test_today_is_berlin_date_at_local_midnight():
    with patch.object(jarvis_chat, "datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 23, 22, 30, tzinfo=timezone.utc)
        prompt = jarvis_chat.build_chat_prompt("today?", [], "")
    assert prompt.startswith("HEUTIGES DATUM: 2026-09-24")
