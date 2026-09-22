#!/usr/bin/env python3
"""Tests for scripts/run_work_order_daemon.py — the poll/claim/subprocess
orchestration loop for the "Autonom starten" feature (see
supabase/migrations/016_work_orders_daemon_run_requested.sql,
frontend/components/operator/LifecycleControls.tsx).

Stdlib-only (unittest + unittest.mock), same posture as every other
scripts/test_*.py — call_api() and subprocess.run() are faked; nothing here
hits a real API or spawns a real run_work_order.py process. The actual
execution logic (safety checks, budget gate, retries) lives entirely
inside run_work_order.py and is NOT re-tested here — this file only
verifies the daemon's own, small responsibility: poll, filter, claim
(before starting anything), and invoke the right subprocess command.

Run:
    python scripts/test_run_work_order_daemon.py
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_work_order_daemon as daemon  # noqa: E402


def _args(**overrides):
    base = dict(
        adapter="claude_code", max_budget_usd=0.20, per_step=False,
        poll_interval=15.0, api_url="http://localhost:8000", token="fake-token",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _order(order_id: str, status: str = "queued", requested_at: str | None = "2026-09-22T10:00:00+00:00") -> dict:
    return {"id": order_id, "status": status, "daemon_run_requested_at": requested_at}


class FetchRequestedWorkOrdersTests(unittest.TestCase):
    def test_filters_to_queued_with_request_set_only(self):
        orders = [
            _order("wo-running", status="running"),
            _order("wo-no-request", requested_at=None),
            _order("wo-match"),
            _order("wo-blocked", status="blocked"),
        ]
        with patch.object(daemon, "call_api", return_value=orders):
            result = daemon.fetch_requested_work_orders("http://api", "token")
        self.assertEqual([o["id"] for o in result], ["wo-match"])

    def test_sorts_oldest_request_first(self):
        orders = [
            _order("wo-newer", requested_at="2026-09-22T12:00:00+00:00"),
            _order("wo-oldest", requested_at="2026-09-22T09:00:00+00:00"),
            _order("wo-middle", requested_at="2026-09-22T10:30:00+00:00"),
        ]
        with patch.object(daemon, "call_api", return_value=orders):
            result = daemon.fetch_requested_work_orders("http://api", "token")
        self.assertEqual([o["id"] for o in result], ["wo-oldest", "wo-middle", "wo-newer"])


class ClaimTests(unittest.TestCase):
    def test_claim_patches_field_to_null(self):
        with patch.object(daemon, "call_api", return_value={}) as mock_call:
            ok = daemon.claim("http://api", "token", "wo-1")
        self.assertTrue(ok)
        mock_call.assert_called_once_with(
            "http://api", "token", "PATCH", "/api/work-orders/wo-1",
            {"daemon_run_requested_at": None},
        )

    def test_claim_failure_is_logged_not_raised(self):
        with patch.object(daemon, "call_api", side_effect=daemon.DaemonApiError("boom")):
            ok = daemon.claim("http://api", "token", "wo-1")
        self.assertFalse(ok)


class RunOneTests(unittest.TestCase):
    def test_builds_correct_subprocess_command(self):
        args = _args(adapter="claude_code_sandboxed", max_budget_usd=0.5, per_step=True)
        with patch.object(daemon.subprocess, "run", return_value=MagicMock(returncode=0)) as mock_run:
            rc = daemon.run_one(args, "wo-1")

        self.assertEqual(rc, 0)
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1], str(daemon.RUN_WORK_ORDER_SCRIPT))
        self.assertEqual(cmd[2], "wo-1")
        self.assertIn("--mode", cmd)
        self.assertEqual(cmd[cmd.index("--mode") + 1], "execute")
        self.assertEqual(cmd[cmd.index("--adapter") + 1], "claude_code_sandboxed")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "0.5")
        self.assertIn("--per-step", cmd)
        self.assertEqual(cmd[cmd.index("--token") + 1], "fake-token")

    def test_omits_per_step_flag_when_not_requested(self):
        args = _args(per_step=False)
        with patch.object(daemon.subprocess, "run", return_value=MagicMock(returncode=0)) as mock_run:
            daemon.run_one(args, "wo-1")
        cmd = mock_run.call_args.args[0]
        self.assertNotIn("--per-step", cmd)


class PollOnceTests(unittest.TestCase):
    def test_claims_before_starting_subprocess(self):
        # The exact ordering guarantee the module docstring promises: the
        # claim PATCH must happen before subprocess.run(), never after.
        call_order: list[str] = []

        def fake_call_api(api_url, token, method, path, payload=None):
            if method == "GET":
                return [_order("wo-1")]
            call_order.append("claim")
            return {}

        def fake_subprocess_run(cmd, cwd=None):
            call_order.append("subprocess")
            return MagicMock(returncode=0)

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon.subprocess, "run", side_effect=fake_subprocess_run):
            daemon.poll_once(_args())

        self.assertEqual(call_order, ["claim", "subprocess"])

    def test_skips_starting_subprocess_when_claim_fails(self):
        def fake_call_api(api_url, token, method, path, payload=None):
            if method == "GET":
                return [_order("wo-1")]
            raise daemon.DaemonApiError("claim failed")

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon.subprocess, "run") as mock_run:
            daemon.poll_once(_args())

        mock_run.assert_not_called()

    def test_processes_multiple_matches_sequentially_oldest_first(self):
        orders = [
            _order("wo-newer", requested_at="2026-09-22T12:00:00+00:00"),
            _order("wo-oldest", requested_at="2026-09-22T09:00:00+00:00"),
        ]
        started: list[str] = []
        claimed: list[str] = []

        def fake_call_api(api_url, token, method, path, payload=None):
            if method == "GET":
                return orders
            claimed.append(path.rsplit("/", 1)[-1])
            return {}

        def fake_subprocess_run(cmd, cwd=None):
            started.append(cmd[2])  # work_order_id is argv[2]
            return MagicMock(returncode=0)

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon.subprocess, "run", side_effect=fake_subprocess_run):
            daemon.poll_once(_args())

        # Oldest first, and both processed sequentially within one poll cycle.
        self.assertEqual(claimed, ["wo-oldest", "wo-newer"])
        self.assertEqual(started, ["wo-oldest", "wo-newer"])

    def test_no_matches_makes_no_calls_beyond_the_initial_fetch(self):
        with patch.object(daemon, "call_api", return_value=[]) as mock_call, \
             patch.object(daemon.subprocess, "run") as mock_run:
            daemon.poll_once(_args())
        mock_call.assert_called_once()  # only the GET, no claim PATCH
        mock_run.assert_not_called()

    def test_fetch_failure_does_not_raise(self):
        with patch.object(daemon, "call_api", side_effect=daemon.DaemonApiError("down")), \
             patch.object(daemon.subprocess, "run") as mock_run:
            daemon.poll_once(_args())  # must not raise
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
