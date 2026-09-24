#!/usr/bin/env python3
"""Tests for POST /api/jarvis/chat (Jarvis v1, phase 4):
- no bearer token -> 401 (before any DB/AI call)
- valid token -> 200, response includes sources from vault_service
- daily spend cap reached -> 429, no AI call made
- suggested_actions passes through whatever generate_chat_reply returned (as
  of JARVIS-C1 — see test_jarvis_quality.py and test_suggested_action_service.py
  for confirm/reject and the two-or-none/no-write-on-chat invariants)

Uses FastAPI's TestClient with get_current_user overridden via
app.dependency_overrides (same object app.routers.jarvis imports), and
unittest.mock.patch on the other collaborators (ensure_user_workspace,
check_daily_cap, vault_service.get_context_for_query, generate_chat_reply,
log_ai_usage) as imported into app.routers.jarvis's namespace. No real
Supabase or OpenAI call is made.

Run:
    python -m pytest backend/tests/test_jarvis_router.py
"""
from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.auth import CurrentUser, get_current_user  # noqa: E402
from app.models.jarvis import JarvisChatAI  # noqa: E402
from app.services.usage_service import DailyCapExceededError  # noqa: E402
import app.routers.jarvis as jarvis_router  # noqa: E402

_FAKE_USER = CurrentUser(id="user-1", email="test@example.com", workspace_id="ws-1")


def _override_get_current_user():
    return _FAKE_USER


class JarvisChatEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_current_user, None)

    def test_missing_token_returns_401(self):
        resp = self.client.post("/api/jarvis/chat", json={"message": "Hallo?"})
        self.assertEqual(resp.status_code, 401)

    def test_valid_token_returns_200_with_sources(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(
                 jarvis_router.vault_service, "get_context_for_query",
                 return_value=(
                     "### Quelle: Projekte/CommandPilot.md — Status\nStatus: active\n\n### Quelle: 00-Index.md\n...",
                     [{"file": "Projekte/CommandPilot.md", "heading": "Status"}],
                     [{"file": "00-Index.md", "heading": ""}],
                 ),
             ), \
             patch.object(jarvis_router.work_orders_context_service, "get_context", return_value=("", [])), \
             patch.object(jarvis_router.projects_context_service, "get_context", return_value=("", [])), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(
                     JarvisChatAI(reply="Laut deinem Second Brain ist CommandPilot aktiv.", suggested_actions=[]),
                     100, 50,
                 ),
             ) as mock_generate, \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Woran arbeite ich gerade?", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("CommandPilot", body["reply"])
        # Only the hit source is in `sources` (visible by default) — the base
        # context entry lands in the separate base_sources field, not here.
        self.assertEqual(body["sources"], [{"source_file": "Projekte/CommandPilot.md", "source_heading": "Status"}])
        self.assertEqual(body["base_sources"], [{"source_file": "00-Index.md", "source_heading": ""}])
        self.assertEqual(body["suggested_actions"], [])
        # user_id must never be taken from the client — only from get_current_user
        mock_generate.assert_called_once()

    def test_calendar_and_notion_context_are_merged_into_context_block(self):
        # 22.09.2026: google_calendar_service/outlook_calendar_service/
        # notion_tasks_service/work_orders_context_service were added
        # alongside vault_service — this asserts all five are actually
        # folded into the same context_block generate_chat_reply receives,
        # not silently unused.
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(jarvis_router, "is_personal_integrations_owner", return_value=True), \
             patch.object(
                 jarvis_router.vault_service, "get_context_for_query",
                 return_value=("### Quelle: 00-Index.md\n...", [], []),
             ), \
             patch.object(
                 jarvis_router.google_calendar_service, "get_context",
                 return_value=(
                     "### Quelle: Kalender – Google (Google Calendar, 2026-09-21 – 2026-09-24)\n- Termin heute (Google)",
                     [{"file": "Kalender – Google", "heading": "Termin heute (Google)"}],
                 ),
             ), \
             patch.object(
                 jarvis_router.outlook_calendar_service, "get_context",
                 return_value=(
                     "### Quelle: Kalender – Outlook (2026-09-21 – 2026-09-24)\n- Termin heute (Outlook)",
                     [{"file": "Kalender – Outlook", "heading": "Termin heute (Outlook)"}],
                 ),
             ), \
             patch.object(
                 jarvis_router.notion_tasks_service, "get_context",
                 return_value=(
                     "### Quelle: Notion — Offene Aufgaben\n- Bewerbung schreiben",
                     [{"file": "Notion — Offene Aufgaben", "heading": "Bewerbung schreiben"}],
                 ),
             ), \
             patch.object(
                 jarvis_router.work_orders_context_service, "get_context",
                 return_value=(
                     "### Quelle: Work Orders (CommandPilot)\n- Update KSV Baunatal — Status: needs_approval",
                     [{"file": "Work Orders (CommandPilot)", "heading": "Update KSV Baunatal — Status: needs_approval"}],
                 ),
             ), \
             patch.object(jarvis_router.projects_context_service, "get_context", return_value=("", [])), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(JarvisChatAI(reply="ok", suggested_actions=[]), 10, 5),
             ) as mock_generate, \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Was ist heute los?", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        # Third positional arg to generate_chat_reply is context_block.
        merged_context = mock_generate.call_args.args[2]
        self.assertIn("00-Index.md", merged_context)
        self.assertIn("Termin heute (Google)", merged_context)
        self.assertIn("Termin heute (Outlook)", merged_context)
        self.assertIn("Bewerbung schreiben", merged_context)
        self.assertIn("Update KSV Baunatal", merged_context)

        body = resp.json()
        self.assertEqual(
            body["calendar_sources"],
            [
                {"source_file": "Kalender – Google", "source_heading": "Termin heute (Google)"},
                {"source_file": "Kalender – Outlook", "source_heading": "Termin heute (Outlook)"},
            ],
        )
        self.assertEqual(
            body["task_sources"],
            [{"source_file": "Notion — Offene Aufgaben", "source_heading": "Bewerbung schreiben"}],
        )
        self.assertEqual(
            body["work_order_sources"],
            [{"source_file": "Work Orders (CommandPilot)", "source_heading": "Update KSV Baunatal — Status: needs_approval"}],
        )

    def test_non_owner_never_gets_calendar_or_notion_context(self):
        # Regression test for a real, live-reproduced data leak (23.09.2026):
        # a second, unrelated authenticated user's Jarvis chat returned the
        # vault owner's real Outlook calendar event and real personal Notion
        # tasks verbatim, because google_calendar_service/outlook_calendar_service/
        # notion_tasks_service take no user_id at all — one Composio identity
        # for the whole process. is_personal_integrations_owner() gates this
        # at the router; here that gate resolves False (default patch target
        # not applied, i.e. the real function runs against a _FAKE_USER whose
        # id can never match a real VAULT_OWNER_USER_ID), so none of the three
        # services should even be called. Explicitly patched to False rather
        # than relying on _FAKE_USER not matching whatever VAULT_OWNER_USER_ID
        # happens to be in the real backend/.env — that env-dependence is
        # exactly the fragility that let three other tests break silently
        # the moment this project's .env got a real value for it.
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(jarvis_router, "is_personal_integrations_owner", return_value=False), \
             patch.object(jarvis_router.vault_service, "get_context_for_query", return_value=("", [], [])), \
             patch.object(jarvis_router.google_calendar_service, "get_context") as mock_google, \
             patch.object(jarvis_router.outlook_calendar_service, "get_context") as mock_outlook, \
             patch.object(jarvis_router.notion_tasks_service, "get_context") as mock_notion, \
             patch.object(
                 jarvis_router.work_orders_context_service, "get_context", return_value=("", []),
             ), \
             patch.object(jarvis_router.projects_context_service, "get_context", return_value=("", [])), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(JarvisChatAI(reply="ok", suggested_actions=[]), 10, 5),
             ), \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Was steht heute in meinem Kalender?", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        mock_google.assert_not_called()
        mock_outlook.assert_not_called()
        mock_notion.assert_not_called()
        body = resp.json()
        self.assertEqual(body["calendar_sources"], [])
        self.assertEqual(body["task_sources"], [])

    def test_calendar_and_notion_failures_do_not_break_chat(self):
        # Same non-fatal contract as vault_service's fetch failure below —
        # a broken Composio call must degrade to "no external context", not
        # a 500.
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(
                 jarvis_router.vault_service, "get_context_for_query",
                 return_value=("", [], []),
             ), \
             patch.object(
                 jarvis_router.google_calendar_service, "get_context",
                 side_effect=RuntimeError("composio down"),
             ), \
             patch.object(
                 jarvis_router.outlook_calendar_service, "get_context",
                 side_effect=RuntimeError("composio down"),
             ), \
             patch.object(
                 jarvis_router.notion_tasks_service, "get_context",
                 side_effect=RuntimeError("composio down"),
             ), \
             patch.object(
                 jarvis_router.work_orders_context_service, "get_context",
                 side_effect=RuntimeError("db down"),
             ), \
             patch.object(
                 jarvis_router.projects_context_service, "get_context",
                 side_effect=RuntimeError("db down"),
             ), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(JarvisChatAI(reply="ok", suggested_actions=[]), 10, 5),
             ) as mock_generate, \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Was ist heute los?", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_generate.call_args.args[2], "")
        body = resp.json()
        self.assertEqual(body["calendar_sources"], [])
        self.assertEqual(body["task_sources"], [])
        self.assertEqual(body["work_order_sources"], [])

    def test_profile_language_is_resolved_and_passed_to_ai_call(self):
        # Regression test: generate_chat_reply used to always be called
        # without a language, hardcoding German inside the prompt regardless
        # of the user's actual profile.language — reported as "the UI
        # language doesn't fully switch over."
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(
            jarvis_router, "ensure_user_workspace",
            return_value={"workspace_id": "ws-1", "profile": {"language": "en"}},
        ), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(
                 jarvis_router.vault_service, "get_context_for_query",
                 return_value=("", [], []),
             ), \
             patch.object(jarvis_router.work_orders_context_service, "get_context", return_value=("", [])), \
             patch.object(jarvis_router.projects_context_service, "get_context", return_value=("", [])), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(JarvisChatAI(reply="Your project is active.", suggested_actions=[]), 10, 5),
             ) as mock_generate, \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "What am I working on?", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        # Fourth positional arg is the resolved language, sourced from the
        # profile — never the request body, which has no language field.
        self.assertEqual(mock_generate.call_args.args[3], "en")

    def test_unknown_profile_language_falls_back_to_english(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(
            jarvis_router, "ensure_user_workspace",
            return_value={"workspace_id": "ws-1", "profile": {"language": "fr"}},
        ), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(
                 jarvis_router.vault_service, "get_context_for_query",
                 return_value=("", [], []),
             ), \
             patch.object(jarvis_router.work_orders_context_service, "get_context", return_value=("", [])), \
             patch.object(jarvis_router.projects_context_service, "get_context", return_value=("", [])), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(JarvisChatAI(reply="ok", suggested_actions=[]), 10, 5),
             ) as mock_generate, \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post("/api/jarvis/chat", json={"message": "Hi", "history": []})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_generate.call_args.args[3], "en")

    def test_daily_cap_reached_returns_429_and_skips_ai_call(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(
                 jarvis_router, "check_daily_cap",
                 side_effect=DailyCapExceededError(Decimal("0.55"), Decimal("0.50"), "2026-09-19T00:00:00+00:00"),
             ), \
             patch.object(jarvis_router, "generate_chat_reply") as mock_generate:
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Noch eine Frage"},
            )

        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json()["detail"]["code"], "DAILY_SPEND_CAP_REACHED")
        mock_generate.assert_not_called()


class SuggestedActionEndpointTests(unittest.TestCase):
    """
    POST /api/jarvis/suggested-actions/{confirm,reject} (JARVIS-C1, Phase 5).
    Business logic (idempotency, work-order creation) is covered in
    test_suggested_action_service.py — this file only checks the HTTP
    boundary: auth, ownership sourcing, and status code mapping.
    """

    _ACTION_PAYLOAD = {
        "title": "CampPilot Onboarding für JK vorbereiten",
        "description": "Onboarding-Schritte dokumentieren und in CampPilot abbilden.",
        "team_type": "development",
        "target_repo_name": "camppilot",
        "risk": "medium",
        "requires_approval": False,
        "sources": [],
    }

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_current_user, None)

    def test_confirm_without_token_returns_401(self):
        resp = self.client.post(
            "/api/jarvis/suggested-actions/confirm",
            json={"action": self._ACTION_PAYLOAD, "request_id": "req-1"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_confirm_success_never_takes_user_id_from_the_request(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(
                 jarvis_router.suggested_action_service, "confirm_suggested_action",
                 return_value={"decision": "confirmed", "work_order_id": "wo-1", "already_decided": False},
             ) as mock_confirm:
            resp = self.client.post(
                "/api/jarvis/suggested-actions/confirm",
                json={"action": self._ACTION_PAYLOAD, "request_id": "req-1"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"decision": "confirmed", "work_order_id": "wo-1", "already_decided": False})
        # First positional arg is user_id — must be the authenticated user's
        # id (from get_current_user), never anything the client could set.
        self.assertEqual(mock_confirm.call_args.args[0], _FAKE_USER.id)

    def test_reject_success(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(
                 jarvis_router.suggested_action_service, "reject_suggested_action",
                 return_value={"decision": "rejected", "work_order_id": None, "already_decided": False},
             ) as mock_reject:
            resp = self.client.post(
                "/api/jarvis/suggested-actions/reject",
                json={"action": self._ACTION_PAYLOAD, "request_id": "req-2"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"decision": "rejected", "work_order_id": None, "already_decided": False})
        self.assertEqual(mock_reject.call_args.args[0], _FAKE_USER.id)

    def test_confirm_conflict_maps_to_409(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(
                 jarvis_router.suggested_action_service, "confirm_suggested_action",
                 side_effect=jarvis_router.AlreadyDecidedError("rejected", None),
             ):
            resp = self.client.post(
                "/api/jarvis/suggested-actions/confirm",
                json={"action": self._ACTION_PAYLOAD, "request_id": "req-3"},
            )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["detail"]["code"], "ALREADY_DECIDED")
        self.assertEqual(resp.json()["detail"]["decision"], "rejected")


class SuggestedActionDecisionListEndpointTests(unittest.TestCase):
    """GET /api/jarvis/suggested-actions/decisions — decision history read."""

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_current_user, None)

    def test_missing_token_returns_401(self):
        resp = self.client.get("/api/jarvis/suggested-actions/decisions")
        self.assertEqual(resp.status_code, 401)

    def test_returns_decisions_scoped_to_authenticated_user(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user

        with patch.object(
            jarvis_router.suggested_action_service, "list_decisions",
            return_value=[
                {
                    "id": "dec-1",
                    "decision": "confirmed",
                    "title": "CampPilot Onboarding für JK vorbereiten",
                    "team_type": "development",
                    "target_repo_name": "camppilot",
                    "risk": "medium",
                    "requires_approval": False,
                    "sources": [{"source_file": "Projekte/CampPilot.md", "source_heading": ""}],
                    "work_order_id": "wo-1",
                    "created_at": "2026-09-21T10:00:00+00:00",
                },
                {
                    "id": "dec-2",
                    "decision": "rejected",
                    "title": "Unwichtiger Vorschlag",
                    "team_type": "development",
                    "target_repo_name": None,
                    "risk": "low",
                    "requires_approval": False,
                    "sources": [],
                    "work_order_id": None,
                    "created_at": "2026-09-20T09:00:00+00:00",
                },
            ],
        ) as mock_list:
            resp = self.client.get("/api/jarvis/suggested-actions/decisions")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["decisions"]), 2)
        self.assertEqual(body["decisions"][0]["decision"], "confirmed")
        self.assertEqual(body["decisions"][0]["work_order_id"], "wo-1")
        self.assertEqual(body["decisions"][1]["decision"], "rejected")
        self.assertIsNone(body["decisions"][1]["work_order_id"])
        # user_id must come from get_current_user, never the client
        self.assertEqual(mock_list.call_args.args[0], _FAKE_USER.id)


if __name__ == "__main__":
    unittest.main()
