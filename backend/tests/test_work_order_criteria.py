#!/usr/bin/env python3
"""R1 tests: WorkOrderCreate requires at least one non-empty acceptance
criterion (see backend/app/models/work_order.py's _require_acceptance_criteria
validator), while WorkOrderStepCreate deliberately keeps criteria optional.

Stdlib-only (unittest), same posture as the sibling test_work_order_*.py
files — the Supabase client is never touched here, these are pure model
validation tests.

Run:
    python backend/tests/test_work_order_criteria.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from pydantic import ValidationError  # noqa: E402

from app.models.work_order import (  # noqa: E402
    ApprovalScopeCreate,
    WorkOrderCreate,
    WorkOrderStepCreate,
)


def _scope() -> ApprovalScopeCreate:
    return ApprovalScopeCreate(max_runtime_minutes=90)


def _make(criteria):
    return WorkOrderCreate(
        title="Test Work Order",
        goal="Irgendetwas Sinnvolles tun",
        acceptance_criteria=criteria,
        approval_scope=_scope(),
    )


class WorkOrderCreateCriteriaTests(unittest.TestCase):
    def test_missing_criteria_is_rejected(self):
        # Field omitted entirely → default [] → must fail.
        with self.assertRaises(ValidationError):
            WorkOrderCreate(title="t", goal="g", approval_scope=_scope())

    def test_empty_list_is_rejected(self):
        with self.assertRaises(ValidationError):
            _make([])

    def test_single_blank_string_is_rejected(self):
        with self.assertRaises(ValidationError):
            _make(["   "])

    def test_all_blank_strings_is_rejected(self):
        with self.assertRaises(ValidationError):
            _make(["", "  ", "\t"])

    def test_one_real_criterion_is_accepted(self):
        order = _make(["Die Seite /foo lädt ohne Fehler"])
        self.assertEqual(order.acceptance_criteria, ["Die Seite /foo lädt ohne Fehler"])

    def test_multiple_criteria_accepted(self):
        order = _make(["Kriterium A", "Kriterium B"])
        self.assertEqual(len(order.acceptance_criteria), 2)


class WorkOrderStepCreateCriteriaTests(unittest.TestCase):
    def test_step_criteria_stay_optional(self):
        # The mandate is for the whole work order, NOT for individual steps.
        step = WorkOrderStepCreate(title="Step 1", assigned_role="coder")
        self.assertEqual(step.acceptance_criteria, [])


if __name__ == "__main__":
    unittest.main()
