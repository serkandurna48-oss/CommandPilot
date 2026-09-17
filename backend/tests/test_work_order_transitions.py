#!/usr/bin/env python3
"""Tests for the CP-OP01 atomic state machine:
backend/app/services/work_order_service.py's transition_work_order(), which
delegates to the transition_work_order() Postgres function
(supabase/migrations/010_transition_work_order_function.sql).

Stdlib-only (unittest + unittest.mock) — no dependency install, no pytest,
consistent with the zero-third-party-dependency stance already established
by scripts/test_*.py. The Supabase client is faked entirely; nothing here
talks to a real database. The transition-table/precondition/audit-log logic
itself lives in the SQL function and is NOT exercised by these tests — that
needs a manual pass against a real Supabase project (see the CP-OP01
report's "what these tests do not cover" note). What these tests verify is
the Python-side contract: the right RPC is called with the right params, and
the failure shapes the SQL function raises (work_order_not_found /
illegal_transition / missing review package) are mapped to the exception the
router expects (LookupError -> 404, ValueError -> 400).

Run:
    python backend/tests/test_work_order_transitions.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# app.core.config.Settings() reads these at import time with no defaults.
# Dummy values are enough — get_db() is patched out in every test below and
# never actually connects anywhere.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.services import work_order_service  # noqa: E402


class FakePostgrestError(Exception):
    """Mimics postgrest-py's APIError shape closely enough for
    _extract_postgrest_message(): a `.message` attribute carrying the text
    the SQL function's RAISE EXCEPTION produced."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class FakeResult:
    def __init__(self, data):
        self.data = data


class _NullScopeTable:
    """Fakes db.table("approval_scopes").select(...).eq(...).maybe_single()
    resolving to "no scope row" — transition_work_order() and
    update_work_order_fields() both look this up after their main write."""

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return None


class FakeRPCClient:
    """Fakes db.rpc(name, params).execute() — records the call, then either
    returns a canned result or raises a canned error. db.table(...) always
    resolves to _NullScopeTable so tests don't need to fake a real scope."""

    def __init__(self, result_data=None, error: Exception | None = None):
        self._result_data = result_data
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    def rpc(self, name: str, params: dict):
        self.calls.append((name, params))
        return self

    def execute(self):
        if self._error is not None:
            raise self._error
        return FakeResult(self._result_data)

    def table(self, *_args, **_kwargs):
        return _NullScopeTable()


class TransitionWorkOrderTests(unittest.TestCase):
    def test_legal_transition_calls_rpc_with_expected_params(self):
        fake_db = FakeRPCClient(result_data={"id": "wo-1", "status": "approved"})
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            result = work_order_service.transition_work_order("wo-1", "approved", source="ui", reason="looks good")

        self.assertEqual(result["status"], "approved")
        self.assertEqual(len(fake_db.calls), 1)
        name, params = fake_db.calls[0]
        self.assertEqual(name, "transition_work_order")
        self.assertEqual(
            params,
            {
                "p_work_order_id": "wo-1",
                "p_to_status": "approved",
                "p_source": "ui",
                "p_reason": "looks good",
            },
        )

    def test_rpc_returning_a_list_unwraps_first_row(self):
        # Some PostgREST configurations wrap a single-row function result in
        # a list — accept either shape.
        fake_db = FakeRPCClient(result_data=[{"id": "wo-1", "status": "queued"}])
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            result = work_order_service.transition_work_order("wo-1", "queued")
        self.assertEqual(result["status"], "queued")

    def test_defaults_source_to_ui_and_reason_to_none(self):
        fake_db = FakeRPCClient(result_data={"id": "wo-1", "status": "cancelled"})
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            work_order_service.transition_work_order("wo-1", "cancelled")
        _, params = fake_db.calls[0]
        self.assertEqual(params["p_source"], "ui")
        self.assertIsNone(params["p_reason"])

    def test_work_order_not_found_raises_lookup_error(self):
        fake_db = FakeRPCClient(error=FakePostgrestError("work_order_not_found"))
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            with self.assertRaises(LookupError):
                work_order_service.transition_work_order("missing-id", "approved")

    def test_illegal_transition_raises_value_error(self):
        fake_db = FakeRPCClient(error=FakePostgrestError("illegal_transition: draft -> accepted is not allowed"))
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            with self.assertRaises(ValueError) as ctx:
                work_order_service.transition_work_order("wo-1", "accepted")
        self.assertIn("illegal_transition", str(ctx.exception))

    def test_missing_review_package_raises_value_error_with_exact_message(self):
        # The router (and docs/manual-e2e-checklist.md AC10) rely on this
        # exact wording, carried over verbatim from the pre-CP-OP01 guard.
        exact_message = "Cannot set status to review_ready: no review package exists for this work order yet."
        fake_db = FakeRPCClient(error=FakePostgrestError(exact_message))
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            with self.assertRaises(ValueError) as ctx:
                work_order_service.transition_work_order("wo-1", "review_ready")
        self.assertEqual(str(ctx.exception), exact_message)

    def test_same_state_transition_succeeds_without_special_casing_in_python(self):
        # The SQL function treats same-state as a no-op (CP-OP01 correction
        # #6) — the Python layer just passes the status through and trusts
        # the function's response. This documents that the Python layer adds
        # no special handling of its own.
        fake_db = FakeRPCClient(result_data={"id": "wo-1", "status": "review_ready"})
        with patch.object(work_order_service, "get_db", return_value=fake_db):
            result = work_order_service.transition_work_order("wo-1", "review_ready")
        self.assertEqual(result["status"], "review_ready")


class UpdateWorkOrderFieldsTests(unittest.TestCase):
    def test_rejects_status_in_payload(self):
        with self.assertRaises(ValueError):
            work_order_service.update_work_order_fields("wo-1", {"status": "approved"})

    def test_applies_non_status_fields(self):
        fake_table = MagicMock()
        fake_table.update.return_value = fake_table
        fake_table.eq.return_value = fake_table
        fake_table.execute.return_value = FakeResult([{"id": "wo-1", "recommended_next_step": "ship it"}])

        fake_db = MagicMock()
        fake_db.table.side_effect = lambda name: fake_table if name == "work_orders" else _NullScopeTable()

        with patch.object(work_order_service, "get_db", return_value=fake_db):
            result = work_order_service.update_work_order_fields("wo-1", {"recommended_next_step": "ship it"})

        self.assertEqual(result["recommended_next_step"], "ship it")
        fake_table.update.assert_called_once_with({"recommended_next_step": "ship it"})


if __name__ == "__main__":
    unittest.main()
