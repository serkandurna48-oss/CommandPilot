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
    python scripts/run_work_order_daemon.py --adapter claude_code --max-budget-usd 0.20
    python scripts/run_work_order_daemon.py --adapter claude_code_sandboxed --max-budget-usd 0.50 --per-step
    python scripts/run_work_order_daemon.py --adapter claude_code --max-budget-usd 0.20 --poll-interval 30

Auth: same as run_work_order.py — --token or COMMANDPILOT_API_TOKEN, your
own Supabase session token. Sees only your own work orders (GET
/api/work-orders/me is user-scoped) — this is inherently a per-user, local,
opt-in process, not a shared service.

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

_MAX_ATTEMPTS = 3
_RETRY_DELAY_S = 1.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}")


class DaemonApiError(Exception):
    """Same shape/intent as import_work_order_result.py's ImportError_ —
    raised for a single failed API call, caught per-call so one bad request
    doesn't crash the whole poll loop."""


def call_api(api_url: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    """Same retry posture as import_work_order_result.py's call_api(): only
    5xx/connection-level failures are retried (a real backend hiccup), 4xx
    is never retried (a 401/404 means something's actually wrong)."""
    url = f"{api_url.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
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


def fetch_requested_work_orders(api_url: str, token: str) -> list[dict]:
    """GET /api/work-orders/me (existing, user-scoped endpoint — no new
    endpoint needed, see the plan) then filters/sorts client-side: only
    status == 'queued' with daemon_run_requested_at set, oldest request
    first. No cross-user query exists or is needed — the daemon only ever
    sees the work orders belonging to whoever's token it's running with."""
    orders = call_api(api_url, token, "GET", "/api/work-orders/me")
    requested = [
        o for o in orders
        if o.get("status") == "queued" and o.get("daemon_run_requested_at")
    ]
    requested.sort(key=lambda o: o["daemon_run_requested_at"])
    return requested


def claim(api_url: str, token: str, work_order_id: str) -> bool:
    """Clears daemon_run_requested_at back to null BEFORE anything is
    started — the actual mechanism that makes a crash mid-claim or a
    second poll cycle unable to double-start the same work order (see
    module docstring). Returns False (and logs, doesn't raise) on failure
    so a transient claim failure just leaves the work order to be retried
    on the next poll instead of crashing the daemon."""
    try:
        call_api(api_url, token, "PATCH", f"/api/work-orders/{work_order_id}",
                  {"daemon_run_requested_at": None})
        return True
    except DaemonApiError as exc:
        log(f"WARNUNG: konnte Work Order {work_order_id} nicht claimen, überspringe diesen Zyklus: {exc}")
        return False


def run_one(args: argparse.Namespace, work_order_id: str) -> int:
    """Invokes run_work_order.py --mode execute exactly as a human would
    type it — this subprocess.run() call, and nothing else in this file,
    is where the actual work happens. Blocking: the daemon does not poll
    again or start a second work order until this one returns, matching
    the plan's "sequential, one at a time" design."""
    cmd = [
        sys.executable, str(RUN_WORK_ORDER_SCRIPT), work_order_id,
        "--mode", "execute",
        "--adapter", args.adapter,
        "--max-budget-usd", str(args.max_budget_usd),
        "--api-url", args.api_url,
        "--token", args.token,
    ]
    if args.per_step:
        cmd.append("--per-step")

    log(f"Starte Work Order {work_order_id}: {' '.join(cmd[:2])} ... --adapter {args.adapter} --max-budget-usd {args.max_budget_usd}{' --per-step' if args.per_step else ''}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    log(f"Work Order {work_order_id} beendet (exit_code={result.returncode})")
    return result.returncode


def poll_once(args: argparse.Namespace) -> None:
    try:
        requested = fetch_requested_work_orders(args.api_url, args.token)
    except DaemonApiError as exc:
        log(f"WARNUNG: konnte Work Orders nicht abrufen, versuche es im nächsten Zyklus erneut: {exc}")
        return

    if not requested:
        return

    log(f"{len(requested)} Work Order(s) angefragt — verarbeite älteste zuerst, sequentiell.")
    for order in requested:
        work_order_id = order["id"]
        if not claim(args.api_url, args.token, work_order_id):
            continue
        run_one(args, work_order_id)


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
    parser.add_argument("--token", default=os.environ.get("COMMANDPILOT_API_TOKEN"))
    args = parser.parse_args()

    if not args.token:
        print("ERROR: no API token. Pass --token or set COMMANDPILOT_API_TOKEN.", file=sys.stderr)
        print("See docs/background-dev-team-runbook.md §1 for how to obtain one.", file=sys.stderr)
        return 1

    if not RUN_WORK_ORDER_SCRIPT.exists():
        print(f"ERROR: {RUN_WORK_ORDER_SCRIPT} not found.", file=sys.stderr)
        return 1

    log(
        f"Daemon gestartet — adapter={args.adapter}, max_budget_usd={args.max_budget_usd}, "
        f"per_step={args.per_step}, poll_interval={args.poll_interval}s. Strg+C zum Beenden."
    )
    try:
        while True:
            poll_once(args)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        log("Beende (Strg+C) — laufende Work Orders werden nicht abgebrochen, nur keine neuen mehr gestartet.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
