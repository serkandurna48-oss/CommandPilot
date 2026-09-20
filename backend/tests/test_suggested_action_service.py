"""
Tests for app/services/suggested_action_service.py (JARVIS-C1, Phase 5/6).

Exercises the confirm/reject business logic against an in-memory fake
Supabase table (no real DB, no real OpenAI call) — verifies:
- confirm creates a work order + approval scope (via the real
  work_order_service.create_work_order, mocked here) + an activity log entry
- reject creates no work order at all
- double-confirm / double-reject with the same request_id is idempotent —
  the expensive side effect (work order creation) happens exactly once
- confirming a request_id already rejected (or vice versa) is rejected with
  AlreadyDecidedError, never silently applied
- a failed work order creation releases the claimed request_id so the same
  click can be retried cleanly

Run:
    python -m pytest backend/tests/test_suggested_action_service.py -v
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

from app.models.jarvis import SuggestedAction  # noqa: E402
from app.services import suggested_action_service as svc  # noqa: E402


# ─── In-memory fake of the postgrest-py fluent query interface ──────────────────
class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table: "_FakeTable"):
        self._table = table
        self._filters: dict = {}
        self._op = None
        self._payload = None

    def select(self, *_cols):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def _matches(self, row):
        return all(row.get(k) == v for k, v in self._filters.items())

    def execute(self):
        if self._op == "select":
            return _FakeResult([r for r in self._table.rows if self._matches(r)])
        if self._op == "insert":
            key = (self._payload.get("user_id"), self._payload.get("request_id"))
            if key in self._table.unique_keys:
                raise RuntimeError("duplicate key value violates unique constraint \"idx_suggested_action_decisions_request\"")
            row = dict(self._payload)
            row["id"] = f"decision-{len(self._table.rows) + 1}"
            self._table.rows.append(row)
            self._table.unique_keys.add(key)
            return _FakeResult([row])
        if self._op == "update":
            matched = [r for r in self._table.rows if self._matches(r)]
            for r in matched:
                r.update(self._payload)
            return _FakeResult(matched)
        if self._op == "delete":
            matched = [r for r in self._table.rows if self._matches(r)]
            for r in matched:
                self._table.rows.remove(r)
                self._table.unique_keys.discard((r.get("user_id"), r.get("request_id")))
            return _FakeResult(matched)
        raise NotImplementedError(self._op)


class _FakeTable:
    def __init__(self):
        self.rows: list[dict] = []
        self.unique_keys: set = set()

    def select(self, *cols):
        return _FakeQuery(self).select(*cols)

    def insert(self, payload):
        return _FakeQuery(self).insert(payload)

    def update(self, payload):
        return _FakeQuery(self).update(payload)

    def delete(self):
        return _FakeQuery(self).delete()


class _FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable())


_ACTION = SuggestedAction(
    title="CampPilot Onboarding für JK vorbereiten",
    description="Onboarding-Schritte dokumentieren und in CampPilot abbilden.",
    risk="medium",
    requires_approval=False,
)


class SuggestedActionServiceTests(unittest.TestCase):
    def setUp(self):
        self.fake_db = _FakeDB()
        self.get_db_patcher = patch.object(svc, "get_db", return_value=self.fake_db)
        self.get_db_patcher.start()

    def tearDown(self):
        self.get_db_patcher.stop()

    def test_confirm_creates_work_order_and_activity_log(self):
        with patch.object(
            svc.work_order_service, "create_work_order",
            return_value={"id": "wo-1", "approval_scope_id": "scope-1"},
        ) as mock_create, patch.object(
            svc.work_order_service, "append_activity_log", return_value={"id": "log-1"}
        ) as mock_log:
            result = svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-1")

        self.assertEqual(result, {"decision": "confirmed", "work_order_id": "wo-1", "already_decided": False})
        mock_create.assert_called_once()
        # Reuses work_order_service — no parallel creation path: the goal,
        # title, team_type and target_repo_name of the created work order
        # must trace back to the proposal.
        call_args = mock_create.call_args.args
        self.assertEqual(call_args[0], "user-1")
        self.assertEqual(call_args[1], "ws-1")
        work_order_create = call_args[3]
        self.assertEqual(work_order_create.title, _ACTION.title)
        self.assertEqual(work_order_create.goal, _ACTION.description)
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.args[0], "wo-1")

        decisions = self.fake_db.table("suggested_action_decisions").rows
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision"], "confirmed")
        self.assertEqual(decisions[0]["work_order_id"], "wo-1")

    def test_reject_never_creates_a_work_order(self):
        with patch.object(svc.work_order_service, "create_work_order") as mock_create, \
             patch.object(svc.work_order_service, "append_activity_log") as mock_log:
            result = svc.reject_suggested_action("user-1", "ws-1", _ACTION, "req-2")

        self.assertEqual(result, {"decision": "rejected", "work_order_id": None, "already_decided": False})
        mock_create.assert_not_called()
        mock_log.assert_not_called()

        decisions = self.fake_db.table("suggested_action_decisions").rows
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision"], "rejected")
        self.assertIsNone(decisions[0]["work_order_id"])

    def test_double_confirm_same_request_id_creates_work_order_once(self):
        with patch.object(
            svc.work_order_service, "create_work_order",
            return_value={"id": "wo-1", "approval_scope_id": "scope-1"},
        ) as mock_create, patch.object(svc.work_order_service, "append_activity_log", return_value={"id": "log-1"}):
            first = svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-double")
            second = svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-double")

        mock_create.assert_called_once()
        self.assertFalse(first["already_decided"])
        self.assertTrue(second["already_decided"])
        self.assertEqual(first["work_order_id"], second["work_order_id"])
        self.assertEqual(len(self.fake_db.table("suggested_action_decisions").rows), 1)

    def test_double_reject_same_request_id_is_idempotent(self):
        first = svc.reject_suggested_action("user-1", "ws-1", _ACTION, "req-double-reject")
        second = svc.reject_suggested_action("user-1", "ws-1", _ACTION, "req-double-reject")

        self.assertFalse(first["already_decided"])
        self.assertTrue(second["already_decided"])
        self.assertEqual(len(self.fake_db.table("suggested_action_decisions").rows), 1)

    def test_confirm_after_reject_raises_already_decided(self):
        svc.reject_suggested_action("user-1", "ws-1", _ACTION, "req-conflict")

        with patch.object(svc.work_order_service, "create_work_order") as mock_create:
            with self.assertRaises(svc.AlreadyDecidedError) as ctx:
                svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-conflict")

        self.assertEqual(ctx.exception.existing_decision, "rejected")
        mock_create.assert_not_called()

    def test_reject_after_confirm_raises_already_decided(self):
        with patch.object(
            svc.work_order_service, "create_work_order",
            return_value={"id": "wo-9", "approval_scope_id": "scope-9"},
        ), patch.object(svc.work_order_service, "append_activity_log", return_value={"id": "log-9"}):
            svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-conflict-2")

        with self.assertRaises(svc.AlreadyDecidedError) as ctx:
            svc.reject_suggested_action("user-1", "ws-1", _ACTION, "req-conflict-2")

        self.assertEqual(ctx.exception.existing_decision, "confirmed")
        self.assertEqual(ctx.exception.work_order_id, "wo-9")

    def test_confirm_failure_releases_claim_for_retry(self):
        with patch.object(
            svc.work_order_service, "create_work_order", side_effect=RuntimeError("db hiccup")
        ):
            with self.assertRaises(RuntimeError):
                svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-retry")

        # The claim must be released — no orphaned decision row blocking a
        # legitimate retry with the same request_id.
        self.assertEqual(self.fake_db.table("suggested_action_decisions").rows, [])

        with patch.object(
            svc.work_order_service, "create_work_order",
            return_value={"id": "wo-retry", "approval_scope_id": "scope-retry"},
        ), patch.object(svc.work_order_service, "append_activity_log", return_value={"id": "log-retry"}):
            retried = svc.confirm_suggested_action("user-1", "ws-1", "Serkan", _ACTION, "req-retry")

        self.assertEqual(retried["work_order_id"], "wo-retry")
        self.assertFalse(retried["already_decided"])

    def test_requires_approval_action_gets_a_stricter_scope(self):
        strict_action = _ACTION.model_copy(update={"requires_approval": True})
        with patch.object(
            svc.work_order_service, "create_work_order",
            return_value={"id": "wo-strict", "approval_scope_id": "scope-strict"},
        ) as mock_create, patch.object(svc.work_order_service, "append_activity_log", return_value={"id": "log-strict"}):
            svc.confirm_suggested_action("user-1", "ws-1", "Serkan", strict_action, "req-strict")

        work_order_create = mock_create.call_args.args[3]
        # requires_approval=True means nothing is auto-allowed — everything
        # (including the routinely-allowed actions) waits for a human nod.
        self.assertEqual(work_order_create.approval_scope.allowed_actions, [])
        self.assertIn("code_edit_within_scope", work_order_create.approval_scope.requires_approval)


if __name__ == "__main__":
    unittest.main()
