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
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_work_order as harness  # noqa: E402
from runner_adapters.base import (  # noqa: E402
    ExecuteOutcome,
    ProgressReporter,
    build_runner_prompt,
    build_step_prompt,
)


# A complete, parse_and_validate_result()-valid whole-order result — reused by
# the R3 "fresh result.json fallback" tests.
VALID_RESULT = {
    "workOrderId": "wo-1",
    "finalStatus": "review_ready",
    "steps": [{"id": "s1", "status": "completed", "outputSummary": "did it", "blockedReason": None}],
    "activityLogs": [],
    "artifacts": [],
    "reviewPackage": {
        "summary": "Done.", "filesChanged": [], "testsRun": [], "risks": [],
        "openQuestions": [], "needsHumanReview": True, "recommendedNextStep": "merge",
        "verdict": "ready_for_review",
    },
}


class FakeAdapter:
    """A minimal RunnerAdapter stand-in whose execute() replays a
    pre-scripted sequence of outcomes/exceptions, one per call.

    writes_result (R3): if set, execute() writes it as result.json into the
    session folder and bumps its mtime into the future — emulating an executor
    that saved result.json itself even though the adapter returned no stdout
    result. The future mtime makes it unambiguously "written during this
    attempt" for _load_fresh_result_file()'s freshness check."""

    def __init__(self, results: list, writes_result: dict | None = None):
        self.info = argparse.Namespace(name="fake_adapter")
        self._results = list(results)
        self._writes_result = writes_result
        self.execute_calls: list[float | None] = []

    def execute(self, order, session_path, runner_command, max_budget_usd=None, progress=None):
        self.execute_calls.append(max_budget_usd)
        self.progress_seen = progress
        if self._writes_result is not None:
            p = Path(session_path) / "result.json"
            p.write_text(json.dumps(self._writes_result), encoding="utf-8")
            future = time.time() + 10
            os.utime(p, (future, future))
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

    def test_exit0_fresh_result_json_is_imported_not_retried(self):
        # R3 finding A / criterion 1: exit_code 0, no stdout result
        # (outcome.result is None), but the executor wrote a FRESH result.json
        # into the session folder. The harness must import it and NOT retry.
        outcome = ExecuteOutcome(exit_code=0, output_log_path=Path("log"), result=None)
        adapter = FakeAdapter([outcome], writes_result=VALID_RESULT)
        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=lambda *a, **k: {},
            status_sequence=["running", "running"],  # top-of-loop, then pre-import cancel check
            git_snapshots=[UNCHANGED],
        )
        self.assertEqual(len(adapter.execute_calls), 1)  # no retry
        mock_import.assert_called_once()
        self.assertEqual(rc, 0)

    def test_exit0_no_result_anywhere_fails_result_missing_without_retry(self):
        # R3 finding A / criterion 2: exit_code 0, no stdout result, no fresh
        # result.json either → failed with reason 'result_missing', no retry.
        outcome = ExecuteOutcome(exit_code=0, output_log_path=Path("log"), result=None)
        adapter = FakeAdapter([outcome])  # writes nothing
        calls = []

        def call_api_side_effect(api_url, token, method, path, payload, dry_run):
            calls.append((method, path, payload))
            return {}

        rc, mock_import = self._run(
            adapter,
            call_api_side_effect=call_api_side_effect,
            status_sequence=["running"],
            git_snapshots=[UNCHANGED],
        )
        self.assertEqual(len(adapter.execute_calls), 1)  # NOT retried
        self.assertEqual(rc, 1)
        mock_import.assert_not_called()
        final_patch = [p for (m, path, p) in calls if m == "PATCH" and path == "/api/work-orders/wo-1"][-1]
        self.assertEqual(final_patch["status"], "failed")
        self.assertEqual(final_patch["reason"], "result_missing")

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


class LoadFreshResultFileTests(unittest.TestCase):
    """R3 finding A / criterion 3: a result.json from before this attempt
    (stale) must be ignored; only one written during the attempt counts."""

    def test_stale_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "result.json"
            p.write_text(json.dumps(VALID_RESULT), encoding="utf-8")
            old = time.time() - 1000
            os.utime(p, (old, old))  # written long before the attempt
            result = harness._load_fresh_result_file(p, time.time(), harness.parse_and_validate_result)
            self.assertIsNone(result)

    def test_fresh_file_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "result.json"
            p.write_text(json.dumps(VALID_RESULT), encoding="utf-8")
            # attempt "started" well in the past → the file counts as fresh
            result = harness._load_fresh_result_file(p, time.time() - 1000, harness.parse_and_validate_result)
            self.assertIsNotNone(result)
            self.assertEqual(result["finalStatus"], "review_ready")

    def test_absent_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = harness._load_fresh_result_file(
                Path(tmp) / "nope.json", time.time() - 1000, harness.parse_and_validate_result
            )
            self.assertIsNone(result)

    def test_fresh_but_invalid_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "result.json"
            p.write_text("{ not valid json", encoding="utf-8")
            result = harness._load_fresh_result_file(
                p, time.time() - 1000, harness.parse_and_validate_result
            )
            self.assertIsNone(result)


class WorktreeChangeDetectionTests(unittest.TestCase):
    """R3 finding B / criterion 5: a new git worktree created during an
    attempt must be seen as a change (no auto-retry)."""

    def test_worktree_component_difference_counts_as_changed(self):
        before = ("sha", "status", "worktree /a\nHEAD abc\n")
        after = ("sha", "status", "worktree /a\nHEAD abc\n\nworktree /a/.claude/worktrees/x\nHEAD def\n")
        self.assertTrue(harness._worktree_changed(before, after))
        self.assertFalse(harness._worktree_changed(before, before))

    def test_git_snapshot_detects_new_worktree_in_real_repo(self):
        import shutil
        import subprocess

        if shutil.which("git") is None:
            self.skipTest("git not available")

        tmp = tempfile.mkdtemp()
        try:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            def git(*a):
                return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)

            git("init")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            (repo / "f.txt").write_text("hi\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-m", "base")

            before = harness._git_snapshot(repo)
            self.assertIsNotNone(before)

            wt = Path(tmp) / "wt"
            r = git("worktree", "add", "--detach", str(wt))
            self.assertEqual(r.returncode, 0, r.stderr)

            after = harness._git_snapshot(repo)
            self.assertIsNotNone(after)
            # HEAD and working-tree status are unchanged by `worktree add`;
            # the ONLY difference is the worktree list — which is exactly what
            # must now flip _worktree_changed to True.
            self.assertEqual(before[0], after[0])
            self.assertEqual(before[1], after[1])
            self.assertNotEqual(before[2], after[2])
            self.assertTrue(harness._worktree_changed(before, after))

            git("worktree", "remove", "--force", str(wt))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _full_order() -> dict:
    return {
        "id": "wo-1", "title": "T", "goal": "G", "repo": "commandpilot",
        "time_limit_minutes": 90, "acceptance_criteria": ["crit"],
        "approval_scope": {
            "allowed_actions": [], "requires_approval": [], "blocked_actions": ["x"],
            "max_runtime_minutes": 90,
        },
        "steps": [{"id": "s1", "order_index": 0, "title": "Step 1", "assigned_role": "coder"}],
    }


class PromptModeTests(unittest.TestCase):
    """R3 finding B / criterion 4: the --mode execute prompt forbids a
    self-created worktree and drops the manual import hint; prompt-file mode
    is unchanged."""

    def test_execute_prompt_forbids_worktree_and_drops_import_hint(self):
        p = build_runner_prompt(_full_order(), execute_mode=True)
        self.assertIn("KEINEN eigenen Worktree", p)
        self.assertNotIn("importiere es mit", p)

    def test_prompt_file_mode_unchanged(self):
        p = build_runner_prompt(_full_order())  # execute_mode defaults to False
        self.assertIn("importiere es mit", p)
        self.assertNotIn("KEINEN eigenen Worktree", p)

    def test_step_prompt_forbids_worktree(self):
        order = _full_order()
        p = build_step_prompt(order, order["steps"][0], [])
        self.assertIn("KEINEN eigenen Worktree", p)


if __name__ == "__main__":
    unittest.main()
