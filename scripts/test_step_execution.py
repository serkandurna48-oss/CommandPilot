#!/usr/bin/env python3
"""Tests for the --per-step execution path:
scripts/run_work_order.py's _run_step_by_step() /
_run_one_step_with_bounded_retry() and their helpers
(_final_status_from_steps, _synthesize_review_package).

Same stdlib-only (unittest + unittest.mock) approach as
scripts/test_bounded_retry.py, which this file mirrors at step
granularity — adapter.execute_step(), call_api(), fetch_work_order(),
import_result(), and _git_snapshot() are all faked. Nothing here spawns a
real subprocess, hits a real API, or touches a real git repo.

Run:
    python scripts/test_step_execution.py
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
from runner_adapters.base import StepExecuteOutcome  # noqa: E402


class FakeStepAdapter:
    """A minimal RunnerAdapter stand-in whose execute_step() replays a
    pre-scripted sequence of outcomes/exceptions, one per call — same
    pattern as test_bounded_retry.py's FakeAdapter, at step granularity."""

    def __init__(self, results: list):
        self.info = argparse.Namespace(name="fake_step_adapter", supports_step_execution=True)
        self._results = list(results)
        self.calls: list[dict] = []

    def execute_step(self, order, step, prior_steps, session_path, max_budget_usd=None, progress=None):
        self.calls.append({
            "step_id": step["id"],
            "max_budget_usd": max_budget_usd,
            "prior_steps": [dict(p) for p in prior_steps],
        })
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _step_outcome(step_id: str, status: str, output_summary: str | None = None,
                   blocked_reason: str | None = None, cost_usd: float | None = None,
                   interrupted: bool = False) -> StepExecuteOutcome:
    step_result = None
    if not interrupted:
        step_entry = {"id": step_id, "status": status, "outputSummary": output_summary, "blockedReason": blocked_reason}
        step_result = {
            "workOrderId": "wo-1",
            "steps": [step_entry],
            "activityLogs": [],
            "artifacts": [],
        }
    return StepExecuteOutcome(
        exit_code=0, output_log_path=Path("log"), step_result=step_result,
        cost_usd=cost_usd, interrupted=interrupted,
    )


def _order(n_steps: int = 2) -> dict:
    roles = ["product", "architect", "coder", "qa", "reviewer", "reporter"]
    return {
        "id": "wo-1",
        "steps": [
            {"id": f"s{i + 1}", "order_index": i, "title": f"Step {i + 1}", "assigned_role": roles[i % len(roles)]}
            for i in range(n_steps)
        ],
        "time_limit_minutes": 90,
    }


def _args(**overrides):
    base = dict(
        work_order_id="wo-1", mode="execute", adapter="fake", api_url="http://localhost:8000",
        token="fake", force=False, result_file=None, runner_command=None, max_budget_usd=None,
        dry_run=False, per_step=True,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


UNCHANGED = ("sha-1", "")


class StepExecutionTests(unittest.TestCase):
    def _run(self, adapter, order, call_api_side_effect, status_sequence, git_snapshots,
              import_result_side_effect=lambda *a, **k: 0, total_budget=None, initial_agent_run_id="run-0"):
        status_iter = iter(status_sequence)
        git_iter = iter(git_snapshots)
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            with patch.object(harness, "log_line"), \
                 patch.object(harness, "fetch_work_order", side_effect=lambda *a, **k: {"status": next(status_iter)}), \
                 patch.object(harness, "call_api", side_effect=call_api_side_effect) as mock_call_api, \
                 patch.object(harness, "_git_snapshot", side_effect=lambda cwd: next(git_iter)), \
                 patch.object(harness, "import_result", side_effect=import_result_side_effect) as mock_import_result:
                rc = harness._run_step_by_step(
                    _args(), adapter, order, session_path, total_budget, initial_agent_run_id
                )
                return rc, mock_call_api, mock_import_result

    def test_technical_failure_on_one_step_does_not_rerun_earlier_steps(self):
        order = _order(2)
        adapter = FakeStepAdapter([
            _step_outcome("s1", "completed", "did step 1"),
            RuntimeError("boom 1"), RuntimeError("boom 2"), RuntimeError("boom 3"),
        ])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            if method == "POST" and path.endswith("/agent-runs"):
                return {"id": f"run-{len(calls)}"}
            return {}

        rc, mock_call_api, mock_import_result = self._run(
            adapter, order,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"] * 20,
            git_snapshots=[UNCHANGED] * 10,
        )

        # s1: exactly one execute_step call (never retried, even though s2
        # technically fails 3 times afterward).
        s1_calls = [c for c in adapter.calls if c["step_id"] == "s1"]
        s2_calls = [c for c in adapter.calls if c["step_id"] == "s2"]
        self.assertEqual(len(s1_calls), 1)
        self.assertEqual(len(s2_calls), 3)
        self.assertEqual(rc, 1)

        # s1's result was imported exactly once — proof the per-step
        # write-back happened immediately, not deferred/re-done during s2's
        # retries.
        self.assertEqual(mock_import_result.call_count, 1)
        imported_result = mock_import_result.call_args.args[0]
        self.assertEqual(imported_result["steps"][0]["id"], "s1")

    def test_cumulative_budget_across_steps(self):
        order = _order(3)
        adapter = FakeStepAdapter([
            _step_outcome("s1", "completed", cost_usd=0.10),
            _step_outcome("s2", "completed", cost_usd=0.10),
            _step_outcome("s3", "completed", cost_usd=0.10),
        ])

        rc, mock_call_api, mock_import_result = self._run(
            adapter, order,
            call_api_side_effect=lambda *a, **k: {"id": "run-x"},
            status_sequence=["running"] * 10,
            git_snapshots=[UNCHANGED] * 5,
            total_budget=0.30,
        )

        self.assertEqual(len(adapter.calls), 3)
        self.assertEqual([c["max_budget_usd"] for c in adapter.calls], [0.30, 0.20, 0.10])
        self.assertEqual(rc, 0)
        self.assertEqual(mock_import_result.call_count, 3)

    def test_interrupt_mid_step_marks_step_failed_and_stops(self):
        order = _order(2)
        adapter = FakeStepAdapter([_step_outcome("s1", "completed", interrupted=True)])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            if method == "POST" and path.endswith("/agent-runs"):
                return {"id": "run-1"}
            return {}

        rc, mock_call_api, mock_import_result = self._run(
            adapter, order,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"] * 5,
            git_snapshots=[UNCHANGED] * 5,
        )

        self.assertEqual(len(adapter.calls), 1)  # s2 never attempted
        self.assertEqual(rc, 0)
        mock_import_result.assert_not_called()

        # Two PATCHes are expected to the same step: the initial "running"
        # marker set before the attempt, then the interrupt's "failed"
        # marker — same two-PATCH pattern the whole-order path already has
        # (cmd_prompt_file()'s running-PATCH + _mark_running_step_interrupted()).
        step_patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1/steps/s1"]
        self.assertEqual([p["status"] for p in step_patches], ["running", "failed"])
        self.assertEqual(step_patches[-1]["blocked_reason"], "Vom Nutzer unterbrochen")

    def test_blocked_step_stops_loop_and_leaves_remaining_pending(self):
        order = _order(3)
        adapter = FakeStepAdapter([
            _step_outcome("s1", "completed", "ok"),
            _step_outcome("s2", "blocked", blocked_reason="needs approval"),
        ])
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            if method == "POST" and path.endswith("/agent-runs"):
                return {"id": "run-x"}
            return {}

        rc, mock_call_api, mock_import_result = self._run(
            adapter, order,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"] * 10,
            git_snapshots=[UNCHANGED] * 5,
        )

        # s3 never even attempted — loop stopped right after s2's 'blocked'.
        self.assertEqual([c["step_id"] for c in adapter.calls], ["s1", "s2"])
        self.assertEqual(rc, 0)  # writes succeeded even though the semantic outcome is 'blocked'

        # No PATCH was ever sent for s3 — it stays at whatever status it
        # already had (pending), never touched by the harness.
        s3_patches = [p for (m, path, p) in calls if path == "/api/work-orders/wo-1/steps/s3"]
        self.assertEqual(s3_patches, [])

        # Finalize wrote a 'blocked' work-order status, deterministically
        # derived from s2's reported outcome.
        wo_patches = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1"]
        self.assertEqual(len(wo_patches), 1)
        self.assertEqual(wo_patches[0]["status"], "blocked")

        review_puts = [p for (m, path, p) in calls if m == "PUT" and path == "/api/work-orders/wo-1/review-package"]
        self.assertEqual(len(review_puts), 1)
        self.assertEqual(review_puts[0]["verdict"], "blocked")

    def test_prior_steps_context_passed_forward(self):
        order = _order(2)
        adapter = FakeStepAdapter([
            _step_outcome("s1", "completed", "wrote the plan"),
            _step_outcome("s2", "completed", "implemented it"),
        ])

        self._run(
            adapter, order,
            call_api_side_effect=lambda *a, **k: {"id": "run-x"},
            status_sequence=["running"] * 10,
            git_snapshots=[UNCHANGED] * 5,
        )

        self.assertEqual(adapter.calls[0]["prior_steps"], [])
        self.assertEqual(len(adapter.calls[1]["prior_steps"]), 1)
        self.assertEqual(adapter.calls[1]["prior_steps"][0]["id"], "s1")
        self.assertEqual(adapter.calls[1]["prior_steps"][0]["outputSummary"], "wrote the plan")


class FinalStatusHelpersTests(unittest.TestCase):
    def test_final_status_prefers_failed_over_blocked(self):
        steps = [{"status": "completed"}, {"status": "blocked"}, {"status": "failed"}]
        self.assertEqual(harness._final_status_from_steps(steps), "failed")

    def test_final_status_blocked_without_failed(self):
        steps = [{"status": "completed"}, {"status": "blocked"}]
        self.assertEqual(harness._final_status_from_steps(steps), "blocked")

    def test_final_status_review_ready_when_all_clean(self):
        steps = [{"status": "completed"}, {"status": "skipped"}]
        self.assertEqual(harness._final_status_from_steps(steps), "review_ready")

    def test_synthesize_review_package_never_invents_files_or_tests(self):
        steps = [{"title": "S1", "status": "completed", "outputSummary": "did it"}]
        rp = harness._synthesize_review_package(steps)
        self.assertEqual(rp["filesChanged"], [])
        self.assertEqual(rp["testsRun"], [])
        self.assertEqual(rp["verdict"], "ready_for_review")


if __name__ == "__main__":
    unittest.main()
