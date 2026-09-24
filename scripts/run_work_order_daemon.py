#!/usr/bin/env python3
"""Local daemon: watches for work orders flagged "Autonom starten" in the
Operator UI and runs them to completion without a human typing a command.

This is the "triggered runner" docs/background-dev-team-system-design.md
§9 step 3b named as "not yet built": "Something (a button in the UI, a
scheduled check) that picks up a queued work order and starts a [...]
session [...] without a human running a command." The trigger moves from
"a human runs a script" to "a human starts this daemon once, then clicks a
button per work order" — CommandPilot's own backend still never executes
a shell command itself; this is a separate, explicitly human-started local
process, exactly like scripts/run_work_order.py always was.

What this daemon IS: a poll loop that finds work orders with
status == "queued" and work_orders.daemon_run_requested_at set (the trigger
signal — see supabase/migrations/016_work_orders_daemon_run_requested.sql
and frontend/components/operator/LifecycleControls.tsx's "Autonom starten"
button), claims the oldest one (clears the field back to null so a crash
mid-claim or a later requeue never stale-retriggers), and invokes
scripts/run_work_order.py --mode execute with ITS OWN fixed configuration
(--adapter/--max-budget-usd/--per-step, chosen once at daemon startup, not
per work order) — the exact same command a human would type.

What this daemon is NOT: it duplicates NONE of run_work_order.py's safety
logic. validate_preconditions(), check_scope_errors(), the budget gate,
check_execute_path_safety(), the bounded retry, the interrupt/should_stop()
poll — all of that lives entirely inside the subprocess this daemon starts,
unchanged. This file is pure orchestration: poll, claim, subprocess.run(),
log, repeat.

Autonomy boundary (unchanged from every other adapter): a run started this
way still stops hard at needs_approval/blocked, still ends at review_ready
(never auto-'accepted' — that stays a human click in the UI), and — for
claude_code_sandboxed — still only ever produces a diff artifact to review,
never applies it automatically.

Zero third-party dependencies on purpose (stdlib `urllib` only), matching
scripts/run_work_order.py and scripts/import_work_order_result.py.

Usage:
    python scripts/run_work_order_daemon.py --pair                        # one-time setup
    python scripts/run_work_order_daemon.py --adapter claude_code --max-budget-usd 0.20
    python scripts/run_work_order_daemon.py --adapter claude_code_sandboxed --max-budget-usd 0.50 --per-step
    python scripts/run_work_order_daemon.py --adapter claude_code --max-budget-usd 0.20 --poll-interval 30

Auth: three modes, in the order you should actually reach for them.

  (a) --pair (RECOMMENDED — no browser DevTools, no copied token, ever).
      Run once: `python scripts/run_work_order_daemon.py --pair`. Prints a
      short code and opens/points you at the "Runner verbinden" page in the
      web app (already logged in there — that's the whole point). Approve
      it there; the daemon picks that up within a few seconds and saves the
      resulting runner token to .cp_runner_token.json (repo root,
      gitignored, 0o600). Every future `run_work_order_daemon.py` call
      (no --pair) loads it automatically — nothing to paste, ever again,
      until you revoke it from the same "Runner verbinden" settings page.
      See supabase/migrations/017_runner_connections.sql for how this is
      backed: a token that's scoped to your account and workspace,
      independently revocable, never a copy of your actual login session.

  (b) --token / COMMANDPILOT_API_TOKEN — a raw Supabase access token. Manual,
      expires in ~1h, no auto-refresh. Kept for scripting/one-off debugging,
      not for anything you leave running.

  (c) --refresh-token / COMMANDPILOT_REFRESH_TOKEN — a Supabase refresh
      token (browser localStorage, next to the access token). Self-renewing
      like (a), but still starts from a value you copied out of DevTools
      once — (a) exists specifically so nobody has to do that. Kept for
      environments where pairing isn't reachable (e.g. the web app itself
      isn't deployed yet). Needs --supabase-url/--supabase-anon-key too
      (auto-discovered from frontend/.env.local if omitted). Rotated token
      cached in .cp_daemon_session.json — a DIFFERENT file from (a)'s, never
      mix the two.

  Whichever mode, this is your own session, scoped to your own account (GET
  /api/work-orders/me is user-scoped) — inherently per-user, local, opt-in,
  never a shared service. Treat every one of these credentials like a
  password — never paste any of them into a chat/agent session.

  Known limitation (b and c only): a work order's subprocess
  (run_work_order.py) gets a single access-token snapshot at start and does
  not refresh mid-run — a single execution longer than the token's lifetime
  can still fail with a 401 partway through. Mode (a)'s runner token doesn't
  expire at all, so this doesn't apply to it.

Stop it with Ctrl+C — it finishes whatever subprocess is currently running
(a claimed work order's own run_work_order.py invocation is not killed by
stopping the daemon between polls) before exiting cleanly. To interrupt a
work order that's actually running, use the Stop button in the UI (already
works — the harness's own ProgressReporter.should_stop() poll picks it up),
not Ctrl+C on this daemon.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_WORK_ORDER_SCRIPT = Path(__file__).resolve().parent / "run_work_order.py"
DEFAULT_SESSION_FILE = REPO_ROOT / ".cp_daemon_session.json"
DEFAULT_RUNNER_TOKEN_FILE = REPO_ROOT / ".cp_runner_token.json"
FRONTEND_ENV_LOCAL = REPO_ROOT / "frontend" / ".env.local"
FRONTEND_URL_DEFAULT = "http://localhost:3001"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_adapters import ADAPTERS, get_adapter  # noqa: E402 — needs sys.path set first

_MAX_ATTEMPTS = 3
_RETRY_DELAY_S = 1.0


def _read_frontend_env_local(key: str) -> str | None:
    """Best-effort read of a NEXT_PUBLIC_* value out of frontend/.env.local —
    both values this is ever used for (Supabase URL, anon key) are public/
    non-secret by design (shipped to every browser via the NEXT_PUBLIC_
    prefix), so reading them here is not a credential leak. Returns None on
    any problem (file missing, key not found) rather than raising — this is
    always just a convenience default, never a required source."""
    try:
        for line in FRONTEND_ENV_LOCAL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line[len(key) + 1:].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _write_owner_only(path: Path, payload: dict) -> None:
    """Same 0o600-on-create-plus-chmod approach as TokenSession._persist —
    see that method's comment for why (a credential file, owner-only,
    best-effort on Windows/real protection on POSIX)."""
    data = json.dumps(payload).encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(str(path), 0o600)


def run_pairing_flow(api_url: str, frontend_url: str, runner_token_file: Path) -> int:
    """--pair: the one-time setup that replaces ever copying a token out of
    browser DevTools. See supabase/migrations/017_runner_connections.sql's
    header comment for the full three-step flow this drives step 1 and 3 of
    (step 2, approval, happens entirely in the browser)."""
    import platform
    import socket

    label = f"{socket.gethostname()} ({platform.system()})"
    body = json.dumps({"label": label}).encode("utf-8")
    req = urllib.request.Request(f"{api_url.rstrip('/')}/api/runner-connections/pairing/request",
                                  data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"ERROR: konnte keine Pairing-Anfrage an {api_url} stellen: {exc}", file=sys.stderr)
        print("Läuft das Backend? --api-url richtig gesetzt?", file=sys.stderr)
        return 1

    user_code = data["user_code"]
    runner_token = data["runner_token"]
    poll_interval = data.get("poll_interval_seconds", 3)
    expires_in = data.get("expires_in_seconds", 600)

    print()
    print(f"  Code:  {user_code}")
    print()
    print(f"  Öffne {frontend_url.rstrip('/')}/settings, Abschnitt \"Runner verbinden\",")
    print(f"  und gib diesen Code ein. Läuft in {expires_in // 60} Minuten ab.")
    print()
    log("Warte auf Bestätigung im Browser...")

    poll_body = json.dumps({"user_code": user_code}).encode("utf-8")
    deadline = time.time() + expires_in + 5
    while time.time() < deadline:
        time.sleep(poll_interval)
        poll_req = urllib.request.Request(f"{api_url.rstrip('/')}/api/runner-connections/pairing/poll",
                                           data=poll_body, method="POST")
        poll_req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(poll_req, timeout=30) as resp:
                status = json.loads(resp.read().decode("utf-8"))["status"]
        except urllib.error.URLError as exc:
            log(f"  (Poll fehlgeschlagen, versuche weiter: {exc})")
            continue

        if status == "approved":
            _write_owner_only(runner_token_file, {"runner_token": runner_token, "label": label, "paired_at": now_iso()})
            log(f"Verbunden. Token gespeichert in {runner_token_file}.")
            print()
            print("  Ab jetzt reicht: python scripts/run_work_order_daemon.py --adapter claude_code --max-budget-usd 0.20")
            print("  (kein Token, keine Umgebungsvariable mehr nötig)")
            return 0
        if status in ("expired", "denied", "not_found"):
            print(f"ERROR: Pairing {status} — führe --pair erneut aus.", file=sys.stderr)
            return 1
        # "pending" — keep waiting.

    print("ERROR: Zeitüberschreitung beim Warten auf Bestätigung — führe --pair erneut aus.", file=sys.stderr)
    return 1


class TokenSession:
    """Holds the daemon's current Supabase credentials and knows how to
    refresh itself. Two modes:

    - plain: only an access_token, no refresh capability (old behavior,
      --token/COMMANDPILOT_API_TOKEN) — refresh() raises immediately, call_api
      surfaces the original 401 exactly as before.
    - refreshing: has a refresh_token + supabase_url + supabase_anon_key —
      refresh() calls Supabase's own token endpoint (the same one the
      browser's Supabase client uses internally), updates access_token AND
      refresh_token in place (Supabase rotates the refresh token on every
      use — the old one stops working the moment a new one is issued), and
      persists both to session_file so a daemon restart can reuse them
      without another manual paste.
    """

    def __init__(
        self,
        access_token: str | None,
        refresh_token: str | None = None,
        supabase_url: str | None = None,
        supabase_anon_key: str | None = None,
        session_file: Path | None = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.supabase_url = supabase_url
        self.supabase_anon_key = supabase_anon_key
        self.session_file = session_file

    @property
    def can_refresh(self) -> bool:
        return bool(self.refresh_token and self.supabase_url and self.supabase_anon_key)

    def refresh(self) -> None:
        if not self.can_refresh:
            raise DaemonApiError(
                "Access token expired/invalid and no refresh token is configured — "
                "get a fresh one (docs/background-dev-team-runbook.md §1) or switch "
                "to --refresh-token for a self-renewing session."
            )
        url = f"{self.supabase_url.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
        body = json.dumps({"refresh_token": self.refresh_token}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("apikey", self.supabase_anon_key)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DaemonApiError(
                f"Refresh token rejected by Supabase (HTTP {exc.code}): {detail[:300]} — "
                "it has likely expired or been revoked (e.g. a password change or "
                "'log out everywhere'). Get a fresh refresh token from the browser "
                "and pass it via --refresh-token again."
            ) from exc
        except urllib.error.URLError as exc:
            raise DaemonApiError(f"Could not reach Supabase to refresh the session: {exc.reason}") from exc

        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]  # rotated — the old one is now dead
        self._persist()
        log("Session automatisch erneuert (Access Token via Refresh Token).")

    def _persist(self) -> None:
        # The refresh token is a full-strength credential — anyone who reads
        # it can mint their own access tokens as this user, same severity as
        # a password (see the runbook's "Token hygiene" note). _write_owner_only
        # writes with 0o600 rather than Path.write_text()'s default (whatever
        # umask/ACL the OS hands out, typically world-readable) — see that
        # function for the Windows-vs-POSIX caveat.
        if not self.session_file:
            return
        try:
            _write_owner_only(self.session_file, {"refresh_token": self.refresh_token, "saved_at": now_iso()})
        except OSError as exc:
            log(f"WARNUNG: konnte Session nicht in {self.session_file} zwischenspeichern: {exc}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}")


class DaemonApiError(Exception):
    """Same shape/intent as import_work_order_result.py's ImportError_ —
    raised for a single failed API call, caught per-call so one bad request
    doesn't crash the whole poll loop."""


def call_api(
    api_url: str, session: TokenSession, method: str, path: str,
    payload: dict[str, Any] | None = None, _refreshed_already: bool = False,
) -> Any:
    """Same retry posture as import_work_order_result.py's call_api(): only
    5xx/connection-level failures are retried (a real backend hiccup), 4xx
    is never retried as-is — EXCEPT 401, which gets exactly one
    refresh-and-retry attempt first (if session.can_refresh) before being
    surfaced as a real error. _refreshed_already guards against ever looping
    (a 401 right after a successful refresh means something is genuinely
    wrong — a revoked session, wrong project — not a token freshness issue)."""
    url = f"{api_url.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {session.access_token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and not _refreshed_already and session.can_refresh:
                session.refresh()  # raises DaemonApiError on its own failure — propagates as-is
                return call_api(api_url, session, method, path, payload, _refreshed_already=True)
            if exc.code < 500 or attempt == _MAX_ATTEMPTS:
                detail = exc.read().decode("utf-8", errors="replace")
                raise DaemonApiError(f"{method} {path} -> HTTP {exc.code}: {detail[:300]}") from exc
            last_exc = exc
        except urllib.error.URLError as exc:
            if attempt == _MAX_ATTEMPTS:
                raise DaemonApiError(f"{method} {path} -> connection failed: {exc.reason}") from exc
            last_exc = exc
        log(f"  (transient error on attempt {attempt}/{_MAX_ATTEMPTS} for {method} {path}, retrying: {last_exc})")
        time.sleep(_RETRY_DELAY_S)

    raise DaemonApiError(f"{method} {path} -> failed after {_MAX_ATTEMPTS} attempts: {last_exc}")


def fetch_requested_work_orders(api_url: str, session: TokenSession) -> list[dict]:
    """GET /api/work-orders/me (existing, user-scoped endpoint — no new
    endpoint needed, see the plan) then filters/sorts client-side: only
    status == 'queued' with daemon_run_requested_at set, oldest request
    first. No cross-user query exists or is needed — the daemon only ever
    sees the work orders belonging to whoever's session it's running with."""
    orders = call_api(api_url, session, "GET", "/api/work-orders/me")
    requested = [
        o for o in orders
        if o.get("status") == "queued" and o.get("daemon_run_requested_at")
    ]
    requested.sort(key=lambda o: o["daemon_run_requested_at"])
    return requested


def claim(api_url: str, session: TokenSession, work_order_id: str) -> bool:
    """Clears daemon_run_requested_at back to null BEFORE anything is
    started — the actual mechanism that makes a crash mid-claim or a
    second poll cycle unable to double-start the same work order (see
    module docstring). Returns False (and logs, doesn't raise) on failure
    so a transient claim failure just leaves the work order to be retried
    on the next poll instead of crashing the daemon."""
    try:
        call_api(api_url, session, "PATCH", f"/api/work-orders/{work_order_id}",
                  {"daemon_run_requested_at": None})
        return True
    except DaemonApiError as exc:
        log(f"WARNUNG: konnte Work Order {work_order_id} nicht claimen, überspringe diesen Zyklus: {exc}")
        return False


def run_one(args: argparse.Namespace, session: TokenSession, work_order_id: str) -> int:
    """Invokes run_work_order.py --mode execute exactly as a human would
    type it — this subprocess.run() call, and nothing else in this file,
    is where the actual work happens. Blocking: the daemon does not poll
    again or start a second work order until this one returns, matching
    the plan's "sequential, one at a time" design.

    Passes session.access_token — the freshest one at the moment THIS work
    order starts, not whatever was current at daemon startup (matters once
    the daemon has been running long enough to have refreshed at least
    once). See the module docstring's "Known limitation" for what this
    does NOT cover (a single execution outliving one token's lifetime)."""
    cmd = [
        sys.executable, str(RUN_WORK_ORDER_SCRIPT), work_order_id,
        "--mode", "execute",
        "--adapter", args.adapter,
        "--max-budget-usd", str(args.max_budget_usd),
        "--api-url", args.api_url,
        "--token", session.access_token,
    ]
    if args.per_step:
        cmd.append("--per-step")

    log(f"Starte Work Order {work_order_id}: {' '.join(cmd[:2])} ... --adapter {args.adapter} --max-budget-usd {args.max_budget_usd}{' --per-step' if args.per_step else ''}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    log(f"Work Order {work_order_id} beendet (exit_code={result.returncode})")
    return result.returncode


def poll_once(args: argparse.Namespace, session: TokenSession) -> None:
    try:
        requested = fetch_requested_work_orders(args.api_url, session)
    except DaemonApiError as exc:
        log(f"WARNUNG: konnte Work Orders nicht abrufen, versuche es im nächsten Zyklus erneut: {exc}")
        return

    if not requested:
        return

    log(f"{len(requested)} Work Order(s) angefragt — verarbeite älteste zuerst, sequentiell.")
    for order in requested:
        work_order_id = order["id"]
        if not claim(args.api_url, session, work_order_id):
            continue
        run_one(args, session, work_order_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adapter", default="manual_prompt",
                          help="RunnerAdapter every claimed work order runs with — fixed for the daemon's "
                               "whole lifetime, not chosen per work order. Typically claude_code or "
                               "claude_code_sandboxed (manual_prompt has no execute() to run autonomously).")
    parser.add_argument("--max-budget-usd", type=float, default=None,
                          help="Required before this daemon will start any work order with a credit-consuming "
                               "adapter — passed straight through to run_work_order.py's own mandatory budget "
                               "gate. No default is ever assumed here either.")
    parser.add_argument("--per-step", action="store_true",
                          help="Passed through to every run_work_order.py invocation — see that script's "
                               "--per-step. Only adapters with supports_step_execution=True accept it.")
    parser.add_argument("--poll-interval", type=float, default=15.0,
                          help="Seconds between poll cycles (default 15, matching the existing "
                               "ProgressReporter/should_stop() cadence elsewhere in this system).")
    parser.add_argument("--api-url", default=os.environ.get("COMMANDPILOT_API_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("COMMANDPILOT_API_TOKEN"),
                          help="Plain access token — expires in ~1h, no auto-refresh. Prefer --refresh-token "
                               "for anything you leave running.")
    parser.add_argument("--refresh-token", default=os.environ.get("COMMANDPILOT_REFRESH_TOKEN"),
                          help="Supabase refresh token — the daemon mints and silently re-mints its own access "
                               "token from this, on startup and on every 401. Needs --supabase-url/"
                               "--supabase-anon-key too (both auto-discovered from frontend/.env.local if omitted).")
    parser.add_argument("--supabase-url", default=os.environ.get("COMMANDPILOT_SUPABASE_URL")
                          or _read_frontend_env_local("NEXT_PUBLIC_SUPABASE_URL"))
    parser.add_argument("--supabase-anon-key", default=os.environ.get("COMMANDPILOT_SUPABASE_ANON_KEY")
                          or _read_frontend_env_local("NEXT_PUBLIC_SUPABASE_ANON_KEY"))
    parser.add_argument("--session-file", type=Path, default=DEFAULT_SESSION_FILE,
                          help="Where the rotated refresh token is cached between runs "
                               f"(default: {DEFAULT_SESSION_FILE.name}, repo root, gitignored).")
    parser.add_argument("--pair", action="store_true",
                          help="One-time setup: pair this machine as a runner via a short code you approve in "
                               "the logged-in web app, no token to copy. Run this once, then run the daemon "
                               "normally (no --pair) — see the module docstring's auth mode (a).")
    parser.add_argument("--runner-token-file", type=Path, default=DEFAULT_RUNNER_TOKEN_FILE,
                          help="Where --pair saves its result and where normal startup loads it from "
                               f"(default: {DEFAULT_RUNNER_TOKEN_FILE.name}, repo root, gitignored).")
    parser.add_argument("--frontend-url", default=os.environ.get("COMMANDPILOT_FRONTEND_URL")
                          or _read_frontend_env_local("NEXT_PUBLIC_FRONTEND_URL") or FRONTEND_URL_DEFAULT,
                          help="Only used by --pair, to tell you where to approve the code.")
    args = parser.parse_args()

    if args.pair:
        return run_pairing_flow(args.api_url, args.frontend_url, args.runner_token_file)

    # Resolution order: explicit --token first, then a paired runner token
    # (mode a — no expiry, nothing to refresh), then the refresh-token flow
    # (mode c) — explicit flag/env first, then whatever a previous run
    # cached, so a RESTART doesn't need a fresh manual paste either.
    if not args.token and args.runner_token_file.exists():
        try:
            cached_runner = json.loads(args.runner_token_file.read_text(encoding="utf-8"))
            args.token = cached_runner.get("runner_token")
            if args.token:
                log(f"Gepaarten Runner-Token aus {args.runner_token_file} geladen.")
        except (OSError, json.JSONDecodeError) as exc:
            log(f"WARNUNG: konnte {args.runner_token_file} nicht lesen, ignoriere: {exc}")

    seed_refresh_token = args.refresh_token
    if not seed_refresh_token and args.session_file.exists():
        try:
            cached = json.loads(args.session_file.read_text(encoding="utf-8"))
            seed_refresh_token = cached.get("refresh_token")
            if seed_refresh_token:
                log(f"Refresh Token aus {args.session_file} geladen (vorheriger Lauf).")
        except (OSError, json.JSONDecodeError) as exc:
            log(f"WARNUNG: konnte {args.session_file} nicht lesen, ignoriere Cache: {exc}")

    session = TokenSession(
        access_token=args.token,
        refresh_token=seed_refresh_token,
        supabase_url=args.supabase_url,
        supabase_anon_key=args.supabase_anon_key,
        session_file=args.session_file,
    )

    if not session.access_token and not session.can_refresh:
        print("ERROR: not connected yet. Run 'python scripts/run_work_order_daemon.py --pair' once "
              "(no token to copy — you approve a short code in the logged-in web app).", file=sys.stderr)
        print("Alternatively: --token, or --refresh-token (+ --supabase-url/--supabase-anon-key, "
              "auto-discovered from frontend/.env.local if that file exists) for a self-renewing session.",
              file=sys.stderr)
        print("See docs/background-dev-team-runbook.md §1 for how to obtain either of those manually.", file=sys.stderr)
        return 1

    if session.can_refresh:
        try:
            session.refresh()
        except DaemonApiError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if not RUN_WORK_ORDER_SCRIPT.exists():
        print(f"ERROR: {RUN_WORK_ORDER_SCRIPT} not found.", file=sys.stderr)
        return 1

    try:
        adapter_info = get_adapter(args.adapter).info
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if adapter_info.supports_auto_execute == "no":
        # Without this check, a work order "Autonom starten"-triggered against
        # this adapter would silently no-op: claim() clears the trigger, then
        # run_work_order.py's own guard (execute mode requires an adapter with
        # an execute()) rejects it before creating any agent_run/activity_log
        # row — the work order just reverts to plain 'queued' with zero trace,
        # and a user watching the UI sees the "Autonom starten" button
        # reappear with no explanation. Fail loudly here instead, once, at
        # daemon startup, where a human is actually watching the terminal.
        print(
            f"ERROR: --adapter {args.adapter!r} has supports_auto_execute='no' — it cannot run "
            "autonomously triggered work orders (no execute() to call). Use --adapter claude_code "
            "or --adapter claude_code_sandboxed. Available adapters: " + ", ".join(ADAPTERS),
            file=sys.stderr,
        )
        return 1

    log(
        f"Daemon gestartet — adapter={args.adapter}, max_budget_usd={args.max_budget_usd}, "
        f"per_step={args.per_step}, poll_interval={args.poll_interval}s, "
        f"session={'selbst-erneuernd' if session.can_refresh else 'statisch (läuft ohne Refresh Token ab)'}. "
        f"Strg+C zum Beenden."
    )
    try:
        while True:
            poll_once(args, session)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        log("Beende (Strg+C) — laufende Work Orders werden nicht abgebrochen, nur keine neuen mehr gestartet.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
