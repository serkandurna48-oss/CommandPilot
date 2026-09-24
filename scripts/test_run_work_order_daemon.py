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
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_work_order_daemon as daemon  # noqa: E402

# Found 23.09.2026, the hard way: a main()-invoking test that forgets to pass
# --session-file falls back to DEFAULT_SESSION_FILE — the real repo-root
# .cp_daemon_session.json. Several tests in this file did exactly that,
# which (a) overwrote a real cached refresh token with mock test data, and
# (b) let at least one test make a REAL network call to Supabase using that
# real refresh token before it got overwritten, which real reuse-detection
# treats as suspicious and can invalidate the whole session (browser
# included). Individually remembering --session-file per test clearly isn't
# reliable enough — this module-wide patch is the actual fix: for the
# duration of this entire test run, DEFAULT_SESSION_FILE (and, since the
# --pair/runner-token feature was added the same day, DEFAULT_RUNNER_TOKEN_FILE
# too) point at throwaway temp paths, so no test — this one or a future one
# that forgets — can ever reach either real file again, regardless of argv.
_patches: list = []
_tmpdir = None


def setUpModule():
    global _tmpdir
    _tmpdir = tempfile.TemporaryDirectory()
    for attr, filename in (
        ("DEFAULT_SESSION_FILE", ".cp_daemon_session.json"),
        ("DEFAULT_RUNNER_TOKEN_FILE", ".cp_runner_token.json"),
    ):
        p = patch.object(daemon, attr, Path(_tmpdir.name) / filename)
        p.start()
        _patches.append(p)


def tearDownModule():
    for p in _patches:
        p.stop()
    _tmpdir.cleanup()


def _args(**overrides):
    base = dict(
        adapter="claude_code", max_budget_usd=0.20, per_step=False,
        poll_interval=15.0, api_url="http://localhost:8000", token="fake-token",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _session(access_token="fake-token", **overrides):
    base = dict(access_token=access_token, refresh_token=None, supabase_url=None, supabase_anon_key=None)
    base.update(overrides)
    return daemon.TokenSession(**base)


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
            result = daemon.fetch_requested_work_orders("http://api", _session())
        self.assertEqual([o["id"] for o in result], ["wo-match"])

    def test_sorts_oldest_request_first(self):
        orders = [
            _order("wo-newer", requested_at="2026-09-22T12:00:00+00:00"),
            _order("wo-oldest", requested_at="2026-09-22T09:00:00+00:00"),
            _order("wo-middle", requested_at="2026-09-22T10:30:00+00:00"),
        ]
        with patch.object(daemon, "call_api", return_value=orders):
            result = daemon.fetch_requested_work_orders("http://api", _session())
        self.assertEqual([o["id"] for o in result], ["wo-oldest", "wo-middle", "wo-newer"])


class ClaimTests(unittest.TestCase):
    def test_claim_patches_field_to_null(self):
        session = _session()
        with patch.object(daemon, "call_api", return_value={}) as mock_call:
            ok = daemon.claim("http://api", session, "wo-1")
        self.assertTrue(ok)
        mock_call.assert_called_once_with(
            "http://api", session, "PATCH", "/api/work-orders/wo-1",
            {"daemon_run_requested_at": None},
        )

    def test_claim_failure_is_logged_not_raised(self):
        with patch.object(daemon, "call_api", side_effect=daemon.DaemonApiError("boom")):
            ok = daemon.claim("http://api", _session(), "wo-1")
        self.assertFalse(ok)


class RunOneTests(unittest.TestCase):
    def test_builds_correct_subprocess_command(self):
        args = _args(adapter="claude_code_sandboxed", max_budget_usd=0.5, per_step=True)
        with patch.object(daemon.subprocess, "run", return_value=MagicMock(returncode=0)) as mock_run:
            rc = daemon.run_one(args, _session(), "wo-1")

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
            daemon.run_one(args, _session(), "wo-1")
        cmd = mock_run.call_args.args[0]
        self.assertNotIn("--per-step", cmd)

    def test_uses_the_sessions_current_access_token_not_a_stale_copy(self):
        # Matters once the daemon has refreshed at least once — run_one must
        # read session.access_token at call time, not a snapshot from
        # daemon startup.
        args = _args()
        session = _session(access_token="rotated-token")
        with patch.object(daemon.subprocess, "run", return_value=MagicMock(returncode=0)) as mock_run:
            daemon.run_one(args, session, "wo-1")
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--token") + 1], "rotated-token")


class PollOnceTests(unittest.TestCase):
    def test_claims_before_starting_subprocess(self):
        # The exact ordering guarantee the module docstring promises: the
        # claim PATCH must happen before subprocess.run(), never after.
        call_order: list[str] = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return [_order("wo-1")]
            call_order.append("claim")
            return {}

        def fake_subprocess_run(cmd, cwd=None):
            call_order.append("subprocess")
            return MagicMock(returncode=0)

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon.subprocess, "run", side_effect=fake_subprocess_run):
            daemon.poll_once(_args(), _session())

        self.assertEqual(call_order, ["claim", "subprocess"])

    def test_skips_starting_subprocess_when_claim_fails(self):
        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return [_order("wo-1")]
            raise daemon.DaemonApiError("claim failed")

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon.subprocess, "run") as mock_run:
            daemon.poll_once(_args(), _session())

        mock_run.assert_not_called()

    def test_processes_multiple_matches_sequentially_oldest_first(self):
        orders = [
            _order("wo-newer", requested_at="2026-09-22T12:00:00+00:00"),
            _order("wo-oldest", requested_at="2026-09-22T09:00:00+00:00"),
        ]
        started: list[str] = []
        claimed: list[str] = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return orders
            claimed.append(path.rsplit("/", 1)[-1])
            return {}

        def fake_subprocess_run(cmd, cwd=None):
            started.append(cmd[2])  # work_order_id is argv[2]
            return MagicMock(returncode=0)

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon.subprocess, "run", side_effect=fake_subprocess_run):
            daemon.poll_once(_args(), _session())

        # Oldest first, and both processed sequentially within one poll cycle.
        self.assertEqual(claimed, ["wo-oldest", "wo-newer"])
        self.assertEqual(started, ["wo-oldest", "wo-newer"])

    def test_no_matches_makes_no_calls_beyond_the_initial_fetch(self):
        with patch.object(daemon, "call_api", return_value=[]) as mock_call, \
             patch.object(daemon.subprocess, "run") as mock_run:
            daemon.poll_once(_args(), _session())
        mock_call.assert_called_once()  # only the GET, no claim PATCH
        mock_run.assert_not_called()

    def test_fetch_failure_does_not_raise(self):
        with patch.object(daemon, "call_api", side_effect=daemon.DaemonApiError("down")), \
             patch.object(daemon.subprocess, "run") as mock_run:
            daemon.poll_once(_args(), _session())  # must not raise
        mock_run.assert_not_called()


def _http_error(code: int, body: bytes = b"{}"):
    import io
    return daemon.urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body))


def _ok_response(payload: dict):
    cm = MagicMock()
    cm.__enter__.return_value = cm
    cm.__exit__.return_value = False
    cm.read.return_value = json.dumps(payload).encode("utf-8")
    return cm


class TokenSessionRefreshTests(unittest.TestCase):
    """Found 23.09.2026: a plain --token expires in ~1h and the daemon had
    no way to renew it — every restart needed a fresh manual paste from
    browser DevTools. TokenSession.refresh() is the fix: same Supabase
    refresh-token flow the browser's own client already uses silently."""

    def test_refresh_updates_tokens_and_persists_to_session_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / "session.json"
            session = daemon.TokenSession(
                access_token="stale", refresh_token="seed-refresh",
                supabase_url="https://proj.supabase.co", supabase_anon_key="anon-key",
                session_file=session_file,
            )
            with patch.object(daemon.urllib.request, "urlopen",
                               return_value=_ok_response({"access_token": "fresh", "refresh_token": "rotated"})):
                session.refresh()

            self.assertEqual(session.access_token, "fresh")
            self.assertEqual(session.refresh_token, "rotated")
            saved = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["refresh_token"], "rotated")

    def test_refresh_without_capability_raises_clearly(self):
        session = _session(access_token="only-this")
        self.assertFalse(session.can_refresh)
        with self.assertRaises(daemon.DaemonApiError):
            session.refresh()

    def test_refresh_rejected_by_supabase_names_likely_cause(self):
        session = daemon.TokenSession(
            access_token="stale", refresh_token="dead-refresh",
            supabase_url="https://proj.supabase.co", supabase_anon_key="anon-key",
        )
        with patch.object(daemon.urllib.request, "urlopen", side_effect=_http_error(400)):
            with self.assertRaises(daemon.DaemonApiError) as ctx:
                session.refresh()
        self.assertIn("expired or been revoked", str(ctx.exception))


class CallApiAutoRefreshTests(unittest.TestCase):
    def test_401_triggers_exactly_one_refresh_then_succeeds(self):
        session = _session(access_token="stale", refresh_token="seed",
                             supabase_url="https://x.supabase.co", supabase_anon_key="anon")
        attempts = {"n": 0}

        def fake_urlopen(req, timeout=30):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise _http_error(401)
            return _ok_response({"ok": True})

        def fake_refresh():
            session.access_token = "fresh"

        with patch.object(session, "refresh", side_effect=fake_refresh) as mock_refresh, \
             patch.object(daemon.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = daemon.call_api("http://api", session, "GET", "/api/work-orders/me")

        mock_refresh.assert_called_once()
        self.assertEqual(result, {"ok": True})
        self.assertEqual(attempts["n"], 2)

    def test_401_without_refresh_capability_raises_immediately(self):
        session = _session(access_token="stale")  # no refresh_token/url/key configured
        with patch.object(daemon.urllib.request, "urlopen", side_effect=_http_error(401)):
            with self.assertRaises(daemon.DaemonApiError):
                daemon.call_api("http://api", session, "GET", "/api/work-orders/me")

    def test_second_401_right_after_a_refresh_is_not_retried_again(self):
        # A 401 immediately after a successful refresh means something is
        # actually wrong (revoked session, wrong project) — must surface as
        # a real error, never loop.
        session = _session(access_token="stale", refresh_token="seed",
                             supabase_url="https://x.supabase.co", supabase_anon_key="anon")
        with patch.object(session, "refresh") as mock_refresh, \
             patch.object(daemon.urllib.request, "urlopen", side_effect=_http_error(401)):
            with self.assertRaises(daemon.DaemonApiError):
                daemon.call_api("http://api", session, "GET", "/api/work-orders/me")
        mock_refresh.assert_called_once()


class MainSessionResolutionTests(unittest.TestCase):
    """main()'s token/session resolution — the part that decides between
    plain --token, a fresh --refresh-token, and a cached session file."""

    def test_refresh_token_flag_mints_a_working_session_at_startup(self):
        argv = [
            "run_work_order_daemon.py", "--adapter", "claude_code",
            "--refresh-token", "seed", "--supabase-url", "https://x.supabase.co",
            "--supabase-anon-key", "anon",
        ]
        with patch.object(sys, "argv", argv), \
             patch.object(daemon.urllib.request, "urlopen",
                           return_value=_ok_response({"access_token": "minted", "refresh_token": "rotated"})), \
             patch.object(daemon, "poll_once") as mock_poll, \
             patch.object(daemon.time, "sleep", side_effect=KeyboardInterrupt):
            rc = daemon.main()
        self.assertEqual(rc, 0)
        session_arg = mock_poll.call_args.args[1]
        self.assertEqual(session_arg.access_token, "minted")

    def test_refresh_token_rejected_at_startup_exits_cleanly(self):
        argv = [
            "run_work_order_daemon.py", "--adapter", "claude_code",
            "--refresh-token", "dead", "--supabase-url", "https://x.supabase.co",
            "--supabase-anon-key", "anon",
        ]
        with patch.object(sys, "argv", argv), \
             patch.object(daemon.urllib.request, "urlopen", side_effect=_http_error(400)):
            rc = daemon.main()
        self.assertEqual(rc, 1)

    def test_cached_session_file_seeds_refresh_without_a_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / "session.json"
            session_file.write_text(json.dumps({"refresh_token": "cached-refresh"}), encoding="utf-8")
            argv = [
                "run_work_order_daemon.py", "--adapter", "claude_code",
                "--supabase-url", "https://x.supabase.co", "--supabase-anon-key", "anon",
                "--session-file", str(session_file),
            ]
            with patch.object(sys, "argv", argv), \
                 patch.object(daemon.urllib.request, "urlopen",
                               return_value=_ok_response({"access_token": "minted", "refresh_token": "rotated-again"})), \
                 patch.object(daemon, "poll_once") as mock_poll, \
                 patch.object(daemon.time, "sleep", side_effect=KeyboardInterrupt):
                rc = daemon.main()
            self.assertEqual(rc, 0)
            mock_poll.assert_called_once()
            # the cache file must now hold the newly-rotated token, not the seed
            self.assertEqual(json.loads(session_file.read_text())["refresh_token"], "rotated-again")

    def test_runner_token_wins_over_a_stale_refresh_cache_even_if_it_is_expired(self):
        # Found in review: a machine that had used --refresh-token before
        # switching to --pair could still have an old .cp_daemon_session.json
        # lying around. If that cached refresh token was itself
        # expired/revoked, the daemon used to try refreshing anyway and
        # refuse to start — even though the runner token it also loaded was
        # perfectly valid on its own. The two must be mutually exclusive.
        with tempfile.TemporaryDirectory() as tmp:
            runner_token_file = Path(tmp) / "runner.json"
            runner_token_file.write_text(
                json.dumps({"runner_token": daemon.RUNNER_TOKEN_PREFIX + "valid-paired-token"}),
                encoding="utf-8",
            )
            session_file = Path(tmp) / "session.json"
            session_file.write_text(json.dumps({"refresh_token": "expired-old-refresh-token"}), encoding="utf-8")
            argv = [
                "run_work_order_daemon.py", "--adapter", "claude_code",
                "--supabase-url", "https://x.supabase.co", "--supabase-anon-key", "anon",
                "--runner-token-file", str(runner_token_file),
                "--session-file", str(session_file),
            ]
            with patch.object(sys, "argv", argv), \
                 patch.object(daemon.urllib.request, "urlopen", side_effect=_http_error(400)) as mock_urlopen, \
                 patch.object(daemon, "poll_once") as mock_poll, \
                 patch.object(daemon.time, "sleep", side_effect=KeyboardInterrupt):
                rc = daemon.main()
            self.assertEqual(rc, 0)
            mock_urlopen.assert_not_called()  # never even attempts to refresh the stale cache
            session_arg = mock_poll.call_args.args[1]
            self.assertEqual(session_arg.access_token, daemon.RUNNER_TOKEN_PREFIX + "valid-paired-token")

    def test_no_token_and_no_refresh_capability_fails_with_a_clear_message(self):
        # Explicit empty strings everywhere a real shell environment could
        # otherwise leak a leftover COMMANDPILOT_API_TOKEN/_SUPABASE_* into
        # this test and silently flip the expected outcome.
        argv = [
            "run_work_order_daemon.py", "--adapter", "claude_code",
            "--token", "", "--supabase-url", "", "--supabase-anon-key", "",
        ]
        with patch.object(sys, "argv", argv), \
             patch.object(daemon, "_read_frontend_env_local", return_value=None):
            rc = daemon.main()
        self.assertEqual(rc, 1)


class MainAdapterValidationTests(unittest.TestCase):
    """main() must refuse to start with an adapter that can't run
    autonomously, instead of starting the poll loop and letting every
    claimed work order silently revert to 'queued' with zero trace (the
    regression this check exists to prevent)."""

    def test_refuses_manual_prompt_adapter_before_polling(self):
        argv = ["run_work_order_daemon.py", "--token", "fake-token"]  # default adapter=manual_prompt
        with patch.object(sys, "argv", argv), \
             patch.object(daemon.time, "sleep") as mock_sleep:
            rc = daemon.main()
        self.assertEqual(rc, 1)
        mock_sleep.assert_not_called()  # never reached the poll loop

    def test_accepts_claude_code_adapter(self):
        argv = ["run_work_order_daemon.py", "--token", "fake-token", "--adapter", "claude_code"]
        with patch.object(sys, "argv", argv), \
             patch.object(daemon, "poll_once") as mock_poll, \
             patch.object(daemon.time, "sleep", side_effect=KeyboardInterrupt):
            rc = daemon.main()
        self.assertEqual(rc, 0)  # clean Ctrl+C exit, not the adapter-validation error path
        mock_poll.assert_called_once()

    def test_rejects_unknown_adapter_name(self):
        argv = ["run_work_order_daemon.py", "--token", "fake-token", "--adapter", "does_not_exist"]
        with patch.object(sys, "argv", argv):
            rc = daemon.main()
        self.assertEqual(rc, 1)


class PairingFlowTests(unittest.TestCase):
    """--pair (23.09.2026) — the flow that replaces ever copying a token out
    of browser DevTools. Runs entirely against mocked HTTP; no real backend,
    no real Supabase."""

    def test_successful_pairing_saves_the_runner_token(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "runner.json"
            responses = iter([
                _ok_response({"user_code": "ABCD-1234", "runner_token": "cprun_secret",
                               "expires_in_seconds": 600, "poll_interval_seconds": 0}),
                _ok_response({"status": "pending"}),
                _ok_response({"status": "approved"}),
            ])
            with patch.object(daemon.urllib.request, "urlopen", side_effect=lambda *a, **k: next(responses)), \
                 patch.object(daemon.time, "sleep"):
                rc = daemon.run_pairing_flow("http://api", "http://web", token_file)

            self.assertEqual(rc, 0)
            saved = json.loads(token_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["runner_token"], "cprun_secret")

    def test_expired_pairing_fails_without_writing_a_token_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "runner.json"
            responses = iter([
                _ok_response({"user_code": "ABCD-1234", "runner_token": "cprun_secret",
                               "expires_in_seconds": 600, "poll_interval_seconds": 0}),
                _ok_response({"status": "expired"}),
            ])
            with patch.object(daemon.urllib.request, "urlopen", side_effect=lambda *a, **k: next(responses)), \
                 patch.object(daemon.time, "sleep"):
                rc = daemon.run_pairing_flow("http://api", "http://web", token_file)

            self.assertEqual(rc, 1)
            self.assertFalse(token_file.exists())

    def test_backend_unreachable_at_request_step_fails_clearly(self):
        with patch.object(daemon.urllib.request, "urlopen", side_effect=daemon.urllib.error.URLError("refused")):
            rc = daemon.run_pairing_flow("http://api", "http://web", Path("unused.json"))
        self.assertEqual(rc, 1)

    def test_main_dispatches_to_pairing_flow_and_skips_the_normal_daemon_path(self):
        argv = ["run_work_order_daemon.py", "--pair"]
        with patch.object(sys, "argv", argv), \
             patch.object(daemon, "run_pairing_flow", return_value=0) as mock_pair, \
             patch.object(daemon, "poll_once") as mock_poll:
            rc = daemon.main()
        self.assertEqual(rc, 0)
        mock_pair.assert_called_once()
        mock_poll.assert_not_called()


if __name__ == "__main__":
    unittest.main()
