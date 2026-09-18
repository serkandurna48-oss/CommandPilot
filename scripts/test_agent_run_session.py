#!/usr/bin/env python3
"""Tests for the AgentRun lifecycle wiring (OP-Runner-Session-001):
- run_work_order.py's agent_run.json session-state round trip
  (write_agent_run_state / read_agent_run_id).
- import_work_order_result.py's agent_run_id handling: activityLogs
  backfill, and the final AgentRun status PATCH.

Stdlib-only (unittest + unittest.mock + tempfile), consistent with the
zero-third-party-dependency stance of the scripts it tests.

Run:
    python scripts/test_agent_run_session.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_work_order_result as importer  # noqa: E402
import run_work_order as harness  # noqa: E402


def _valid_result(**overrides):
    base = {
        "workOrderId": "wo-1",
        "finalStatus": "review_ready",
        "steps": [
            {"id": "s1", "status": "completed", "outputSummary": "done", "blockedReason": None},
        ],
        "activityLogs": [
            {"level": "info", "eventType": "run_completed", "message": "ok", "agentRunId": None},
        ],
        "artifacts": [{"type": "summary", "title": "Summary", "content": "..."}],
        "reviewPackage": {
            "summary": "Did the thing.",
            "filesChanged": [], "testsRun": [], "risks": [], "openQuestions": [],
            "needsHumanReview": True, "recommendedNextStep": "review it",
            "verdict": "ready_for_review",
        },
    }
    base.update(overrides)
    return base


def _order_for(result):
    return {"id": result["workOrderId"], "steps": [{"id": s["id"]} for s in result["steps"]]}


class CmdPromptFileAgentRunTests(unittest.TestCase):
    """Covers cmd_prompt_file()'s AgentRun-creation block directly — the
    part that a live run against a real backend exposed a gap in: it
    reproduces the exact "POST succeeds, response has no usable id" case
    that previously failed completely silently (no log line, no state
    file, no error) during an actual OP-Runner-Session-001 test run."""

    def _order(self):
        return {
            "id": "wo-1", "title": "Test WO", "status": "queued", "time_limit_minutes": 90,
            "steps": [{"id": "s1", "title": "Product Agent", "assigned_role": "product"}],
            "approval_scope": {"blocked_actions": ["deploy"], "allowed_actions": [], "requires_approval": []},
        }

    def _args(self, **overrides):
        import argparse
        base = dict(
            work_order_id="wo-1", mode="prompt-file", adapter="manual_prompt",
            api_url="http://localhost:8000", token="fake", force=False,
            result_file=None, runner_command=None, max_budget_usd=None, dry_run=False,
        )
        base.update(overrides)
        return argparse.Namespace(**base)

    def _run(self, session_path, call_api_side_effect):
        adapter = harness.get_adapter("manual_prompt")
        with patch.object(harness, "session_dir", return_value=session_path), \
             patch.object(harness, "fetch_work_order", return_value=self._order()), \
             patch.object(harness, "call_api", side_effect=call_api_side_effect), \
             patch.object(adapter, "prepare", return_value=session_path / "prompt.md"):
            return harness.cmd_prompt_file(self._args(), adapter)

    def test_successful_creation_writes_state_file(self):
        def side_effect(api_url, token, method, path, payload, dry_run):
            if method == "POST" and path.endswith("/agent-runs"):
                return {"id": "run-xyz", "role": "product", "status": "running"}
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            rc = self._run(session_path, side_effect)
            self.assertEqual(rc, 0)
            self.assertEqual(harness.read_agent_run_id(session_path), "run-xyz")

    def test_id_less_response_does_not_crash_and_is_logged(self):
        # Reproduces the exact live failure mode: the POST returns 2xx (no
        # exception) but the body has no "id" — e.g. an unexpectedly empty
        # response. Must not silently do nothing.
        def side_effect(api_url, token, method, path, payload, dry_run):
            if method == "POST" and path.endswith("/agent-runs"):
                return {}
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            rc = self._run(session_path, side_effect)
            self.assertEqual(rc, 0)  # non-fatal — the rest of prompt-file mode still completes
            self.assertIsNone(harness.read_agent_run_id(session_path))
            log_text = (session_path / "run.log").read_text(encoding="utf-8")
            self.assertIn("WARNUNG: AgentRun-Antwort enthielt keine 'id'", log_text)

    def test_agent_run_post_failure_does_not_abort_prompt_file_mode(self):
        def side_effect(api_url, token, method, path, payload, dry_run):
            if method == "POST" and path.endswith("/agent-runs"):
                raise importer.ImportError_("simulated 500")
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            rc = self._run(session_path, side_effect)
            self.assertEqual(rc, 0)  # best-effort, matches the first-step PATCH's existing behavior
            self.assertIsNone(harness.read_agent_run_id(session_path))
            log_text = (session_path / "run.log").read_text(encoding="utf-8")
            self.assertIn("WARNUNG: konnte AgentRun nicht anlegen", log_text)


class AgentRunStateFileTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            harness.write_agent_run_state(session_path, "run-123", "claude_code", "prompt-file")
            self.assertEqual(harness.read_agent_run_id(session_path), "run-123")

    def test_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(harness.read_agent_run_id(Path(tmp)))

    def test_corrupt_file_returns_none_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            (session_path / harness._AGENT_RUN_STATE_FILENAME).write_text("{not json", encoding="utf-8")
            self.assertIsNone(harness.read_agent_run_id(session_path))


class AgentRunUpdatePayloadTests(unittest.TestCase):
    def test_basic(self):
        payload = importer.agent_run_update_payload("completed", "all good")
        self.assertEqual(payload, {"status": "completed", "output_summary": "all good"})

    def test_no_summary(self):
        payload = importer.agent_run_update_payload("failed", None)
        self.assertEqual(payload, {"status": "failed"})

    def test_summary_truncated_to_2000_chars(self):
        payload = importer.agent_run_update_payload("completed", "x" * 3000)
        self.assertEqual(len(payload["output_summary"]), 2000)


class ImportResultAgentRunTests(unittest.TestCase):
    def _run(self, result, agent_run_id, call_api_side_effect=None):
        side_effect = call_api_side_effect or (lambda *a, **kw: {})
        with patch.object(importer, "fetch_work_order", return_value=_order_for(result)), \
             patch.object(importer, "call_api", side_effect=side_effect) as mock_call:
            exit_code = importer.import_result(
                result, "http://localhost:8000", "fake-token", dry_run=False, agent_run_id=agent_run_id,
            )
        return exit_code, mock_call

    def _agent_run_calls(self, mock_call, work_order_id, agent_run_id):
        return [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{work_order_id}/agent-runs/{agent_run_id}"
        ]

    def test_no_agent_run_id_means_no_agent_run_call(self):
        result = _valid_result()
        exit_code, mock_call = self._run(result, agent_run_id=None)
        self.assertEqual(exit_code, 0)
        agent_run_calls = [c for c in mock_call.call_args_list if "/agent-runs/" in c.args[3]]
        self.assertEqual(agent_run_calls, [], "no agent_run_id provided -> must not touch the agent-runs endpoint")

    def test_review_ready_success_completes_agent_run(self):
        result = _valid_result()
        exit_code, mock_call = self._run(result, agent_run_id="run-1")
        self.assertEqual(exit_code, 0)
        calls = self._agent_run_calls(mock_call, "wo-1", "run-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[4]["status"], "completed")
        self.assertEqual(calls[0].args[4].get("output_summary"), "Did the thing.")

    def test_requested_blocked_marks_agent_run_blocked(self):
        result = _valid_result(
            finalStatus="blocked",
            steps=[{"id": "s1", "status": "blocked", "outputSummary": None, "blockedReason": "needs approval"}],
        )
        exit_code, mock_call = self._run(result, agent_run_id="run-1")
        calls = self._agent_run_calls(mock_call, "wo-1", "run-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[4]["status"], "blocked")

    def test_requested_failed_marks_agent_run_failed(self):
        result = _valid_result(finalStatus="failed")
        exit_code, mock_call = self._run(result, agent_run_id="run-1")
        calls = self._agent_run_calls(mock_call, "wo-1", "run-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[4]["status"], "failed")

    def test_atomic_gate_blocking_review_ready_marks_agent_run_failed_not_completed(self):
        # A review_ready request that OP-Import-Integrity-001's gate refuses
        # (because a step write failed) must be recorded honestly — the run
        # did not actually complete, regardless of what it asked for.
        result = _valid_result()

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/steps/" in path:
                raise importer.ImportError_("simulated step failure")
            return {}

        exit_code, mock_call = self._run(result, agent_run_id="run-1", call_api_side_effect=side_effect)
        self.assertEqual(exit_code, 1)
        calls = self._agent_run_calls(mock_call, "wo-1", "run-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[4]["status"], "failed")
        self.assertIn("blocked", calls[0].args[4]["output_summary"])

    def test_activity_log_backfilled_with_agent_run_id(self):
        result = _valid_result()
        exit_code, mock_call = self._run(result, agent_run_id="run-1")
        log_calls = [c for c in mock_call.call_args_list if c.args[3] == "/api/work-orders/wo-1/activity-log"]
        self.assertEqual(len(log_calls), 1)
        self.assertEqual(log_calls[0].args[4].get("agent_run_id"), "run-1")

    def test_activity_log_runner_supplied_agent_run_id_is_overridden_by_the_harness_one(self):
        # A runner is never told the real AgentRun UUID, so an agentRunId
        # it fills in itself is unverified — the harness's own known
        # agent_run_id always wins now (see scripts/test_import_result_integrity.py::
        # ActivityLogAgentRunIdMixupTests for the full rationale/regression
        # this pins: a step id landing here used to fail a foreign key and
        # silently drop the log entry).
        result = _valid_result(activityLogs=[
            {"level": "info", "eventType": "run_completed", "message": "ok", "agentRunId": "other-run"},
        ])
        exit_code, mock_call = self._run(result, agent_run_id="run-1")
        log_calls = [c for c in mock_call.call_args_list if c.args[3] == "/api/work-orders/wo-1/activity-log"]
        self.assertEqual(log_calls[0].args[4].get("agent_run_id"), "run-1")

    def test_agent_run_patch_failure_does_not_crash_or_change_exit_code_meaning(self):
        result = _valid_result()

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/agent-runs/" in path:
                raise importer.ImportError_("simulated agent-run patch failure")
            return {}

        exit_code, mock_call = self._run(result, agent_run_id="run-1", call_api_side_effect=side_effect)
        self.assertEqual(exit_code, 1)  # still surfaced as a real failure


if __name__ == "__main__":
    unittest.main()
