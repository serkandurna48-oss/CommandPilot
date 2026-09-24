"""
Tests for app/services/runner_connection_service.py and app/auth.py's
runner-token acceptance (23.09.2026 — guided pairing replaces copying a
Supabase session token out of browser DevTools for the local runner).

In-memory fake Supabase table, same posture as test_suggested_action_service.py
— no real DB, no real network.

Run:
    python -m pytest backend/tests/test_runner_connection_service.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.services import runner_connection_service as svc  # noqa: E402
from app import auth  # noqa: E402


# ─── In-memory fake of the postgrest-py fluent query interface ──────────────────
class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table: "_FakeTable"):
        self._table = table
        self._filters: dict = {}
        self._is_null_filters: list[str] = []
        self._op = None
        self._payload = None
        self._single = False
        self._order_col = None
        self._order_desc = False

    def select(self, *_cols):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def is_(self, col, val):
        if val in (None, "null"):
            self._is_null_filters.append(col)
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def maybe_single(self):
        self._single = True
        return self

    def _matches(self, row):
        if not all(row.get(k) == v for k, v in self._filters.items()):
            return False
        if not all(row.get(k) is None for k in self._is_null_filters):
            return False
        return True

    def execute(self):
        if self._op == "select":
            rows = [r for r in self._table.rows if self._matches(r)]
            if self._order_col is not None:
                rows = sorted(rows, key=lambda r: r.get(self._order_col), reverse=self._order_desc)
            if self._single:
                # Matches postgrest-py 2.30.0's real (surprising) behavior:
                # maybe_single().execute() returns bare None — not a response
                # object with .data=None — when zero rows match. Missed by an
                # earlier version of this fake, which let a real crash
                # (AttributeError: 'NoneType' object has no attribute 'data'
                # in _find_pending_request/poll_pairing_status) through to
                # production; caught live 23.09.2026 during the actual
                # guided-pairing browser flow.
                return _FakeResult(rows[0]) if rows else None
            return _FakeResult(rows)
        if self._op == "insert":
            row = dict(self._payload)
            row.setdefault("id", f"row-{len(self._table.rows) + 1}")
            for k in ("user_id", "workspace_id", "last_used_at", "revoked_at"):
                row.setdefault(k, None)
            self._table.rows.append(row)
            return _FakeResult([row])
        if self._op == "update":
            matched = [r for r in self._table.rows if self._matches(r)]
            for r in matched:
                r.update(self._payload)
            return _FakeResult(matched)
        raise NotImplementedError(self._op)


class _FakeTable:
    def __init__(self):
        self.rows: list[dict] = []

    def select(self, *cols):
        return _FakeQuery(self).select(*cols)

    def insert(self, payload):
        return _FakeQuery(self).insert(payload)

    def update(self, payload):
        return _FakeQuery(self).update(payload)


class _FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable())


def _patched_db():
    fake_db = _FakeDB()
    return fake_db, patch.object(svc, "get_db", return_value=fake_db)


import unittest  # noqa: E402


class PairingFlowTests(unittest.TestCase):
    def setUp(self):
        self.fake_db, self.patcher = _patched_db()
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_request_returns_a_usable_token_and_a_human_code(self):
        result = svc.create_pairing_request(label="Mein Laptop")
        self.assertTrue(result["runner_token"].startswith(svc.RUNNER_TOKEN_PREFIX))
        self.assertRegex(result["user_code"], r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertGreater(result["expires_in_seconds"], 0)

        # The connection exists but is unlinked — a fresh token authorizes nothing yet.
        conn = self.fake_db.table("runner_connections").rows[0]
        self.assertIsNone(conn["user_id"])
        self.assertNotEqual(conn["token_hash"], result["runner_token"])  # never stored raw

    def test_poll_before_approval_is_pending(self):
        result = svc.create_pairing_request(None)
        self.assertEqual(svc.poll_pairing_status(result["user_code"]), "pending")

    def test_approve_links_the_connection_to_the_approving_user(self):
        result = svc.create_pairing_request(None)
        connection = svc.approve_pairing("user-1", "ws-1", result["user_code"], "Büro-PC")
        self.assertEqual(connection["user_id"], "user-1")
        self.assertEqual(connection["workspace_id"], "ws-1")
        self.assertEqual(connection["label"], "Büro-PC")
        self.assertEqual(svc.poll_pairing_status(result["user_code"]), "approved")

    def test_approve_unknown_code_returns_none(self):
        self.assertIsNone(svc.approve_pairing("user-1", "ws-1", "ZZZZ-9999", None))

    def test_approve_is_case_and_whitespace_insensitive(self):
        result = svc.create_pairing_request(None)
        messy = f"  {result['user_code'].lower()}  "
        connection = svc.approve_pairing("user-1", "ws-1", messy, None)
        self.assertIsNotNone(connection)

    def test_poll_unknown_code_is_not_found(self):
        self.assertEqual(svc.poll_pairing_status("NOPE-0000"), "not_found")

    def test_list_connections_scoped_to_user(self):
        r1 = svc.create_pairing_request(None)
        r2 = svc.create_pairing_request(None)
        svc.approve_pairing("user-1", "ws-1", r1["user_code"], None)
        svc.approve_pairing("user-2", "ws-2", r2["user_code"], None)

        mine = svc.list_connections_for_user("user-1")
        self.assertEqual(len(mine), 1)

    def test_revoke_requires_matching_owner(self):
        result = svc.create_pairing_request(None)
        connection = svc.approve_pairing("user-1", "ws-1", result["user_code"], None)

        self.assertFalse(svc.revoke_connection("user-2", connection["id"]))  # wrong owner
        self.assertTrue(svc.revoke_connection("user-1", connection["id"]))   # real owner
        self.assertIsNotNone(
            [r for r in self.fake_db.table("runner_connections").rows if r["id"] == connection["id"]][0]["revoked_at"]
        )


class GetCurrentUserRunnerTokenTests(unittest.TestCase):
    """app.auth.get_current_user() must accept an approved runner token
    exactly like a real Supabase session — and reject anything else the
    same way it always has (unknown token, revoked connection, or a
    not-yet-approved one)."""

    def setUp(self):
        self.fake_db, self.patcher = _patched_db()
        self.patcher.start()
        self.get_db_patcher = patch.object(auth, "get_db", return_value=self.fake_db)
        self.get_db_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.get_db_patcher.stop()

    def _bearer(self, token: str):
        from fastapi.security import HTTPAuthorizationCredentials
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def test_approved_runner_token_resolves_to_its_owner(self):
        result = svc.create_pairing_request(None)
        svc.approve_pairing("user-1", "ws-1", result["user_code"], None)

        user = auth.get_current_user(self._bearer(result["runner_token"]))
        self.assertEqual(user.id, "user-1")
        self.assertEqual(user.workspace_id, "ws-1")

    def test_unapproved_runner_token_is_rejected(self):
        # Asserts the specific HTTPException(401) the auth dependency is
        # documented to raise for this case — not just "some exception".
        # A bare assertRaises(Exception) here would equally accept a real
        # AttributeError crash as a pass, which is exactly how the
        # maybe_single()-returns-None bug fixed 23.09.2026 (see
        # _resolve_runner_token's comment) slipped through this suite the
        # first time: it crashed with a 500 in production while this test
        # kept reporting green.
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(self._bearer(svc.create_pairing_request(None)["runner_token"]))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_revoked_runner_token_is_rejected(self):
        from fastapi import HTTPException
        result = svc.create_pairing_request(None)
        connection = svc.approve_pairing("user-1", "ws-1", result["user_code"], None)
        svc.revoke_connection("user-1", connection["id"])

        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(self._bearer(result["runner_token"]))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_unknown_runner_prefixed_token_is_rejected_not_treated_as_jwt(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(self._bearer(svc.RUNNER_TOKEN_PREFIX + "totally-made-up"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_runner_token_never_touches_runner_connections_table(self):
        # The fast prefix check must bail out before any DB call — a plain
        # (fake, in this test) JWT-shaped string should never even query
        # runner_connections.
        real_jwt_like = "eyJhbGciOiJIUzI1NiJ9.not-a-runner-token"
        db = self.fake_db
        original_table = db.table
        calls = []
        db.table = lambda name: (calls.append(name), original_table(name))[1]
        try:
            with self.assertRaises(Exception):
                auth.get_current_user(self._bearer(real_jwt_like))
        finally:
            db.table = original_table
        self.assertNotIn("runner_connections", calls)


class GetCurrentBrowserUserTests(unittest.TestCase):
    """app.auth.get_current_browser_user() — used by the pairing-approve
    endpoint — must reject a runner token outright, even a valid, already-
    approved one. A runner token proving "I am this onboarded user" is not
    the same guarantee as an actual logged-in browser session; letting one
    approve further pairing requests would let a single compromised runner
    token mint arbitrarily more of itself."""

    def setUp(self):
        self.fake_db, self.patcher = _patched_db()
        self.patcher.start()
        self.get_db_patcher = patch.object(auth, "get_db", return_value=self.fake_db)
        self.get_db_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.get_db_patcher.stop()

    def _bearer(self, token: str):
        from fastapi.security import HTTPAuthorizationCredentials
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def test_valid_approved_runner_token_is_still_rejected(self):
        from fastapi import HTTPException
        result = svc.create_pairing_request(None)
        svc.approve_pairing("user-1", "ws-1", result["user_code"], None)

        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_browser_user(self._bearer(result["runner_token"]))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_real_supabase_session_is_still_accepted(self):
        self.fake_db.auth = MagicMock()
        self.fake_db.auth.get_user.return_value = MagicMock(user=MagicMock(id="user-1", email="a@b.com"))

        user = auth.get_current_browser_user(self._bearer("a-real-looking-jwt"))
        self.assertEqual(user.id, "user-1")


if __name__ == "__main__":
    unittest.main()
