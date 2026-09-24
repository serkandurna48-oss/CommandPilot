#!/usr/bin/env python3
"""Tests for GET /api/integrations/vault-status — the Home dashboard's
data-source indicator (24.09.2026). Thin router, all real logic already
covered by test_vault_service.py's get_vault_status tests; this only
checks the HTTP wiring (auth required, service result passed through).

Run:
    python -m pytest backend/tests/test_integrations_router.py
"""
from __future__ import annotations

import os
import sys
import unittest
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
import app.routers.integrations as integrations_router  # noqa: E402

_FAKE_USER = CurrentUser(id="user-1", email="test@example.com", workspace_id="ws-1")


def _override_get_current_user():
    return _FAKE_USER


class VaultStatusEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_current_user, None)

    def test_missing_token_returns_401(self):
        resp = self.client.get("/api/integrations/vault-status")
        self.assertEqual(resp.status_code, 401)

    def test_passes_through_the_service_result(self):
        app.dependency_overrides[get_current_user] = _override_get_current_user
        fake_status = {"ok": True, "reason": None, "notes_found": 3, "checked_at": "2026-09-24T10:00:00+00:00"}
        with patch.object(integrations_router.vault_service, "get_vault_status", return_value=fake_status) as mock_status:
            resp = self.client.get("/api/integrations/vault-status")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), fake_status)
        mock_status.assert_called_once_with("user-1")


if __name__ == "__main__":
    unittest.main()
