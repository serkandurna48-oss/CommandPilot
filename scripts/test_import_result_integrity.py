#!/usr/bin/env python3
"""Tests for the atomic/fail-fast guarantees added to the result-import
path (OP-Import-Integrity-001): scripts/import_work_order_result.py and
scripts/runner_adapters/base.py's parse_and_validate_result() /
validate_result_against_order().

Stdlib-only (unittest + unittest.mock) — no dependency install, consistent
with import_work_order_result.py's own zero-third-party-dependency stance.

Run:
    python scripts/test_import_result_integrity.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_work_order_result as importer  # noqa: E402
from runner_adapters.base import (  # noqa: E402
    parse_and_validate_result,
    validate_result_against_order,
)


def _valid_result(**overrides):
    base = {
        "workOrderId": "wo-1",
        "finalStatus": "review_ready",
        "steps": [
            {"id": "s1", "status": "completed", "outputSummary": "done", "blockedReason": None},
            {"id": "s2", "status": "completed", "outputSummary": "done", "blockedReason": None},
        ],
        "activityLogs": [{"level": "info", "eventType": "run_completed", "message": "ok", "agentRunId": None}],
        "artifacts": [{"type": "summary", "title": "Summary", "content": "..."}],
        "reviewPackage": {
            "summary": "Did the thing.",
            "filesChanged": [],
            "testsRun": [],
            "risks": [],
            "openQuestions": [],
            "needsHumanReview": True,
            "recommendedNextStep": "review it",
            "verdict": "ready_for_review",
        },
    }
    base.update(overrides)
    return base


def _order_for(result):
    return {"id": result["workOrderId"], "steps": [{"id": s["id"]} for s in result["steps"]]}


class ParseAndValidateResultTests(unittest.TestCase):
    def test_valid_result_passes(self):
        import json
        data = parse_and_validate_result(json.dumps(_valid_result()), "test")
        self.assertEqual(data["finalStatus"], "review_ready")

    def test_review_ready_with_zero_progress_rejected(self):
        import json
        result = _valid_result(steps=[
            {"id": "s1", "status": "blocked", "outputSummary": None, "blockedReason": "needs approval"},
        ])
        with self.assertRaises(ValueError) as ctx:
            parse_and_validate_result(json.dumps(result), "test")
        self.assertIn("progress would be 0%", str(ctx.exception))

    def test_review_ready_with_missing_review_package_summary_rejected(self):
        import json
        result = _valid_result()
        result["reviewPackage"]["summary"] = ""
        with self.assertRaises(ValueError) as ctx:
            parse_and_validate_result(json.dumps(result), "test")
        self.assertIn("reviewPackage.summary", str(ctx.exception))

    def test_invalid_step_status_rejected(self):
        import json
        result = _valid_result(steps=[{"id": "s1", "status": "done", "outputSummary": None, "blockedReason": None}])
        with self.assertRaises(ValueError) as ctx:
            parse_and_validate_result(json.dumps(result), "test")
        self.assertIn("steps[0].status", str(ctx.exception))

    def test_blocked_status_without_reason_rejected(self):
        import json
        result = _valid_result(
            finalStatus="blocked",
            steps=[{"id": "s1", "status": "blocked", "outputSummary": None, "blockedReason": None}],
        )
        with self.assertRaises(ValueError) as ctx:
            parse_and_validate_result(json.dumps(result), "test")
        self.assertIn("no blockedReason", str(ctx.exception))

    def test_blocked_final_status_with_zero_progress_is_allowed(self):
        # The 0%-progress rule is specific to review_ready — a genuinely
        # blocked run legitimately has no completed steps yet.
        import json
        result = _valid_result(
            finalStatus="blocked",
            steps=[{"id": "s1", "status": "blocked", "outputSummary": None, "blockedReason": "needs approval"}],
        )
        data = parse_and_validate_result(json.dumps(result), "test")
        self.assertEqual(data["finalStatus"], "blocked")

    def test_order_independent_checks_do_not_need_an_order_object(self):
        # Regression guard: these checks must run even when the live work
        # order can't be fetched, so they must not require `order` at all.
        import inspect
        params = inspect.signature(parse_and_validate_result).parameters
        self.assertNotIn("order", params)


class ValidateResultAgainstOrderTests(unittest.TestCase):
    def test_missing_step_update_rejected(self):
        result = _valid_result()
        order = _order_for(result)
        order["steps"].append({"id": "s3"})  # order has a step the result never mentions
        with self.assertRaises(ValueError) as ctx:
            validate_result_against_order(result, order, "test")
        self.assertIn("s3", str(ctx.exception))

    def test_unknown_step_id_rejected(self):
        result = _valid_result()
        order = _order_for(result)
        result["steps"][0]["id"] = "not-a-real-step"
        with self.assertRaises(ValueError):
            validate_result_against_order(result, order, "test")

    def test_complete_match_passes(self):
        result = _valid_result()
        order = _order_for(result)
        validate_result_against_order(result, order, "test")  # must not raise


class ImportResultAtomicGateTests(unittest.TestCase):
    """Exercises import_result() itself with call_api mocked out, so no
    network/backend is required — the gate under test is purely
    control-flow (does a failure anywhere prevent the finalStatus PATCH)."""

    def _run(self, result, call_api_side_effect):
        with patch.object(importer, "fetch_work_order", return_value=_order_for(result)), \
             patch.object(importer, "call_api", side_effect=call_api_side_effect) as mock_call:
            exit_code = importer.import_result(result, "http://localhost:8000", "fake-token", dry_run=False)
        return exit_code, mock_call

    def test_step_write_failure_blocks_review_ready(self):
        result = _valid_result()

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/steps/" in path:
                raise importer.ImportError_("simulated step failure")
            return {}

        exit_code, mock_call = self._run(result, side_effect)
        self.assertEqual(exit_code, 1)
        final_status_calls = [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{result['workOrderId']}"
        ]
        self.assertEqual(final_status_calls, [], "finalStatus must not be PATCHed when a step write failed")

    def test_artifact_write_failure_blocks_review_ready(self):
        result = _valid_result()

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/artifacts" in path:
                raise importer.ImportError_("simulated artifact failure")
            return {}

        exit_code, mock_call = self._run(result, side_effect)
        self.assertEqual(exit_code, 1)
        final_status_calls = [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{result['workOrderId']}"
        ]
        self.assertEqual(final_status_calls, [])

    def test_review_package_write_failure_blocks_review_ready(self):
        result = _valid_result()

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/review-package" in path:
                raise importer.ImportError_("simulated review-package failure")
            return {}

        exit_code, mock_call = self._run(result, side_effect)
        self.assertEqual(exit_code, 1)
        final_status_calls = [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{result['workOrderId']}"
        ]
        self.assertEqual(final_status_calls, [])

    def test_activity_log_failure_does_not_block_review_ready(self):
        # Logs are supplementary telemetry, not one of the gated categories.
        result = _valid_result()

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/activity-log" in path:
                raise importer.ImportError_("simulated log failure")
            return {}

        exit_code, mock_call = self._run(result, side_effect)
        self.assertEqual(exit_code, 1)  # still a nonzero exit — the failure is real
        final_status_calls = [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{result['workOrderId']}"
        ]
        self.assertEqual(len(final_status_calls), 1, "review_ready must still be set when only a log write failed")

    def test_fully_successful_import_sets_review_ready(self):
        result = _valid_result()
        exit_code, mock_call = self._run(result, lambda *a, **kw: {})
        self.assertEqual(exit_code, 0)
        final_status_calls = [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{result['workOrderId']}"
        ]
        self.assertEqual(len(final_status_calls), 1)

    def test_blocked_final_status_is_set_even_with_step_failures(self):
        # The gate is specific to review_ready — blocked/failed already
        # tell the reader something is wrong, so they're written as-is.
        result = _valid_result(
            finalStatus="blocked",
            steps=[{"id": "s1", "status": "blocked", "outputSummary": None, "blockedReason": "needs approval"},
                   {"id": "s2", "status": "blocked", "outputSummary": None, "blockedReason": "needs approval"}],
        )

        def side_effect(api_url, token, method, path, payload, dry_run):
            if "/steps/" in path:
                raise importer.ImportError_("simulated step failure")
            return {}

        exit_code, mock_call = self._run(result, side_effect)
        self.assertEqual(exit_code, 1)  # the step failure itself is still a real failure
        final_status_calls = [
            c for c in mock_call.call_args_list
            if c.args[2] == "PATCH" and c.args[3] == f"/api/work-orders/{result['workOrderId']}"
        ]
        self.assertEqual(len(final_status_calls), 1, "a non-review_ready status is written regardless of step failures")


if __name__ == "__main__":
    unittest.main()
