#!/usr/bin/env python3
"""Tests for POST /api/jarvis/chat (Jarvis v1, phase 4):
- no bearer token -> 401 (before any DB/AI call)
- valid token -> 200, response includes sources from vault_service
- daily spend cap reached -> 429, no AI call made
- suggested_actions is always [] in v1

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
                 return_value=("### Quelle: Projekte/CommandPilot.md\nStatus: active", [{"file": "Projekte/CommandPilot.md", "heading": ""}]),
             ), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=("Laut deinem Second Brain ist CommandPilot aktiv.", 100, 50),
             ) as mock_generate, \
             patch.object(jarvis_router, "log_ai_usage", return_value=None):
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Woran arbeite ich gerade?", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("CommandPilot", body["reply"])
        self.assertEqual(body["sources"], [{"source_file": "Projekte/CommandPilot.md", "source_heading": ""}])
        self.assertEqual(body["suggested_actions"], [])
        # user_id must never be taken from the client — only from get_current_user
        mock_generate.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
