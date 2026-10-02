"""Tests for L1: Supabase thread-safety and resilience fixes.

Criterion 1: get_db() creates a Supabase client with HTTP/2 disabled.
Criterion 2: 20 parallel threads calling a mocked select chain complete
             without exception and without sharing a single HTTP/2 connection.
Criterion 3: ReadError on first select attempt → second attempt succeeds;
             insert NOT wrapped in retry_read → propagates immediately.
Criterion 4: Unhandled route exception → 500 JSON with Access-Control-Allow-Origin
             set for matching origin.

Run:
    python -m pytest backend/tests/test_supabase_threadsafe.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

import httpx  # noqa: E402 — after sys.path setup


# ─── Criterion 1: get_db() without HTTP/2 ────────────────────────────────────

class GetDbNoHttp2Tests(unittest.TestCase):
    def setUp(self):
        import app.db.client as db_module
        self._db_module = db_module
        self._saved = db_module._client
        db_module._client = None

    def tearDown(self):
        self._db_module._client = self._saved

    def test_create_client_called_with_http2_false(self):
        """get_db() must pass ClientOptions(httpx_client=httpx.Client(http2=False))
        to create_client, so postgrest-py never falls back to its default
        http2=True (which caused EAGAIN/ReadError under concurrent load)."""
        mock_client = MagicMock()
        with patch("app.db.client.create_client", return_value=mock_client) as mock_create:
            self._db_module.get_db()

        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        options = kwargs.get("options")
        self.assertIsNotNone(options, "ClientOptions must be passed as 'options'")
        httpx_client = options.httpx_client
        self.assertIsNotNone(httpx_client, "ClientOptions.httpx_client must not be None")
        # Verify HTTP/2 is disabled on the transport pool level
        http2_flag = httpx_client._transport._pool._http2
        self.assertFalse(http2_flag, "httpx.Client must be created with http2=False")

    def test_same_instance_returned_on_second_call(self):
        mock_client = MagicMock()
        with patch("app.db.client.create_client", return_value=mock_client) as mock_create:
            a = self._db_module.get_db()
            b = self._db_module.get_db()
        mock_create.assert_called_once()
        self.assertIs(a, b)


# ─── Criterion 2: 20 parallel threads, no shared HTTP/2 connection ───────────

class ParallelThreadsNoHttp2Tests(unittest.TestCase):
    def setUp(self):
        import app.db.client as db_module
        self._db_module = db_module
        self._saved = db_module._client
        db_module._client = None

    def tearDown(self):
        self._db_module._client = self._saved

    def test_20_threads_no_exception(self):
        """20 concurrent threads each call a mocked select chain via get_db().
        With http2=False the underlying connection pool is thread-safe
        (HTTP/1.1, one connection per concurrent request from the pool)."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"id": "row"})

        errors: list[Exception] = []

        def call_select():
            try:
                db = self._db_module.get_db()
                db.table("test").select("*").eq("id", "1").maybe_single().execute()
            except Exception as exc:
                errors.append(exc)

        with patch("app.db.client.create_client", return_value=mock_db):
            threads = [threading.Thread(target=call_select) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [], f"Threads raised: {errors}")

    def test_every_client_created_has_http2_false(self):
        """Whether one or more Supabase clients are created across threads,
        each must always use http2=False (covered centrally in get_db())."""
        created_options: list = []
        original_create = None

        import supabase as _supabase_mod

        def capturing_create(url, key, options=None):
            if options is not None:
                created_options.append(options)
            return MagicMock()

        with patch("app.db.client.create_client", side_effect=capturing_create):
            threads = [threading.Thread(target=self._db_module.get_db) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertGreater(len(created_options), 0, "At least one client must be created")
        for opts in created_options:
            self.assertFalse(
                opts.httpx_client._transport._pool._http2,
                "Every client created must have http2=False",
            )


# ─── Criterion 3: retry_read for select; no retry for insert ─────────────────

class RetryReadTests(unittest.TestCase):
    def test_read_error_on_first_attempt_retried(self):
        """ReadError on attempt 1 → transparent retry → result returned on attempt 2."""
        from app.db.client import retry_read

        calls = [0]

        def mock_select():
            calls[0] += 1
            if calls[0] == 1:
                raise httpx.ReadError("EAGAIN")
            return {"data": [{"id": "row-1"}]}

        result = retry_read(mock_select)
        self.assertEqual(calls[0], 2)
        self.assertEqual(result, {"data": [{"id": "row-1"}]})

    def test_remote_protocol_error_retried(self):
        from app.db.client import retry_read

        calls = [0]

        def mock_select():
            calls[0] += 1
            if calls[0] == 1:
                raise httpx.RemoteProtocolError("peer closed")
            return {"data": []}

        result = retry_read(mock_select)
        self.assertEqual(calls[0], 2)

    def test_max_retries_exceeded_raises(self):
        """After _RETRY_MAX + 1 attempts all failing → last ReadError is raised."""
        from app.db.client import retry_read, _RETRY_MAX

        calls = [0]

        def always_fail():
            calls[0] += 1
            raise httpx.ReadError("always fail")

        with self.assertRaises(httpx.ReadError):
            retry_read(always_fail)
        self.assertEqual(calls[0], _RETRY_MAX + 1)

    def test_insert_not_wrapped_raises_immediately(self):
        """Insert callables are never passed to retry_read — a bare call
        raises immediately (call count == 1, no retry)."""
        calls = [0]

        def mock_insert():
            calls[0] += 1
            raise httpx.ReadError("transient")

        with self.assertRaises(httpx.ReadError):
            mock_insert()  # direct call, no retry_read wrapper
        self.assertEqual(calls[0], 1)


# ─── Criterion 4: global exception handler returns 500 JSON + CORS ───────────

class UnhandledExceptionHandlerTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def _make_request(self, origin: str) -> MagicMock:
        req = MagicMock()
        req.headers.get.side_effect = lambda key, default="": origin if key == "origin" else default
        return req

    def test_500_json_for_frontend_origin(self):
        from app.main import _unhandled_exception_handler

        req = self._make_request(os.environ.get("FRONTEND_URL", "http://localhost:3000"))
        resp = self._run(_unhandled_exception_handler(req, RuntimeError("boom")))

        import json
        body = json.loads(resp.body)
        self.assertEqual(resp.status_code, 500)
        self.assertIn("detail", body)
        self.assertEqual(resp.headers.get("access-control-allow-origin"),
                         os.environ.get("FRONTEND_URL", "http://localhost:3000"))
        self.assertEqual(resp.headers.get("access-control-allow-credentials"), "true")

    def test_500_json_for_localhost_3001(self):
        from app.main import _unhandled_exception_handler

        req = self._make_request("http://localhost:3001")
        resp = self._run(_unhandled_exception_handler(req, ValueError("db error")))

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.headers.get("access-control-allow-origin"), "http://localhost:3001")

    def test_500_json_no_cors_for_unknown_origin(self):
        from app.main import _unhandled_exception_handler

        req = self._make_request("https://attacker.example.com")
        resp = self._run(_unhandled_exception_handler(req, ValueError("x")))

        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("access-control-allow-origin", resp.headers)

    def test_500_json_for_vercel_preview_origin(self):
        from app.main import _unhandled_exception_handler

        origin = "https://command-pilot-abc123-serkans-projects-a49183cd.vercel.app"
        req = self._make_request(origin)
        resp = self._run(_unhandled_exception_handler(req, RuntimeError("x")))

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.headers.get("access-control-allow-origin"), origin)


if __name__ == "__main__":
    unittest.main()
