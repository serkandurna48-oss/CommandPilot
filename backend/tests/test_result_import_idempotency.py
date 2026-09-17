#!/usr/bin/env python3
"""Tests for the CP-OP03 idempotent result-import writes:
backend/app/services/work_order_service.py's append_activity_log() and
create_artifact(), which upsert on (work_order_id, dedup_key) instead of
plain-inserting (see supabase/migrations/012_result_import_dedup_keys.sql).

Stdlib-only (unittest + unittest.mock) — no dependency install, same
convention as backend/tests/test_work_order_transitions.py and
scripts/test_*.py. The Supabase client is faked entirely.

Run:
    python backend/tests/test_result_import_idempotency.py
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

from app.models.work_order import ActivityLogCreate, ArtifactCreate  # noqa: E402
from app.services import work_order_service  # noqa: E402


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeUpsertTable:
    """Fakes db.table(name).upsert(payload, on_conflict=...).execute() —
    records every upsert call and returns a canned single-row result."""

    def __init__(self, row: dict):
        self._row = row
        self.upsert_calls: list[tuple[dict, str | None]] = []

    def upsert(self, payload: dict, on_conflict: str | None = None):
        self.upsert_calls.append((payload, on_conflict))
        return self

    def execute(self):
        return FakeResult([self._row])


class FakeDB:
    def __init__(self, table_obj):
        self._table_obj = table_obj

    def table(self, _name: str):
        return self._table_obj


class AppendActivityLogIdempotencyTests(unittest.TestCase):
    def test_upserts_on_work_order_id_and_dedup_key_when_set(self):
        fake_table = FakeUpsertTable({"id": "log-1", "work_order_id": "wo-1", "dedup_key": "abc123"})
        data = ActivityLogCreate(level="info", event_type="x", message="y", dedup_key="abc123")
        with patch.object(work_order_service, "get_db", return_value=FakeDB(fake_table)):
            result = work_order_service.append_activity_log("wo-1", data)

        self.assertEqual(result["id"], "log-1")
        self.assertEqual(len(fake_table.upsert_calls), 1)
        payload, on_conflict = fake_table.upsert_calls[0]
        self.assertEqual(on_conflict, "work_order_id,dedup_key")
        self.assertEqual(payload["dedup_key"], "abc123")
        self.assertEqual(payload["work_order_id"], "wo-1")

    def test_still_uses_upsert_when_dedup_key_is_none(self):
        # Postgres never treats two NULLs as equal for uniqueness purposes,
        # so an upsert with dedup_key=None can never match an existing row
        # — it behaves exactly like a plain insert. Every non-import caller
        # (e.g. the harness's own "runner_started" log) relies on this.
        fake_table = FakeUpsertTable({"id": "log-2", "dedup_key": None})
        data = ActivityLogCreate(level="info", event_type="x", message="y")
        with patch.object(work_order_service, "get_db", return_value=FakeDB(fake_table)):
            work_order_service.append_activity_log("wo-1", data)

        payload, on_conflict = fake_table.upsert_calls[0]
        self.assertIsNone(payload["dedup_key"])
        self.assertEqual(on_conflict, "work_order_id,dedup_key")


class CreateArtifactIdempotencyTests(unittest.TestCase):
    def test_upserts_on_work_order_id_and_dedup_key_when_set(self):
        fake_table = FakeUpsertTable({"id": "art-1", "dedup_key": "xyz789"})
        data = ArtifactCreate(type="summary", title="T", dedup_key="xyz789")
        with patch.object(work_order_service, "get_db", return_value=FakeDB(fake_table)):
            result = work_order_service.create_artifact("wo-1", data)

        self.assertEqual(result["id"], "art-1")
        payload, on_conflict = fake_table.upsert_calls[0]
        self.assertEqual(on_conflict, "work_order_id,dedup_key")
        self.assertEqual(payload["dedup_key"], "xyz789")

    def test_still_uses_upsert_when_dedup_key_is_none(self):
        fake_table = FakeUpsertTable({"id": "art-2", "dedup_key": None})
        data = ArtifactCreate(type="summary", title="T")
        with patch.object(work_order_service, "get_db", return_value=FakeDB(fake_table)):
            work_order_service.create_artifact("wo-1", data)

        payload, on_conflict = fake_table.upsert_calls[0]
        self.assertIsNone(payload["dedup_key"])
        self.assertEqual(on_conflict, "work_order_id,dedup_key")


if __name__ == "__main__":
    unittest.main()
