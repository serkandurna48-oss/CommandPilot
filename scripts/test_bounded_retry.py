#!/usr/bin/env python3
"""Tests for the CP-OP02 bounded auto-retry loop:
scripts/run_work_order.py's _run_adapter_with_bounded_retry() and its
helpers (_git_snapshot, _worktree_changed, _current_status,
_finalize_technical_failure).

Stdlib-only (unittest + unittest.mock), consistent with the
zero-third-party-dependency stance of the scripts it tests. adapter.execute(),
call_api(), fetch_work_order(), and _git_snapshot() are all faked — nothing
here spawns a real subprocess, hits a real API, or touches a real git repo.

Run:
    python scripts/test_bounded_retry.py
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_work_order as harness  # noqa: E402
from runner_adapters.base import ExecuteOutcome, ProgressReporter  # noqa: E402


class FakeAdapter:
    """A minimal RunnerAdapter stand-in whose execute() replays a
    pre-scripted sequence of outcomes/exceptions, one per call."""

    def __init__(self, results: list):
        self.info = argparse.Namespace(name="fake_adapter")
        self._results = list(results)
        self.execute_calls: list[float | None] = []

    def execute(self, order, session_path, runner_command, max_budget_usd=None, progress=None):
        self.execute_calls.append(max_budget_usd)
        self.progress_seen = progress
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _order():
    return {
        "id": "wo-1",
        "steps": [{"id": "s1", "title": "Do the thing", "assigned_role": "coder"}],
        "time_limit_minutes": 90,
    }


def _args(**overrides):
    base = dict(
        work_order_id="wo-1", mode="execute", adapter="fake", api_url="http://localhost:8000",
        token="fake", force=False, result_file=None, runner_command=None, max_budget_usd=None, dry_run=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


UNCHANGED = ("sha-1", "")  # (HEAD, porcelain status) — same value before/after means "unchanged"
CHANGED = ("sha-2", "")  # different HEAD than UNCHANGED means "changed"


class BoundedRetryTests(unittest.TestCase):
    def _run(self, adapter, call_api_side_effect, status_sequence, git_snapshots, total_budget=None):
        """status_sequence: values returned by successive fetch_work_order()
        calls (i.e. successive _current_status() checks). git_snapshots:
        values returned by successive _git_snapshot() calls."""
        status_iter = iter(status_sequence)
        git_iter = iter(git_snapshots)
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            with patch.object(harness, "log_line"), \
                 patch.object(harness, "fetch_work_order", side_effect=lambda *a, **k: {"status": next(status_iter)}), \
                 patch.object(harness, "call_api", side_effect=call_api_side_effect), \
                 patch.object(harness, "_git_snapshot", side_effect=lambda cwd: next(git_iter)), \
                 patch.object(harness, "cmd_import_result", return_value=0) as mock_import:
                rc = harness._run_adapter_with_bounded_retry(
                    _args(), adapter, _order(), session_path, total_budget, "run-1"
                )
                return rc, mock_import

    def test_valid_result_is_imported_and_never_retried(self):
        # finalStatus is deliberately "blocked" — a real runner-reported
        # outcome is never auto-retried regardless of which finalStatus it is.
        outcome = ExecuteOutcome(exit_code=0, output_log_path=Path("log"), result={"finalStatus": "blocked"})
        adapter = FakeAdapter([outcome])
        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=lambda *a, **k: {},
            status_sequence=["running", "running"],  # before attempt, before import
            git_snapshots=[UNCHANGED],
        )
        self.assertEqual(len(adapter.execute_calls), 1)
        mock_import.assert_called_once()
        self.assertEqual(rc, 0)

    def test_a_progress_reporter_is_always_passed_to_execute(self):
        outcome = ExecuteOutcome(exit_code=0, output_log_path=Path("log"), result={"finalStatus": "review_ready"})
        adapter = FakeAdapter([outcome])
        self._run(
            adapter,
            call_api_side_effect=lambda *a, **k: {},
            status_sequence=["running", "running"],
            git_snapshots=[UNCHANGED],
        )
        self.assertIsInstance(adapter.progress_seen, ProgressReporter)

    def test_interrupted_outcome_marks_step_failed_and_never_retries(self):
        # should_stop()==True mid-execute() (user hit Stop) must be treated
        # as neither a technical failure (no retry) nor a normal cancel-
        # before-attempt (the running step needs its own failed+blocked_reason
        # PATCH, on top of the existing AgentRun-terminalization path).
        outcome = ExecuteOutcome(
            exit_code=124, output_log_path=Path("log"), result=None, interrupted=True,
        )
        adapter = FakeAdapter([outcome])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"],  # only the top-of-loop check before the one attempt
            git_snapshots=[UNCHANGED],
        )
        self.assertEqual(len(adapter.execute_calls), 1)  # no retry attempted
        self.assertEqual(rc, 0)
        mock_import.assert_not_called()

        step_patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1/steps/s1"]
        self.assertEqual(len(step_patches), 1)
        self.assertEqual(step_patches[0]["status"], "failed")
        self.assertEqual(step_patches[0]["blocked_reason"], "Vom Nutzer unterbrochen")

        run_patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1/agent-runs/run-1"]
        self.assertEqual(len(run_patches), 1)
        self.assertEqual(run_patches[0]["status"], "failed")

    def test_technical_failure_with_unchanged_worktree_retries_up_to_max(self):
        adapter = FakeAdapter([RuntimeError("boom 1"), RuntimeError("boom 2"), RuntimeError("boom 3")])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            if method == "POST" and path.endswith("/agent-runs"):
                return {"id": f"run-{len(calls)}"}
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"] * 10,  # cancellation-checked before every attempt and every retry
            git_snapshots=[UNCHANGED, UNCHANGED, UNCHANGED, UNCHANGED, UNCHANGED, UNCHANGED],
            total_budget=None,
        )
        self.assertEqual(len(adapter.execute_calls), 3)
        self.assertEqual(rc, 1)
        mock_import.assert_not_called()

        # Two new AgentRuns should have been created (for attempts 2 and 3),
        # each carrying the right attempt_number/retry_reason.
        created = [payload for (method, path, payload) in calls if method == "POST" and path.endswith("/agent-runs")]
        self.assertEqual([c["attempt_number"] for c in created], [2, 3])
        self.assertEqual(created[0]["retry_reason"], "technical_failure_attempt_1")
        self.assertEqual(created[1]["retry_reason"], "technical_failure_attempt_2")

        # The final work-order PATCH must set status=failed with the
        # "retries exhausted" reason, sourced as 'harness' (never 'ui').
        final_patch = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1"][-1]
        self.assertEqual(final_patch["status"], "failed")
        self.assertEqual(final_patch["source"], "harness")
        self.assertEqual(final_patch["reason"], "technical_failure_retries_exhausted")

    def test_technical_failure_with_changed_worktree_never_retries(self):
        adapter = FakeAdapter([RuntimeError("boom")])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"],
            git_snapshots=[UNCHANGED, CHANGED],  # HEAD differs before vs. after the attempt
        )
        self.assertEqual(len(adapter.execute_calls), 1)  # no retry attempted
        self.assertEqual(rc, 1)
        mock_import.assert_not_called()

        final_patch = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1"][-1]
        self.assertEqual(final_patch["reason"], "technical_failure_with_worktree_changes")

    def test_undeterminable_worktree_state_is_treated_as_changed(self):
        # _git_snapshot() returning None (git missing/failed) must fail
        # closed — treated exactly like a changed working tree, never like
        # an unchanged one.
        adapter = FakeAdapter([RuntimeError("boom")])
        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=lambda *a, **k: {},
            status_sequence=["running"],
            git_snapshots=[None, None],
        )
        self.assertEqual(len(adapter.execute_calls), 1)
        self.assertEqual(rc, 1)

    def test_cancelled_before_first_attempt_never_starts_runner_and_terminalizes_existing_run(self):
        # cmd_prompt_file() already created "run-1" (status=running) before
        # this loop ever runs — cancellation before attempt 1 must not leave
        # it stuck on 'running' forever.
        adapter = FakeAdapter([ExecuteOutcome(exit_code=0, output_log_path=Path("log"), result={"finalStatus": "review_ready"})])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["cancelled"],
            git_snapshots=[],
        )
        self.assertEqual(len(adapter.execute_calls), 0)
        mock_import.assert_not_called()
        self.assertEqual(rc, 0)

        patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1/agent-runs/run-1"]
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["status"], "failed")

    def test_cancelled_after_valid_result_skips_import_and_terminalizes_run(self):
        outcome = ExecuteOutcome(exit_code=0, output_log_path=Path("log"), result={"finalStatus": "review_ready"})
        adapter = FakeAdapter([outcome])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running", "cancelled"],  # ok before attempt, cancelled before import
            git_snapshots=[UNCHANGED],
        )
        self.assertEqual(len(adapter.execute_calls), 1)
        mock_import.assert_not_called()
        self.assertEqual(rc, 0)

        patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1/agent-runs/run-1"]
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["status"], "failed")

    def test_cancelled_between_retries_stops_without_a_third_attempt_and_terminalizes_run(self):
        # status_sequence: "running" satisfies the top-of-loop check for
        # attempt 1; "cancelled" is then seen at the check between "attempt 1
        # technically failed" and "create AgentRun for attempt 2" — cancel
        # must win there, before any second AgentRun is ever created.
        adapter = FakeAdapter([RuntimeError("boom 1")])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            if method == "POST" and path.endswith("/agent-runs"):
                return {"id": "run-2"}
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running", "cancelled"],
            git_snapshots=[UNCHANGED, UNCHANGED],
        )
        self.assertEqual(len(adapter.execute_calls), 1)
        self.assertEqual(rc, 0)
        mock_import.assert_not_called()

        # The one attempt that actually ran ("run-1") must be terminalized —
        # cancellation was detected before a second AgentRun was ever created,
        # so no POST /agent-runs should have happened at all.
        posts = [p for (m, path, p) in calls if m == "POST" and path.endswith("/agent-runs")]
        self.assertEqual(posts, [])
        patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1/agent-runs/run-1"]
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["status"], "failed")

    def test_git_snapshot_uses_actual_execution_worktree_not_repo_root(self):
        # REPO_ROOT is always CommandPilot's own repo; a cross-repo work
        # order's adapter subprocess actually runs wherever the harness
        # process's cwd is (claude_code.py's Popen() sets no cwd=). The
        # safety check must snapshot THAT directory, not REPO_ROOT.
        sentinel = Path("/some/other/target-repo")
        seen_paths: list[Path] = []

        def fake_git_snapshot(path):
            seen_paths.append(path)
            return UNCHANGED

        adapter = FakeAdapter([RuntimeError("boom")])
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(harness, "_target_worktree", return_value=sentinel), \
             patch.object(harness, "log_line"), \
             patch.object(harness, "fetch_work_order", return_value={"status": "running"}), \
             patch.object(harness, "call_api", return_value={"id": "run-2"}), \
             patch.object(harness, "_git_snapshot", side_effect=fake_git_snapshot), \
             patch.object(harness, "cmd_import_result", return_value=0):
            harness._run_adapter_with_bounded_retry(_args(), adapter, _order(), Path(tmp), None, "run-1")

        self.assertTrue(seen_paths, "expected _git_snapshot to be called at least once")
        for p in seen_paths:
            self.assertEqual(p, sentinel)
        self.assertNotEqual(sentinel, harness.REPO_ROOT)

    def test_unreported_cost_conservatively_assumes_full_remaining_budget_spent(self):
        # cost_usd=None on a returned (non-exception) technical failure — the
        # harness must assume the WHOLE remaining budget was spent, so a
        # second attempt is refused rather than silently allowed to spend
        # up to total_budget AGAIN.
        outcome = ExecuteOutcome(exit_code=124, output_log_path=Path("log"), result=None, cost_usd=None)
        adapter = FakeAdapter([outcome])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"] * 5,
            git_snapshots=[UNCHANGED, UNCHANGED],
            total_budget=0.10,
        )
        self.assertEqual(len(adapter.execute_calls), 1)  # attempt 2 never started — budget already exhausted
        self.assertEqual(rc, 1)
        self.assertEqual(adapter.execute_calls[0], 0.10)  # attempt 1 got the full budget

        final_patch = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1"][-1]
        self.assertEqual(final_patch["reason"], "technical_failure_budget_exhausted")

    def test_reported_cost_correctly_decrements_cumulative_budget(self):
        # Each attempt reports an actual cost_usd — the next attempt's
        # remaining_budget must reflect real cumulative spend, not the full
        # total again, but also must not be refused early just because a
        # partial cost was reported.
        outcomes = [
            ExecuteOutcome(exit_code=124, output_log_path=Path("log"), result=None, cost_usd=0.05),
            ExecuteOutcome(exit_code=124, output_log_path=Path("log"), result=None, cost_usd=0.05),
            ExecuteOutcome(exit_code=124, output_log_path=Path("log"), result=None, cost_usd=0.05),
        ]
        adapter = FakeAdapter(outcomes)
        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=lambda *a, **k: {"id": "run-x"},
            status_sequence=["running"] * 10,
            git_snapshots=[UNCHANGED] * 6,
            total_budget=0.30,
        )
        self.assertEqual(len(adapter.execute_calls), 3)  # all 3 attempts fit well within budget
        self.assertEqual(adapter.execute_calls, [0.30, 0.25, 0.2])
        self.assertEqual(rc, 1)  # still fails after 3 attempts — max attempts reached, not budget


if __name__ == "__main__":
    unittest.main()
