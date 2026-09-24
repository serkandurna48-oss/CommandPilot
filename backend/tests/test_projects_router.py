#!/usr/bin/env python3
"""Tests for PATCH /api/projects/{id} — specifically the exclude_unset fix
(24.09.2026): a field the client explicitly sends as null (clearing
next_action/risk in the edit form) must reach project_service.update_project
as an explicit None, not be silently dropped. Confirmed against e8c2b02:
exclude_none=True stripped an explicit null the same way it strips an
absent field, so clearing either field reverted to its old value on reload.

Mocks require_owned_record and project_service.update_project directly —
this is about the router's field-inclusion logic, not real DB/ownership
behavior (already covered elsewhere).

Run:
    python -m pytest backend/tests/test_projects_router.py
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
import app.routers.projects as projects_router  # noqa: E402

_FAKE_USER = CurrentUser(id="user-1", email="test@example.com", workspace_id="ws-1")
_FAKE_PROJECT_ROW = {
    "id": "proj-1", "user_id": "user-1", "name": "Softwarebusiness",
    "status": "active", "priority": "high",
    "created_at": "2026-09-01T00:00:00+00:00", "updated_at": "2026-09-24T00:00:00+00:00",
}


def _override_get_current_user():
    return _FAKE_USER


class UpdateProjectFieldInclusionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = _override_get_current_user
        self.owned_patcher = patch.object(projects_router, "require_owned_record", return_value=_FAKE_PROJECT_ROW)
        self.owned_patcher.start()

    def tearDown(self):
        self.owned_patcher.stop()
        app.dependency_overrides.pop(get_current_user, None)

    def test_explicit_null_clears_the_field(self):
        with patch.object(projects_router.project_service, "update_project", return_value={**_FAKE_PROJECT_ROW, "risk": None}) as mock_update:
            resp = self.client.patch("/api/projects/proj-1", json={"risk": None})
        self.assertEqual(resp.status_code, 200)
        sent_updates = mock_update.call_args.args[2]
        self.assertIn("risk", sent_updates)
        self.assertIsNone(sent_updates["risk"])

    def test_omitted_field_is_not_sent_at_all(self):
        with patch.object(projects_router.project_service, "update_project", return_value=_FAKE_PROJECT_ROW) as mock_update:
            resp = self.client.patch("/api/projects/proj-1", json={"name": "Renamed"})
        self.assertEqual(resp.status_code, 200)
        sent_updates = mock_update.call_args.args[2]
        self.assertEqual(sent_updates, {"name": "Renamed"})
        self.assertNotIn("risk", sent_updates)
        self.assertNotIn("next_action", sent_updates)

    def test_both_cleared_fields_reach_the_service_as_null(self):
        with patch.object(projects_router.project_service, "update_project", return_value=_FAKE_PROJECT_ROW) as mock_update:
            resp = self.client.patch("/api/projects/proj-1", json={"next_action": None, "risk": None})
        self.assertEqual(resp.status_code, 200)
        sent_updates = mock_update.call_args.args[2]
        self.assertEqual(sent_updates, {"next_action": None, "risk": None})

    def test_empty_body_returns_400_not_a_no_op_success(self):
        resp = self.client.patch("/api/projects/proj-1", json={})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
