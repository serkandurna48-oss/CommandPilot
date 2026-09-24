#!/usr/bin/env python3
"""Tests for the daemon_run_requested_at field handling in
backend/app/routers/work_orders.py::update_work_order() — the trigger
signal scripts/run_work_order_daemon.py claims by PATCHing it to null
(supabase/migrations/016_work_orders_daemon_run_requested.sql).

Narrow, targeted regression test for one specific bug: the router builds
its update dict via `data.model_dump(exclude_none=True)`, which — without
the fix this test guards — silently DROPS an explicit `daemon_run_requested_
at: null` the same way it drops "field not sent at all", meaning the
daemon's claim PATCH would appear to succeed (200 OK) while never actually
clearing the field in the database. Calls the router function directly
(not via TestClient/HTTP) with require_owned_record and
work_order_service mocked — no real Supabase connection.

Run:
    python backend/tests/test_work_order_daemon_trigger.py
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

from app.auth import CurrentUser  # noqa: E402
from app.models.work_order import WorkOrderUpdate  # noqa: E402
from app.routers import work_orders as work_orders_router  # noqa: E402


FAKE_USER = CurrentUser(id="user-1", email="test@example.com", workspace_id=None)


class DaemonTriggerFieldTests(unittest.TestCase):
    def test_explicit_null_clears_the_field(self):
        # CMD-004 (found in review, 24.09.2026): a bare
        # {"daemon_run_requested_at": None} — exactly what the daemon's
        # claim() sends — now routes through the atomic claim_daemon_run(),
        # not the generic (unconditional) update_work_order_fields(). See
        # ClaimDaemonRunTests in test_work_order_transitions.py for the
        # atomicity itself; this test only guards the router's routing.
        with patch.object(work_orders_router, "require_owned_record", return_value={"id": "wo-1"}), \
             patch.object(work_orders_router.work_order_service, "claim_daemon_run", return_value={"id": "wo-1"}) as mock_claim:
            work_orders_router.update_work_order(
                "wo-1", WorkOrderUpdate(daemon_run_requested_at=None), user=FAKE_USER,
            )

        mock_claim.assert_called_once_with("wo-1")

    def test_explicit_null_alone_is_not_treated_as_empty_body(self):
        # Before the original fix, model_dump(exclude_none=True) alone
        # would produce an empty dict for this exact payload, and the
        # router would raise "No fields to update" (400) instead of
        # clearing the field.
        with patch.object(work_orders_router, "require_owned_record", return_value={"id": "wo-1"}), \
             patch.object(work_orders_router.work_order_service, "claim_daemon_run", return_value={"id": "wo-1"}):
            result = work_orders_router.update_work_order(
                "wo-1", WorkOrderUpdate(daemon_run_requested_at=None), user=FAKE_USER,
            )
        self.assertEqual(result, {"id": "wo-1"})

    def test_claim_conflict_returns_409_not_a_silent_success(self):
        # CMD-004: require_owned_record already confirmed the id exists and
        # is owned by this user, so a failed atomic claim here can only
        # mean someone else (another daemon poll) already won it — must
        # surface as a real conflict, not a 200 with stale/wrong data.
        from fastapi import HTTPException
        with patch.object(work_orders_router, "require_owned_record", return_value={"id": "wo-1"}), \
             patch.object(work_orders_router.work_order_service, "claim_daemon_run", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                work_orders_router.update_work_order(
                    "wo-1", WorkOrderUpdate(daemon_run_requested_at=None), user=FAKE_USER,
                )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_setting_a_real_timestamp_still_works(self):
        # The "Start autonom" button's PATCH — the other direction, unaffected
        # by the fix (a non-None value was never dropped by exclude_none).
        with patch.object(work_orders_router, "require_owned_record", return_value={"id": "wo-1"}), \
             patch.object(work_orders_router.work_order_service, "update_work_order_fields", return_value={"id": "wo-1"}) as mock_update:
            work_orders_router.update_work_order(
                "wo-1", WorkOrderUpdate(daemon_run_requested_at="2026-09-22T18:00:00+00:00"), user=FAKE_USER,
            )
        mock_update.assert_called_once_with("wo-1", {"daemon_run_requested_at": "2026-09-22T18:00:00+00:00"})

    def test_omitting_the_field_entirely_does_not_touch_it(self):
        # A plain, unrelated field update (e.g. recommended_next_step) must
        # NOT accidentally clear daemon_run_requested_at just because the
        # field wasn't mentioned in this particular request.
        with patch.object(work_orders_router, "require_owned_record", return_value={"id": "wo-1"}), \
             patch.object(work_orders_router.work_order_service, "update_work_order_fields", return_value={"id": "wo-1"}) as mock_update:
            work_orders_router.update_work_order(
                "wo-1", WorkOrderUpdate(recommended_next_step="ship it"), user=FAKE_USER,
            )
        mock_update.assert_called_once_with("wo-1", {"recommended_next_step": "ship it"})

    def test_null_alongside_status_transition_still_transitions(self):
        # A daemon claim could in principle be combined with a status change
        # in one call — confirm both the transition path and the field-clear
        # path fire correctly together, neither silently swallowing the other.
        with patch.object(work_orders_router, "require_owned_record", return_value={"id": "wo-1"}), \
             patch.object(work_orders_router.work_order_service, "transition_work_order", return_value={"id": "wo-1", "status": "running"}) as mock_transition, \
             patch.object(work_orders_router.work_order_service, "update_work_order_fields", return_value={"id": "wo-1"}) as mock_update:
            work_orders_router.update_work_order(
                "wo-1", WorkOrderUpdate(status="running", daemon_run_requested_at=None), user=FAKE_USER,
            )
        mock_transition.assert_called_once()
        mock_update.assert_called_once_with("wo-1", {"daemon_run_requested_at": None})


if __name__ == "__main__":
    unittest.main()
