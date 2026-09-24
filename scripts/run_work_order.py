#!/usr/bin/env python3
"""Local runner harness for the Background Dev Team control plane.

CommandPilot is the Control Plane (work orders, approval scopes, steps,
activity log, review packages — all persisted server-side). It orchestrates
RunnerAdapters; it does not become a coding agent itself. Execution always
happens on the Execution Plane — a human running this script on their own
machine, whether that's fully manual (manual_prompt), the local `claude`
CLI directly (claude_code, semi_auto), or the same CLI fully unattended
inside a disposable Docker container + git worktree
(claude_code_sandboxed, supports_auto_execute="yes" — see that adapter's
module docstring for the safety argument). Codex/OpenClaw adapters are
still architectural placeholders. See scripts/runner_adapters/ and
docs/runner-adapter-contract.md.

Three modes, each delegating the adapter-specific parts to whichever
--adapter was chosen (default: manual_prompt):

  --mode prompt-file
      Fetches a work order, runs hard safety preconditions (harness-level
      AND adapter-level), sets it to "running" (+ its first step), and has
      the adapter prepare() whatever it needs (e.g. a ready-to-paste
      prompt) in a local session folder.

  --mode import-result
      Has the adapter collect_result() a runner's result JSON, then writes
      it into CommandPilot via scripts/import_work_order_result.py (reused,
      not duplicated).

  --mode execute   (optional, explicit opt-in only)
      With --runner-command: does everything prompt-file does, then runs
      YOUR shell command (never a default) and best-effort auto-imports a
      detected result JSON — this generic path works with any adapter.
      Without --runner-command: delegates to the adapter's own execute()
      (adapter-native invocation) — only meaningful for adapters with
      supports_auto_execute != "no".

Budget gate (OP-ClaudeBudgetGate-001): --mode execute against an adapter
that spends real money on its own initiative (claude_code today;
info.consumes_paid_credits) refuses to run at all unless a budget is
explicitly set — via --max-budget-usd or the COMMANDPILOT_CLAUDE_MAX_BUDGET_USD
env var. No default is ever assumed here; CommandPilot must never silently
burn usage credits. --mode prompt-file (writes files only) and
manual_prompt (never calls a paid API itself) are unaffected by this gate.

Zero third-party dependencies (stdlib only), matching
scripts/import_work_order_result.py's precedent.

Usage:
    python scripts/run_work_order.py <work_order_id> --mode prompt-file
    python scripts/run_work_order.py <work_order_id> --mode import-result
    python scripts/run_work_order.py <work_order_id> --mode execute --runner-command "claude --print < {prompt_file}"
    python scripts/run_work_order.py <work_order_id> --mode prompt-file --adapter claude_code
    python scripts/run_work_order.py <work_order_id> --mode execute --adapter claude_code --max-budget-usd 0.20

Auth: same as import_work_order_result.py — --token or COMMANDPILOT_API_TOKEN,
your own Supabase session token. See docs/background-dev-team-runbook.md.
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

# Windows consoles often default to a legacy codepage (cp1252) rather than
# UTF-8 — a plain print() of arbitrary runner/prompt text (em dashes,
# arrows, German umlauts) then crashes with UnicodeEncodeError. Also applied
# by import_work_order_result.py (imported below); repeated here explicitly
# (idempotent) so this file doesn't rely on that import happening first.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Import the existing recorder script as a module — reuse its call_api/
# import_result logic rather than duplicating it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_work_order_result import ImportError_, call_api, import_result, review_package_payload  # noqa: E402
from runner_adapters import ADAPTERS, RunnerAdapter, get_adapter  # noqa: E402
from runner_adapters.base import (  # noqa: E402
    ProgressReporter,
    extract_json_result,
    find_blocked_keyword,
    parse_and_validate_step_result,
    validate_result_against_order,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where cmd_prompt_file() records the AgentRun it created for this session,
# so a later (often separate-process) --mode import-result invocation can
# find it again and close it out (OP-Runner-Session-001). Deliberately a
# small standalone file rather than piggy-backing on run.log (plaintext,
# append-only, not meant to be parsed back) or prompt.md (adapter-owned).
_AGENT_RUN_STATE_FILENAME = "agent_run.json"

# CP-OP02: the bounded auto-retry loop in --mode execute tries at most this
# many attempts total (the first attempt plus up to 2 retries) before
# finalizing the work order as 'failed' and requiring human intervention.
# Retrying is scoped to harness-detected TECHNICAL failures only — an
# exception from adapter.execute(), or a run that produced no usable result
# JSON at all. A valid runner-reported result (any finalStatus) is never
# retried, and a retry never happens if the working tree changed during the
# failed attempt (see _worktree_changed()).
_MAX_TECHNICAL_ATTEMPTS = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_dir(work_order_id: str) -> Path:
    d = REPO_ROOT / "tmp" / "work-order-runs" / work_order_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_agent_run_state(session_path: Path, agent_run_id: str, adapter_name: str, mode: str) -> None:
    state = {"agent_run_id": agent_run_id, "adapter": adapter_name, "mode": mode, "recorded_at": now_iso()}
    (session_path / _AGENT_RUN_STATE_FILENAME).write_text(json.dumps(state, indent=2), encoding="utf-8")


def read_agent_run_id(session_path: Path) -> str | None:
    """Best-effort: a missing or unreadable state file just means this
    import isn't tied to a prompt-file-created AgentRun (e.g. an older
    session predating this feature, or a manually-assembled result.json)
    — not a reason to fail the import."""
    path = session_path / _AGENT_RUN_STATE_FILENAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("agent_run_id")
    except (json.JSONDecodeError, OSError):
        return None


def log_line(session_path: Path, message: str) -> None:
    line = f"[{now_iso()}] {message}"
    print(line)
    with open(session_path / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_work_order(api_url: str, token: str, work_order_id: str) -> dict:
    url = f"{api_url.rstrip('/')}/api/work-orders/{work_order_id}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET /api/work-orders/{work_order_id} -> HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET /api/work-orders/{work_order_id} -> connection failed: {exc.reason}") from exc


# Human-readable reasons per non-startable status, shown when --force is not
# passed. Every status in WorkOrderStatusLiteral is covered explicitly so a
# new status added later fails loudly (missing-key default below) instead
# of silently allowing a start from an unconsidered state.
_STATUS_BLOCK_REASONS = {
    "draft": "noch nicht genehmigt — erst im UI auf 'Genehmigen' klicken, dann 'Als eingereiht markieren'.",
    "running": "läuft bereits. Nutze --force nur für einen Neustart — nicht nötig, wenn der Runner selbst schon läuft.",
    "accepted": "bereits akzeptiert — dieser Run ist abgeschlossen.",
    "cancelled": "abgebrochen — dieser Run ist beendet.",
    "review_ready": "wartet bereits auf menschliches Review — erst Accept/Rework entscheiden.",
    "rework_requested": "Überarbeitung angefordert — erst im UI klären, bevor neu gestartet wird.",
    "blocked": "blockiert — Activity Log/Steps prüfen, bevor neu gestartet wird.",
    "needs_approval": "wartet auf Freigabe — erst im UI klären.",
    "failed": "fehlgeschlagen — Review Package/Log prüfen, bevor neu gestartet wird.",
}


def validate_preconditions(order: dict, force: bool) -> list[str]:
    """Harness-level, adapter-agnostic hard checks on the work order itself
    (its approval scope, ticket plan, status) — run regardless of which
    adapter was chosen. Any non-empty return aborts the run before anything
    is mutated. See RunnerAdapter.check_scope_errors() for the
    complementary, adapter-specific half of this gate."""
    errors: list[str] = []
    scope = order.get("approval_scope")
    steps = order.get("steps") or []
    status = order.get("status")

    if not scope:
        errors.append("Kein Approval Scope vorhanden — Start verweigert.")
    else:
        if not scope.get("blocked_actions"):
            errors.append("Approval Scope hat eine leere blocked_actions-Liste — sicherheitskritisch, Start verweigert.")
        for action in list(scope.get("allowed_actions", [])) + list(scope.get("requires_approval", [])):
            hit = find_blocked_keyword(action)
            if hit:
                errors.append(
                    f"'{action}' sieht wie eine blockierte Aktion aus (Treffer: '{hit}') "
                    "und steht in allowed_actions/requires_approval statt blocked_actions."
                )

    if not steps:
        errors.append("Keine Steps im Ticketplan vorhanden — Start verweigert.")

    if not order.get("time_limit_minutes"):
        errors.append("time_limit_minutes fehlt oder ist 0.")

    if not force and status not in ("approved", "queued"):
        reason = _STATUS_BLOCK_REASONS.get(status, f"Status '{status}' ist kein bekannter Startzustand.")
        errors.append(f"Status ist '{status}' — {reason}")

    return errors


_CODE_CHANGE_KEYWORDS = ("ändern", "aendern", "change", "edit", "code", "implement")


def _mentions_code_change(scope: dict) -> bool:
    allowed = scope.get("allowed_actions", [])
    return any(kw in a.lower() for a in allowed for kw in _CODE_CHANGE_KEYWORDS)


def check_warnings(order: dict) -> list[str]:
    """Harness-level, non-blocking. Printed, but the run proceeds. This is
    the --mode prompt-file posture: a human is about to read the prompt
    before anything happens, so a warning is enough. --mode execute (real
    or adapter-native auto-execution) uses the stricter, blocking sibling
    below instead — see check_execute_path_safety()."""
    warnings: list[str] = []
    scope = order.get("approval_scope") or {}
    if _mentions_code_change(scope) and not scope.get("allowed_paths"):
        warnings.append(
            "allowed_actions erlaubt Code-/Dateiänderungen, aber allowed_paths ist leer — "
            "der Runner hat keine Pfad-Einschränkung, in welchen Verzeichnissen er arbeiten darf."
        )
    return warnings


def check_execute_path_safety(order: dict, force: bool) -> list[str]:
    """Hard, blocking — but only for actual auto-execution (--mode execute),
    never for --mode prompt-file (see check_warnings(), which only warns
    there). Nothing constrains *where* an auto-executing runner writes if
    allowed_paths is empty while code changes are allowed — for a run a
    human isn't watching turn-by-turn, that's a real gap, not just a
    formality. --force overrides this specific check only."""
    if force:
        return []
    scope = order.get("approval_scope") or {}
    if _mentions_code_change(scope) and not scope.get("allowed_paths"):
        return [
            "Automatische Ausführung erlaubt Code-Änderungen, aber allowed_paths ist leer — ohne "
            "Pfad-Einschränkung dürfte der Runner überall im Repo schreiben. Setze allowed_paths im "
            "Approval Scope, oder nutze --force, um das bewusst zu übergehen."
        ]
    return []


def _agent_run_role(order: dict) -> str:
    """Anchors a new AgentRun's role on the first ticketplan step's role
    (same anchor cmd_prompt_file's first-step PATCH uses), falling back to
    "coder" if the work order has no ticketplan at all. Shared by
    cmd_prompt_file() and the CP-OP02 retry loop so a retry's AgentRun uses
    the same convention as the initial one."""
    steps = order.get("steps") or []
    return steps[0]["assigned_role"] if steps else "coder"


def _current_status(args: argparse.Namespace) -> str | None:
    """Fresh work-order status check (CP-OP02 cancellation gate). Returns
    None — rather than raising — on a fetch failure, so a transient network
    blip during a long-running retry sequence doesn't itself abort the run;
    callers only stop the loop on an explicit 'cancelled' status, never on
    "couldn't check" (the retry loop already fails closed on *working-tree*
    uncertainty — see _worktree_changed() — status-check uncertainty is a
    different, non-safety-critical failure mode and is only warned about)."""
    try:
        return fetch_work_order(args.api_url, args.token, args.work_order_id).get("status")
    except RuntimeError as exc:
        print(f"WARNUNG: konnte aktuellen Work-Order-Status nicht abrufen: {exc}", file=sys.stderr)
        return None


# How often (seconds) a live progress tick / cancellation poll is actually
# allowed through to the API per adapter.execute() call — matches the
# adapter-side (claude_code.py) poll cadence this replaces/extends. Adapters
# may call report_progress()/should_stop() far more often than this; rate-
# limiting is the harness's job (ProgressReporter contract), not theirs.
_PROGRESS_MIN_INTERVAL_S = 15.0


def make_progress_reporter(args: argparse.Namespace, session_path: Path, agent_run_id: str | None) -> ProgressReporter:
    """Builds the ProgressReporter passed into adapter.execute() (CP live-
    execution feature) out of the existing POST .../activity-log and
    GET /work-orders/{id} endpoints — no new endpoints needed. Rate-limited
    to _PROGRESS_MIN_INTERVAL_S so an adapter's own tight poll loop can call
    both freely without flooding the API. Both callables are best-effort and
    never raise into the adapter: a report failure just logs a local
    warning; a status-check failure conservatively reports "not stopped"
    (an unreachable API must never itself be interpreted as a stop request).
    """
    state = {"last_report": 0.0, "last_stop_check": 0.0, "cached_stop": False}

    def report_progress(message: str) -> None:
        now = time.monotonic()
        if now - state["last_report"] < _PROGRESS_MIN_INTERVAL_S:
            return
        state["last_report"] = now
        log_line(session_path, f"[progress] {message}")
        payload: dict[str, Any] = {"level": "info", "event_type": "progress_tick", "message": message[:2000]}
        if agent_run_id:
            payload["agent_run_id"] = agent_run_id
        try:
            call_api(
                args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/activity-log",
                payload, dry_run=args.dry_run,
            )
        except ImportError_ as exc:
            log_line(session_path, f"WARNUNG: konnte Progress-ActivityLog nicht schreiben: {exc}")

    def should_stop() -> bool:
        now = time.monotonic()
        if now - state["last_stop_check"] < _PROGRESS_MIN_INTERVAL_S:
            return state["cached_stop"]
        state["last_stop_check"] = now
        state["cached_stop"] = _current_status(args) == "cancelled"
        return state["cached_stop"]

    return ProgressReporter(report_progress=report_progress, should_stop=should_stop)


def _target_worktree() -> Path:
    """Where the adapter's subprocess actually runs — for the CP-OP02
    working-tree-safety check, this is deliberately NOT REPO_ROOT.
    REPO_ROOT is fixed by this script's own file location (CommandPilot's
    repo), but a cross-repo work order's runner is expected to operate
    against a different repo (order.target_repo_path is prompt/display
    context only, see build_runner_prompt() — CommandPilot itself never cds
    anywhere). scripts/runner_adapters/claude_code.py's execute() spawns its
    subprocess via subprocess.Popen() with no explicit cwd=, so it inherits
    whatever directory the harness process itself was started in — i.e.
    Path.cwd(). Snapshotting Path.cwd() instead of REPO_ROOT means the
    safety check always looks at the exact worktree the adapter is about to
    touch, whether that's CommandPilot itself (the common case, where
    Path.cwd() == REPO_ROOT because the runbook says to invoke this script
    from the CommandPilot repo root) or a different target repo the human
    invoked this harness from within."""
    return Path.cwd()


def _git_snapshot(cwd: Path) -> tuple[str, str] | None:
    """(HEAD sha, working-tree status) for cwd, or None if it can't be
    determined at all (not a git repo, git missing from PATH, timeout, ...).
    CP-OP02's retry-safety check (_worktree_changed) treats None as
    "unknown" and fails closed — an undeterminable working-tree state is
    treated exactly like a changed one, never like an unchanged one."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=10
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=cwd, capture_output=True, text=True, timeout=10
        )
        if head.returncode != 0 or status.returncode != 0:
            return None
        return head.stdout.strip(), status.stdout
    except Exception:
        return None


def _worktree_changed(before: tuple[str, str] | None, after: tuple[str, str] | None) -> bool:
    """True if the working tree looks different after an attempt than
    before it started — OR if either snapshot couldn't be taken. A
    technical failure with a changed (or undeterminable) working tree must
    never be auto-retried (CP-OP02): retrying against a repo state the
    failed attempt already modified risks compounding a half-finished
    change instead of cleanly re-trying from the same starting point. Fail
    closed: "unknown" is treated the same as "changed"."""
    if before is None or after is None:
        return True
    return before != after


def _finalize_technical_failure(
    args: argparse.Namespace, session_path: Path, run_id: str | None, reason: str, detail: str
) -> None:
    """Closes out the current attempt's AgentRun as failed and transitions
    the work order to 'failed' via PATCH /work-orders/{id} (routed through
    transition_work_order(), CP-OP01) with source='harness' and the given
    short reason code — the RPC writes its own audit-log entry atomically
    with the status change. Also posts a richer, human-readable
    activity-log entry with the full diagnostic detail, since the
    transition's own audit entry only carries the short reason code.
    Degrades to warnings (never raises) if the work order was concurrently
    moved to some other terminal status (e.g. a human clicked Cancel while
    this was running) — that PATCH failing with illegal_transition is an
    expected race, not a bug."""
    if run_id:
        try:
            call_api(
                args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/agent-runs/{run_id}",
                {"status": "failed", "output_summary": detail[:2000]}, dry_run=args.dry_run,
            )
        except ImportError_ as exc:
            log_line(session_path, f"WARNUNG: konnte AgentRun {run_id} nicht auf failed setzen: {exc}")
    try:
        call_api(
            args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/activity-log",
            {"level": "error", "event_type": "auto_retry_exhausted", "message": detail[:2000], "agent_run_id": run_id},
            dry_run=args.dry_run,
        )
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte Activity-Log nicht schreiben: {exc}")
    try:
        call_api(
            args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}",
            {"status": "failed", "source": "harness", "reason": reason}, dry_run=args.dry_run,
        )
        log_line(session_path, f"Work Order -> failed (Grund: {reason})")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte Work Order nicht auf failed setzen (evtl. bereits in anderem Endzustand): {exc}")
        print(f"WARNUNG: {exc}", file=sys.stderr)


def _terminalize_cancelled_run(args: argparse.Namespace, session_path: Path, run_id: str | None, detail: str) -> None:
    """Closes out the given AgentRun (if any) when the harness stops
    because the work order was cancelled out from under it — no AgentRun
    may be left sitting on 'running' forever just because the harness gave
    up early (CP-OP02 correction). Uses 'failed', not a new status:
      - not 'completed' — nothing was actually recorded/applied for this
        run (even if a valid result was obtained, it was deliberately never
        imported once cancellation was seen).
      - not 'blocked' — 'blocked' means paused pending a human decision to
        CONTINUE this same run; a cancelled work order has no "continue"
        left, there is nothing to resume.
      - 'failed' is the closest existing terminal meaning: this run did not
        finish successfully. The output_summary text ("... cancelled ...")
        distinguishes this from a genuine technical failure for anyone
        reading the Activity Log/Agent Runs UI.
    Never touches work_orders.status — the work order is already in
    whatever terminal-for-this-purpose state got it cancelled; this only
    prevents its AgentRun from being stuck open."""
    if not run_id:
        return
    try:
        call_api(
            args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/agent-runs/{run_id}",
            {"status": "failed", "output_summary": detail[:2000]}, dry_run=args.dry_run,
        )
        log_line(session_path, f"AgentRun {run_id} -> failed (Work Order cancelled)")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte AgentRun {run_id} nach Cancellation nicht auf failed setzen: {exc}")


def _mark_running_step_interrupted(args: argparse.Namespace, session_path: Path, order: dict, detail: str) -> None:
    """Best-effort: marks the step cmd_prompt_file() set to 'running' (the
    first ticketplan step — the only one this harness tracks individually;
    the rest are only ever resolved via the runner's own result.json) as
    'failed' with a blocked_reason explaining the user-requested stop, so
    the UI's step list doesn't show a step stuck on 'running' forever after
    an interrupt. Never raises — a failure here is logged only, matching
    every other best-effort PATCH in this file."""
    steps = order.get("steps") or []
    if not steps:
        return
    first_step = steps[0]
    try:
        call_api(
            args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/steps/{first_step['id']}",
            {"status": "failed", "blocked_reason": "Vom Nutzer unterbrochen"}, dry_run=args.dry_run,
        )
        log_line(session_path, f"Step '{first_step['title']}' ({first_step['id']}) -> failed (Vom Nutzer unterbrochen)")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte Step nach Unterbrechung nicht auf failed setzen: {exc}")


def _mark_step_interrupted(args: argparse.Namespace, session_path: Path, step: dict, detail: str) -> None:
    """Per-step sibling of _mark_running_step_interrupted() — the --per-step
    path (_run_step_by_step()) always knows exactly which step was running
    when should_stop() fired, so no first-step-only heuristic is needed
    here, unlike the whole-order path this mirrors."""
    try:
        call_api(
            args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/steps/{step['id']}",
            {"status": "failed", "blocked_reason": "Vom Nutzer unterbrochen"}, dry_run=args.dry_run,
        )
        log_line(session_path, f"Step '{step['title']}' ({step['id']}) -> failed (Vom Nutzer unterbrochen)")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte Step nach Unterbrechung nicht auf failed setzen: {exc}")


def _run_adapter_with_bounded_retry(
    args: argparse.Namespace,
    adapter: RunnerAdapter,
    order: dict,
    session_path: Path,
    total_budget: float | None,
    initial_agent_run_id: str | None,
) -> int:
    """CP-OP02: drives up to _MAX_TECHNICAL_ATTEMPTS calls to
    adapter.execute(). Retries ONLY on a harness-detected technical failure
    — an exception from adapter.execute(), or a call that returned without
    raising but produced no usable result JSON at all (e.g. a timeout). A
    valid, structured runner result is handed straight to cmd_import_result()
    and never retried, regardless of its finalStatus — blocked/failed are a
    runner telling us something real, not a technical hiccup.

    work_orders.status stays 'running' for the entire sequence: auto-retry
    is deliberately not a work_order status transition (CP-OP01's state
    machine has no notion of retries). Each attempt gets its own AgentRun
    row (attempt_number/retry_reason) so the retry history stays visible.

    total_budget, if not None, is a CUMULATIVE ceiling across every attempt
    in this call — the per-attempt budget passed to adapter.execute() is
    whatever remains after previously-reported spend, never the full amount
    again. If an attempt doesn't report its actual cost, the entire
    remaining budget for that attempt is conservatively assumed spent, so
    the sum can never exceed total_budget even for a cost-silent adapter.
    """
    spent_so_far = 0.0
    run_id = initial_agent_run_id

    for attempt in range(1, _MAX_TECHNICAL_ATTEMPTS + 1):
        if _current_status(args) == "cancelled":
            detail = f"Work Order ist cancelled — kein weiterer Runner-Start (vor Attempt {attempt})."
            log_line(session_path, detail)
            print("Work Order wurde cancelled — breche ab, kein weiterer Runner-Start.")
            _terminalize_cancelled_run(args, session_path, run_id, detail)
            return 0

        remaining_budget: float | None = None
        if total_budget is not None:
            remaining_budget = round(max(total_budget - spent_so_far, 0.0), 4)
            if remaining_budget <= 0:
                detail = (
                    f"Gesamtbudget ${total_budget} durch vorherige Attempts aufgebraucht — "
                    f"Attempt {attempt}/{_MAX_TECHNICAL_ATTEMPTS} wird nicht mehr gestartet."
                )
                log_line(session_path, detail)
                _finalize_technical_failure(args, session_path, run_id, "technical_failure_budget_exhausted", detail)
                return 1

        before = _git_snapshot(_target_worktree())
        budget_note = f" (Budget verbleibend: ${remaining_budget})" if remaining_budget is not None else ""
        log_line(session_path, f"Attempt {attempt}/{_MAX_TECHNICAL_ATTEMPTS} — starte adapter.execute(){budget_note}")

        progress = make_progress_reporter(args, session_path, run_id)

        outcome = None
        exec_error: Exception | None = None
        try:
            outcome = adapter.execute(order, session_path, None, max_budget_usd=remaining_budget, progress=progress)
        except NotImplementedError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001 — any adapter failure here is a technical failure by definition
            exec_error = exc
            log_line(session_path, f"FEHLER bei adapter.execute() (Attempt {attempt}): {exc}")

        if outcome is not None:
            log_line(session_path, f"adapter.execute() beendet (Attempt {attempt}), exit_code={outcome.exit_code}")
            if remaining_budget is not None:
                spent_so_far += outcome.cost_usd if outcome.cost_usd is not None else remaining_budget

        if outcome is not None and outcome.interrupted:
            detail = "Vom Nutzer unterbrochen (Stop-Button) während adapter.execute()."
            log_line(session_path, detail)
            print("Work Order wurde vom Nutzer gestoppt — kein weiterer Runner-Start.")
            _mark_running_step_interrupted(args, session_path, order, detail)
            _terminalize_cancelled_run(args, session_path, run_id, detail)
            return 0

        if outcome is not None and outcome.result is not None:
            (session_path / "result.json").write_text(
                json.dumps(outcome.result, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            log_line(session_path, "Ergebnis-JSON aus adapter.execute() als result.json gespeichert.")

            if _current_status(args) == "cancelled":
                detail = "Work Order wurde cancelled — Ergebnis liegt lokal vor, wird NICHT importiert."
                log_line(session_path, detail)
                print("Work Order wurde inzwischen cancelled — Ergebnis-Import wird übersprungen.")
                _terminalize_cancelled_run(args, session_path, run_id, detail)
                return 0
            return cmd_import_result(args, adapter)

        # Technical failure: either an exception, or execute() returned
        # without one but produced no usable result at all.
        after = _git_snapshot(_target_worktree())
        failure_detail = f"Fehler: {exec_error}" if exec_error else f"exit_code={outcome.exit_code if outcome else 'unbekannt'}"

        if _worktree_changed(before, after):
            detail = (
                f"Technischer Fehler bei Attempt {attempt} UND der Working Tree hat sich seitdem verändert "
                "(oder war nicht feststellbar) — kein Auto-Retry, menschliches Eingreifen nötig. " + failure_detail
            )
            log_line(session_path, detail)
            _finalize_technical_failure(args, session_path, run_id, "technical_failure_with_worktree_changes", detail)
            return 1

        if attempt >= _MAX_TECHNICAL_ATTEMPTS:
            detail = (
                f"Technischer Fehler, {attempt}/{_MAX_TECHNICAL_ATTEMPTS} Versuche ausgeschöpft, Working Tree "
                "unverändert — kein weiterer Retry mehr erlaubt. " + failure_detail
            )
            log_line(session_path, detail)
            _finalize_technical_failure(args, session_path, run_id, "technical_failure_retries_exhausted", detail)
            return 1

        if _current_status(args) == "cancelled":
            detail = "Work Order wurde cancelled — kein weiterer Retry."
            log_line(session_path, detail)
            print(detail)
            _terminalize_cancelled_run(args, session_path, run_id, detail)
            return 0

        # Close out this attempt's AgentRun, open a new one for the next
        # attempt — each attempt is its own row (CP-OP02).
        next_attempt = attempt + 1
        if run_id:
            try:
                call_api(
                    args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/agent-runs/{run_id}",
                    {"status": "failed", "output_summary": f"Attempt {attempt} technischer Fehler — wird retried. {failure_detail}"[:2000]},
                    dry_run=args.dry_run,
                )
            except ImportError_ as exc:
                log_line(session_path, f"WARNUNG: konnte AgentRun {run_id} nicht auf failed setzen: {exc}")

        retry_reason = f"technical_failure_attempt_{attempt}"
        try:
            created = call_api(
                args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/agent-runs",
                {
                    "role": _agent_run_role(order),
                    "status": "running",
                    "input_summary": f"Auto-Retry Attempt {next_attempt}/{_MAX_TECHNICAL_ATTEMPTS} ({adapter.info.name})"[:2000],
                    "model": f"{adapter.info.name} (execute, retry)",
                    "attempt_number": next_attempt,
                    "retry_reason": retry_reason,
                },
                dry_run=args.dry_run,
            )
            run_id = created.get("id") if created else run_id
            if run_id:
                write_agent_run_state(session_path, run_id, adapter.info.name, args.mode)
            log_line(session_path, f"AgentRun für Attempt {next_attempt} angelegt: {run_id}")
        except ImportError_ as exc:
            log_line(session_path, f"WARNUNG: konnte AgentRun für Attempt {next_attempt} nicht anlegen: {exc}")

    # Unreachable: the loop always returns on its final iteration
    # (attempt >= _MAX_TECHNICAL_ATTEMPTS is guaranteed to be true then).
    return 1


def _run_one_step_with_bounded_retry(
    args: argparse.Namespace,
    adapter: RunnerAdapter,
    order: dict,
    step: dict,
    prior_steps: list[dict],
    session_path: Path,
    total_budget: float | None,
    spent_so_far: float,
) -> tuple[int | None, dict | None, float]:
    """Step-granular sibling of _run_adapter_with_bounded_retry() — same
    bounded-retry/worktree-safety/cancellation contract, scoped to ONE
    ticketplan step's attempts instead of the whole order's. Called once
    per step, in order, by _run_step_by_step().

    Returns (rc, step_entry, new_spent_so_far):
      - rc is None on a genuine step result (the caller continues the
        per-step loop with step_entry — the validated single-entry
        `steps[0]` dict from the step's result).
      - rc is an int (0 or 1) when the WHOLE run should stop now (technical
        failure exhausted, budget exhausted, or cancellation) — everything
        that needed finalizing (AgentRun/work-order state) has already
        been done by the time this returns; the caller just propagates rc.
    """
    run_id: str | None = None
    try:
        created = call_api(
            args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/agent-runs",
            {
                "role": step["assigned_role"],
                "status": "running",
                "input_summary": f"Step '{step['title']}' ({adapter.info.name}, --per-step)"[:2000],
                "model": f"{adapter.info.name} (execute, per-step)",
            },
            dry_run=args.dry_run,
        )
        run_id = created.get("id") if created else None
        if run_id:
            log_line(session_path, f"AgentRun für Step '{step['title']}' angelegt: {run_id}")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte AgentRun für Step '{step['title']}' nicht anlegen: {exc}")

    try:
        call_api(
            args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/steps/{step['id']}",
            {"status": "running"}, dry_run=args.dry_run,
        )
        log_line(session_path, f"Step '{step['title']}' ({step['id']}) -> running")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte Step '{step['title']}' nicht auf running setzen: {exc}")

    for attempt in range(1, _MAX_TECHNICAL_ATTEMPTS + 1):
        if _current_status(args) == "cancelled":
            detail = f"Work Order ist cancelled — kein weiterer Versuch für Step '{step['title']}' (vor Attempt {attempt})."
            log_line(session_path, detail)
            print("Work Order wurde cancelled — breche ab, kein weiterer Step-Versuch.")
            _terminalize_cancelled_run(args, session_path, run_id, detail)
            return 0, None, spent_so_far

        remaining_budget: float | None = None
        if total_budget is not None:
            remaining_budget = round(max(total_budget - spent_so_far, 0.0), 4)
            if remaining_budget <= 0:
                detail = (
                    f"Gesamtbudget ${total_budget} durch vorherige Steps/Versuche aufgebraucht — "
                    f"Step '{step['title']}' Attempt {attempt}/{_MAX_TECHNICAL_ATTEMPTS} wird nicht mehr gestartet."
                )
                log_line(session_path, detail)
                _finalize_technical_failure(args, session_path, run_id, "technical_failure_budget_exhausted", detail)
                return 1, None, spent_so_far

        before = _git_snapshot(_target_worktree())
        budget_note = f" (Budget verbleibend: ${remaining_budget})" if remaining_budget is not None else ""
        log_line(
            session_path,
            f"Step '{step['title']}' Attempt {attempt}/{_MAX_TECHNICAL_ATTEMPTS} — starte adapter.execute_step(){budget_note}",
        )

        progress = make_progress_reporter(args, session_path, run_id)

        outcome = None
        exec_error: Exception | None = None
        try:
            outcome = adapter.execute_step(
                order, step, prior_steps, session_path, max_budget_usd=remaining_budget, progress=progress,
            )
        except NotImplementedError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1, None, spent_so_far
        except Exception as exc:  # noqa: BLE001 — any adapter failure here is a technical failure by definition
            exec_error = exc
            log_line(session_path, f"FEHLER bei adapter.execute_step() für Step '{step['title']}' (Attempt {attempt}): {exc}")

        if outcome is not None:
            log_line(
                session_path,
                f"adapter.execute_step() für Step '{step['title']}' beendet (Attempt {attempt}), exit_code={outcome.exit_code}",
            )
            if remaining_budget is not None:
                spent_so_far += outcome.cost_usd if outcome.cost_usd is not None else remaining_budget

        if outcome is not None and outcome.interrupted:
            detail = f"Vom Nutzer unterbrochen (Stop-Button) während Step '{step['title']}'."
            log_line(session_path, detail)
            print("Work Order wurde vom Nutzer gestoppt — kein weiterer Step-Start.")
            _mark_step_interrupted(args, session_path, step, detail)
            _terminalize_cancelled_run(args, session_path, run_id, detail)
            return 0, None, spent_so_far

        validated: dict | None = None
        if outcome is not None and outcome.step_result is not None:
            try:
                validated = parse_and_validate_step_result(
                    json.dumps(outcome.step_result), f"execute_step() result for step {step['id']}",
                )
            except ValueError as exc:
                exec_error = exc
                log_line(session_path, f"FEHLER: Step-Ergebnis für '{step['title']}' hat ungültige Form: {exc}")

        if validated is not None:
            (session_path / f"result_step_{step['id']}.json").write_text(
                json.dumps(validated, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            log_line(session_path, f"Ergebnis-JSON für Step '{step['title']}' gespeichert.")

            if _current_status(args) == "cancelled":
                detail = f"Work Order wurde cancelled — Step-Ergebnis für '{step['title']}' liegt lokal vor, wird NICHT importiert."
                log_line(session_path, detail)
                print("Work Order wurde inzwischen cancelled — Step-Ergebnis-Import wird übersprungen.")
                _terminalize_cancelled_run(args, session_path, run_id, detail)
                return 0, None, spent_so_far

            import_rc = import_result(
                validated, args.api_url, args.token, dry_run=args.dry_run,
                agent_run_id=run_id, require_all_steps=False,
            )
            if import_rc != 0:
                log_line(
                    session_path,
                    f"WARNUNG: Import des Step-Ergebnisses für '{step['title']}' hatte Fehler (exit {import_rc}) "
                    "— Step-Status könnte trotzdem gesetzt sein, siehe Log oben.",
                )
            return None, validated["steps"][0], spent_so_far

        # Technical failure: an exception, an invalid-shape result, or no
        # result at all — same three-way branch as
        # _run_adapter_with_bounded_retry(), just per-step.
        after = _git_snapshot(_target_worktree())
        failure_detail = f"Fehler: {exec_error}" if exec_error else f"exit_code={outcome.exit_code if outcome else 'unbekannt'}"

        if _worktree_changed(before, after):
            detail = (
                f"Technischer Fehler bei Step '{step['title']}' Attempt {attempt} UND der Working Tree hat sich "
                "seitdem verändert (oder war nicht feststellbar) — kein Auto-Retry, menschliches Eingreifen nötig. "
                + failure_detail
            )
            log_line(session_path, detail)
            _finalize_technical_failure(args, session_path, run_id, "technical_failure_with_worktree_changes", detail)
            return 1, None, spent_so_far

        if attempt >= _MAX_TECHNICAL_ATTEMPTS:
            detail = (
                f"Technischer Fehler bei Step '{step['title']}', {attempt}/{_MAX_TECHNICAL_ATTEMPTS} Versuche "
                "ausgeschöpft, Working Tree unverändert — kein weiterer Retry mehr erlaubt. " + failure_detail
            )
            log_line(session_path, detail)
            _finalize_technical_failure(args, session_path, run_id, "technical_failure_retries_exhausted", detail)
            return 1, None, spent_so_far

        if _current_status(args) == "cancelled":
            detail = f"Work Order wurde cancelled — kein weiterer Retry für Step '{step['title']}'."
            log_line(session_path, detail)
            print(detail)
            _terminalize_cancelled_run(args, session_path, run_id, detail)
            return 0, None, spent_so_far

        next_attempt = attempt + 1
        if run_id:
            try:
                call_api(
                    args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}/agent-runs/{run_id}",
                    {
                        "status": "failed",
                        "output_summary": f"Attempt {attempt} technischer Fehler — wird retried. {failure_detail}"[:2000],
                    },
                    dry_run=args.dry_run,
                )
            except ImportError_ as exc:
                log_line(session_path, f"WARNUNG: konnte AgentRun {run_id} nicht auf failed setzen: {exc}")

        retry_reason = f"technical_failure_attempt_{attempt}"
        try:
            created = call_api(
                args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/agent-runs",
                {
                    "role": step["assigned_role"],
                    "status": "running",
                    "input_summary": f"Step '{step['title']}' Auto-Retry Attempt {next_attempt}/{_MAX_TECHNICAL_ATTEMPTS} ({adapter.info.name})"[:2000],
                    "model": f"{adapter.info.name} (execute, per-step retry)",
                    "attempt_number": next_attempt,
                    "retry_reason": retry_reason,
                },
                dry_run=args.dry_run,
            )
            run_id = created.get("id") if created else run_id
            log_line(session_path, f"AgentRun für Step '{step['title']}' Attempt {next_attempt} angelegt: {run_id}")
        except ImportError_ as exc:
            log_line(session_path, f"WARNUNG: konnte AgentRun für Step '{step['title']}' Attempt {next_attempt} nicht anlegen: {exc}")

    # Unreachable: the loop always returns on its final iteration.
    return 1, None, spent_so_far


def _final_status_from_steps(steps_results: list[dict]) -> str:
    if any(s["status"] == "failed" for s in steps_results):
        return "failed"
    if any(s["status"] == "blocked" for s in steps_results):
        return "blocked"
    return "review_ready"


def _synthesize_review_package(steps_results: list[dict]) -> dict:
    """Deterministic reviewPackage assembly from per-step outputSummaries —
    no extra LLM call (per Serkan's explicit choice: --per-step should stay
    at exactly the N calls the per-step model already costs, not N+1). Less
    polished than a model-written summary, but every line traces to a real
    step result — nothing invented."""
    completed = [s for s in steps_results if s["status"] in ("completed", "skipped")]
    blocked = [s for s in steps_results if s["status"] == "blocked"]
    failed = [s for s in steps_results if s["status"] == "failed"]

    summary_parts = [f"{len(completed)}/{len(steps_results)} Steps abgeschlossen (Per-Step-Ausführung)."]
    if blocked:
        summary_parts.append(f"{len(blocked)} blockiert.")
    if failed:
        summary_parts.append(f"{len(failed)} fehlgeschlagen.")

    if failed:
        verdict = "needs_fix"
        recommended = "Fehlgeschlagene(n) Step(s) prüfen, ggf. Work Order requeuen."
    elif blocked:
        verdict = "blocked"
        recommended = "Blockierte(n) Step(s) prüfen — Approval nötig oder Scope anpassen."
    else:
        verdict = "ready_for_review"
        recommended = "Review Package prüfen und freigeben."

    risks = [
        f"Step '{s['title']}': {s.get('outputSummary') or s.get('blockedReason') or '(kein Detail gemeldet)'}"
        for s in steps_results if s["status"] in ("blocked", "failed")
    ]

    return {
        "summary": " ".join(summary_parts),
        "filesChanged": [],
        "testsRun": [],
        "risks": risks,
        "openQuestions": [],
        "needsHumanReview": True,
        "recommendedNextStep": recommended,
        "verdict": verdict,
    }


def _finalize_step_by_step_run(args: argparse.Namespace, session_path: Path, steps_results: list[dict]) -> int:
    """Called once after the --per-step loop ends (every step resolved
    cleanly, or the loop stopped early on the first blocked/failed step).
    Writes a deterministically-synthesized reviewPackage and the work
    order's final status via the same endpoints the whole-order path uses.
    Remaining un-started steps (if the loop stopped early) are left at
    their existing 'pending' status — not touched here, matching the
    plan's explicit choice that 'skipped' means a considered runner
    decision, not "we didn't get there".

    Return code follows the same convention as import_result(): 0 means
    the writes themselves succeeded, independent of whether the semantic
    outcome was review_ready/blocked/failed — a clean 'blocked' finalize
    is exit 0, exactly like a genuine blocked result import is today."""
    final_status = _final_status_from_steps(steps_results)
    review_package = _synthesize_review_package(steps_results)

    had_failure = False
    try:
        call_api(
            args.api_url, args.token, "PUT", f"/api/work-orders/{args.work_order_id}/review-package",
            review_package_payload(review_package), dry_run=args.dry_run,
        )
        log_line(session_path, f"Review Package geschrieben (verdict={review_package['verdict']})")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte Review Package nicht schreiben: {exc}")
        had_failure = True

    try:
        call_api(
            args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}",
            {"status": final_status, "source": "harness"}, dry_run=args.dry_run,
        )
        log_line(session_path, f"Work Order -> {final_status} (Per-Step-Lauf abgeschlossen)")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte finalen Work-Order-Status nicht setzen: {exc}")
        print(f"WARNUNG: {exc}", file=sys.stderr)
        had_failure = True

    return 1 if had_failure else 0


def _run_step_by_step(
    args: argparse.Namespace,
    adapter: RunnerAdapter,
    order: dict,
    session_path: Path,
    total_budget: float | None,
    initial_agent_run_id: str | None,
) -> int:
    """--per-step: drives adapter.execute_step() once per ticketplan step,
    in order_index order, writing each step's result back IMMEDIATELY
    (PATCH step status + POST activityLogs/artifacts via import_result())
    instead of waiting for one final whole-order result — this is what
    actually makes the Operator UI's step pipeline show real, individual
    step transitions instead of only the first step ever leaving 'pending'.

    Each step gets its own AgentRun (role = the step's own assigned_role)
    with its own bounded retry — see _run_one_step_with_bounded_retry().
    `total_budget` stays ONE cumulative ceiling across every step × every
    retry in this whole run, same conservative accounting as
    _run_adapter_with_bounded_retry().

    cmd_prompt_file() (called by cmd_execute() before this) already created
    one session-level AgentRun anchored on the first step's role — that
    row is immediately closed out here as 'completed' (a no-op session
    marker) since per-step mode creates its own real AgentRun per step;
    leaving it open would be exactly the "stuck on running forever" bug
    OP-Runner-Session-001 already fixed once for the whole-order path.
    """
    if initial_agent_run_id:
        try:
            call_api(
                args.api_url, args.token, "PATCH",
                f"/api/work-orders/{args.work_order_id}/agent-runs/{initial_agent_run_id}",
                {
                    "status": "completed",
                    "output_summary": "Session-Start-AgentRun — Ausführung läuft im Per-Step-Modus, "
                                       "siehe die AgentRun-Zeile pro Step für den echten Verlauf.",
                },
                dry_run=args.dry_run,
            )
            log_line(session_path, f"Session-AgentRun {initial_agent_run_id} -> completed (Per-Step-Modus übernimmt eigene AgentRuns pro Step)")
        except ImportError_ as exc:
            log_line(session_path, f"WARNUNG: konnte Session-AgentRun {initial_agent_run_id} nicht schließen: {exc}")

    steps = sorted(order.get("steps") or [], key=lambda s: s.get("order_index", 0))
    prior_steps: list[dict] = []
    steps_results: list[dict] = []
    spent_so_far = 0.0

    for step in steps:
        if _current_status(args) == "cancelled":
            detail = f"Work Order ist cancelled — kein weiterer Step-Start (vor Step '{step['title']}')."
            log_line(session_path, detail)
            print("Work Order wurde cancelled — breche ab, kein weiterer Step-Start.")
            _terminalize_cancelled_run(args, session_path, None, detail)
            return 0

        rc, step_entry, spent_so_far = _run_one_step_with_bounded_retry(
            args, adapter, order, step, prior_steps, session_path, total_budget, spent_so_far,
        )
        if rc is not None:
            return rc

        prior_steps.append({
            "id": step["id"], "title": step["title"],
            "status": step_entry["status"], "outputSummary": step_entry.get("outputSummary"),
        })
        # step_entry (from the validated STEP_RESULT_JSON_SCHEMA result) has
        # no 'title' — the model is never asked to restate it. Merge in the
        # ticketplan's own title here so _synthesize_review_package() can
        # produce a readable risks list without re-deriving it.
        steps_results.append({**step_entry, "title": step["title"]})

        if step_entry["status"] in ("blocked", "failed"):
            log_line(
                session_path,
                f"Step '{step['title']}' meldet {step_entry['status']} — Lauf wird beendet, "
                "verbleibende Steps bleiben 'pending'.",
            )
            break

    return _finalize_step_by_step_run(args, session_path, steps_results)


def cmd_prompt_file(args: argparse.Namespace, adapter: RunnerAdapter) -> int:
    order = fetch_work_order(args.api_url, args.token, args.work_order_id)

    errors = validate_preconditions(order, args.force) + adapter.check_scope_errors(order)
    if errors:
        print("Sicherheits-Preconditions nicht erfüllt — Start abgebrochen:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    for w in check_warnings(order) + adapter.check_scope_warnings(order):
        print(f"WARNUNG: {w}")

    session_path = session_dir(args.work_order_id)
    log_line(session_path, f"Preconditions OK (Adapter: {adapter.info.name}). Status vor Start: {order['status']}")

    try:
        prepared_path = adapter.prepare(order, session_path)
    except Exception as exc:
        log_line(session_path, f"FEHLER bei adapter.prepare(): {exc}")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    log_line(session_path, f"Adapter '{adapter.info.name}'.prepare() abgeschlossen: {prepared_path}")

    if order["status"] != "running":
        try:
            call_api(args.api_url, args.token, "PATCH", f"/api/work-orders/{args.work_order_id}",
                      {"status": "running", "source": "harness"}, dry_run=args.dry_run)
            log_line(session_path, "Work Order Status -> running")
        except ImportError_ as exc:
            log_line(session_path, f"FEHLER beim Setzen von Status running: {exc}")
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    steps = order.get("steps") or []
    if steps:
        first_step = steps[0]
        try:
            call_api(args.api_url, args.token, "PATCH",
                      f"/api/work-orders/{args.work_order_id}/steps/{first_step['id']}",
                      {"status": "running"}, dry_run=args.dry_run)
            log_line(session_path, f"Step '{first_step['title']}' ({first_step['id']}) -> running")
        except ImportError_ as exc:
            log_line(session_path, f"WARNUNG: konnte ersten Step nicht auf running setzen: {exc}")

    # ── Real AgentRun record for this session (OP-Runner-Session-001) —
    # `role` anchors on the first ticketplan step's role, same anchor the
    # first-step PATCH above already uses; falls back to "coder" if the
    # work order has no ticketplan at all. `model` doubles as "which
    # runner ran this, in which mode" (adapter name + args.mode) since
    # AgentRun has no dedicated column for either and adding one would be
    # a migration (needs approval) — see reviewPackage.risks. Best-effort:
    # a failure here is logged but never aborts prompt-file mode, matching
    # the first-step PATCH above.
    agent_run_id: str | None = None
    agent_run_role = _agent_run_role(order)
    try:
        created = call_api(
            args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/agent-runs",
            {
                "role": agent_run_role,
                "status": "running",
                "input_summary": f"Runner-Start ({adapter.info.name}, --mode {args.mode}) für Work Order '{order['title']}'"[:2000],
                "model": f"{adapter.info.name} ({args.mode})",
            },
            dry_run=args.dry_run,
        )
        agent_run_id = created.get("id") if created else None
        if agent_run_id:
            write_agent_run_state(session_path, agent_run_id, adapter.info.name, args.mode)
            log_line(session_path, f"AgentRun {agent_run_id} angelegt (role={agent_run_role}, status=running)")
        elif args.dry_run:
            log_line(session_path, "AgentRun-Anlage übersprungen (--dry-run liefert keine echte id)")
        else:
            # The POST didn't raise (so the server answered 2xx) but the
            # response had no usable "id" — e.g. an unexpectedly empty body.
            # Silently doing nothing here was the actual bug behind a real
            # confusing session (OP-Runner-Session-001 follow-up): the run
            # continued fine, but nothing said WHY no AgentRun got tracked.
            log_line(session_path, f"WARNUNG: AgentRun-Antwort enthielt keine 'id' — nichts angelegt. Antwort: {created!r}")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte AgentRun nicht anlegen: {exc}")

    activity_log_payload: dict[str, Any] = {
        "level": "info", "event_type": "runner_started",
        "message": f"Lokaler Runner ({adapter.info.name}) gestartet, vorbereitet nach {session_path}",
    }
    if agent_run_id:
        activity_log_payload["agent_run_id"] = agent_run_id
    try:
        call_api(args.api_url, args.token, "POST", f"/api/work-orders/{args.work_order_id}/activity-log",
                  activity_log_payload, dry_run=args.dry_run)
        log_line(session_path, "ActivityLog-Eintrag 'runner_started' geschrieben")
    except ImportError_ as exc:
        log_line(session_path, f"WARNUNG: konnte ActivityLog nicht schreiben: {exc}")

    print(f"\nFertig ({adapter.info.name}). Artefakt liegt unter: {prepared_path}")
    if adapter.info.supports_auto_execute == "no":
        print("Nächster Schritt: Inhalt in Claude Code/Codex einfügen, laufen lassen, Ergebnis-JSON speichern als:")
        print(f"  {session_path / 'result.json'}")
    elif adapter.info.supports_auto_execute == "semi_auto":
        print(f"Dieser Adapter unterstützt teilautomatische Ausführung — siehe {session_path / 'claude_command.txt'} "
              f"für den genauen Befehl, oder starte ihn direkt mit --mode execute --adapter {adapter.info.name}.")
    print(f"Danach: python scripts/run_work_order.py {args.work_order_id} --mode import-result --adapter {adapter.info.name}")
    return 0


def cmd_import_result(args: argparse.Namespace, adapter: RunnerAdapter) -> int:
    session_path = session_dir(args.work_order_id)

    try:
        result = adapter.collect_result(session_path, args.result_file)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        # ValueError covers both a plain JSONDecodeError (which is itself a
        # ValueError subclass) and parse_and_validate_result()'s own shape
        # errors (missing required field, bad finalStatus, ...) — both
        # already carry a clear, specific message naming the problem.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if result.get("workOrderId") != args.work_order_id:
        print(
            f"WARNUNG: workOrderId im Ergebnis ('{result.get('workOrderId')}') stimmt nicht mit "
            f"dem angegebenen Work Order ('{args.work_order_id}') überein — importiere trotzdem, wie angegeben.",
            file=sys.stderr,
        )

    # Cross-check the result against the REAL work order (real step ids,
    # valid status/verdict enums) before a single API call is made — see
    # validate_result_against_order()'s docstring for why this previously
    # only surfaced as partial import failures.
    try:
        order = fetch_work_order(args.api_url, args.token, args.work_order_id)
        validate_result_against_order(result, order, f"result.json for {args.work_order_id}")
    except RuntimeError as exc:
        print(f"WARNUNG: konnte Work Order für Cross-Validation nicht laden ({exc}) — überspringe Step-ID/Status-Check.", file=sys.stderr)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    agent_run_id = read_agent_run_id(session_path)
    if agent_run_id:
        log_line(session_path, f"Importiere Ergebnis (Adapter: {adapter.info.name}, AgentRun: {agent_run_id})")
    else:
        log_line(session_path, f"Importiere Ergebnis (Adapter: {adapter.info.name}, kein AgentRun für diese Session gefunden)")
    exit_code = import_result(result, args.api_url, args.token, dry_run=args.dry_run, agent_run_id=agent_run_id)
    log_line(session_path, f"Import abgeschlossen, exit_code={exit_code}")
    return exit_code


def cmd_execute(args: argparse.Namespace, adapter: RunnerAdapter) -> int:
    # Path safety applies to BOTH auto-execution branches below (the generic
    # --runner-command escape hatch and adapter-native execute()) — checked
    # once, here, before cmd_prompt_file mutates anything (sets status
    # running, first step running, ...). An earlier version of this
    # function only ran this check in the adapter-native branch, which
    # silently let --runner-command bypass it entirely — fixed before ever
    # shipping, caught by this file's own dry-run test suite.
    order = fetch_work_order(args.api_url, args.token, args.work_order_id)
    path_errors = check_execute_path_safety(order, args.force)
    if path_errors:
        print("Sicherheits-Precondition für automatische Ausführung nicht erfüllt — abgebrochen:", file=sys.stderr)
        for e in path_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Budget gate: adapters that spend real money on execute() (claude_code
    # today) require an EXPLICIT budget acknowledgment before this harness
    # will invoke them — --max-budget-usd or COMMANDPILOT_CLAUDE_MAX_BUDGET_USD.
    # Deliberately never defaulted to some "safe-sounding" number ourselves:
    # a silent default would be exactly the kind of "unkontrolliert Usage
    # Credits verbrauchen" this gate exists to prevent. Scoped to the
    # adapter-native path only (no --runner-command) — that path is the one
    # where THIS harness decides to invoke a paid CLI on the user's behalf;
    # --runner-command always requires a human to have typed the exact
    # command themselves, which is a fundamentally different consent signal.
    effective_budget: float | None = None
    if not args.runner_command and adapter.info.consumes_paid_credits:
        effective_budget = args.max_budget_usd
        if effective_budget is None:
            env_value = os.environ.get("COMMANDPILOT_CLAUDE_MAX_BUDGET_USD")
            if env_value:
                try:
                    effective_budget = float(env_value)
                except ValueError:
                    print(
                        f"ERROR: COMMANDPILOT_CLAUDE_MAX_BUDGET_USD={env_value!r} ist keine gültige Zahl.",
                        file=sys.stderr,
                    )
                    return 1
        if effective_budget is None:
            print(
                "ERROR: Claude Code execution would consume usage credits. "
                "Set --max-budget-usd or use --mode prompt-file.",
                file=sys.stderr,
            )
            return 1
        if effective_budget <= 0:
            print("ERROR: --max-budget-usd muss größer als 0 sein.", file=sys.stderr)
            return 1

    rc = cmd_prompt_file(args, adapter)
    if rc != 0:
        return rc

    session_path = session_dir(args.work_order_id)

    if args.runner_command:
        # Generic, adapter-agnostic path — a human always supplies the
        # actual command. Works with any adapter, unchanged since
        # OP-Runner-002; not part of the RunnerAdapter contract itself.
        prompt_path = session_path / "prompt.md"
        command = args.runner_command.replace("{prompt_file}", str(prompt_path)).replace("{session_dir}", str(session_path))

        log_line(session_path, f"Führe Runner-Befehl aus: {command}")
        print(f"\nFühre aus: {command}")
        try:
            proc = subprocess.run(command, shell=True, cwd=REPO_ROOT, capture_output=True, text=True)
        except Exception as exc:
            log_line(session_path, f"FEHLER beim Ausführen des Runner-Befehls: {exc}")
            print(f"ERROR: Runner-Befehl fehlgeschlagen: {exc}", file=sys.stderr)
            return 1

        output = (proc.stdout or "") + (("\n--- stderr ---\n" + proc.stderr) if proc.stderr else "")
        (session_path / "execute_output.log").write_text(output, encoding="utf-8")
        log_line(session_path, f"Runner-Befehl beendet (exit {proc.returncode}), Output in execute_output.log gespeichert")

        extracted = extract_json_result(proc.stdout or "")
        if extracted is not None:
            (session_path / "result.json").write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
            log_line(session_path, "Ergebnis-JSON automatisch im Output erkannt und als result.json gespeichert.")
            print("Erkanntes Ergebnis-JSON gefunden — importiere es jetzt...")
            return cmd_import_result(args, adapter)

        print(
            "\nKonnte kein gültiges Ergebnis-JSON automatisch im Output finden.\n"
            f"Output wurde gespeichert in: {session_path / 'execute_output.log'}\n"
            f"Speichere das Ergebnis-JSON manuell als {session_path / 'result.json'} und führe dann aus:\n"
            f"  python scripts/run_work_order.py {args.work_order_id} --mode import-result --adapter {adapter.info.name}"
        )
        return 0

    # No --runner-command: adapter-native execution. Only meaningful for
    # adapters declaring "yes" or "semi_auto" — "no" adapters (manual_prompt,
    # unresearched placeholders) have nothing to call here. path_errors was
    # already checked above, against this same `order` — no need to refetch
    # or recheck.
    if adapter.info.supports_auto_execute == "no":
        print(f"Adapter '{adapter.info.name}' unterstützt kein automatisches Ausführen ohne --runner-command.", file=sys.stderr)
        print("Nutze --mode prompt-file und führe den Prompt manuell aus, oder gib --runner-command an.", file=sys.stderr)
        return 1

    if adapter.info.supports_auto_execute == "semi_auto":
        print(
            f"Hinweis: Adapter '{adapter.info.name}' ist teilautomatisch (semi_auto) — die Ausführung "
            "kann von einem einmaligen manuellen Schritt abhängen (z.B. Workspace-Trust bei Claude Code). "
            "Ein Fehlschlag hier ist erwartbar, kein Bug."
        )

    initial_agent_run_id = read_agent_run_id(session_path)

    if args.per_step:
        if not adapter.info.supports_step_execution:
            print(
                f"ERROR: Adapter '{adapter.info.name}' unterstützt --per-step nicht "
                f"(supports_step_execution={adapter.info.supports_step_execution!r}).",
                file=sys.stderr,
            )
            return 1
        return _run_step_by_step(
            args, adapter, order, session_path, effective_budget, initial_agent_run_id
        )

    # CP-OP02: bounded, harness-driven retry — up to _MAX_TECHNICAL_ATTEMPTS
    # calls to adapter.execute(), retried only on a technical failure with
    # an unchanged working tree. See _run_adapter_with_bounded_retry()'s
    # docstring for the full contract; cmd_prompt_file() above already
    # created the first AgentRun (status=running), which is attempt 1.
    return _run_adapter_with_bounded_retry(
        args, adapter, order, session_path, effective_budget, initial_agent_run_id
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("work_order_id")
    parser.add_argument("--mode", required=True, choices=["prompt-file", "import-result", "execute"])
    parser.add_argument("--adapter", default="manual_prompt", choices=list(ADAPTERS.keys()),
                          help="RunnerAdapter to use. Default: manual_prompt (fully manual — copy/paste). "
                               "claude_code is semi-automatic (see docs/runner-adapter-contract.md for the "
                               "one-time workspace-trust step it depends on); claude_code_sandboxed runs the "
                               "same CLI fully unattended inside a disposable Docker container + git worktree "
                               "(requires Docker; see scripts/sandbox/Dockerfile and that adapter's module "
                               "docstring for the safety argument); codex/openclaw are still architectural "
                               "placeholders only.")
    parser.add_argument("--api-url", default=os.environ.get("COMMANDPILOT_API_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("COMMANDPILOT_API_TOKEN"))
    parser.add_argument("--force", action="store_true",
                          help="Bypass only the work-order-status precondition — never the safety-critical checks.")
    parser.add_argument("--result-file",
                          help="Path to the result JSON for --mode import-result. Defaults to "
                               "tmp/work-order-runs/<id>/result.json. Use '-' for stdin.")
    parser.add_argument("--runner-command",
                          help="Shell command for --mode execute. Supports {prompt_file}/{session_dir} "
                               "placeholders. No default — must be explicit.")
    parser.add_argument("--max-budget-usd", type=float, default=None,
                          help="Required (or set COMMANDPILOT_CLAUDE_MAX_BUDGET_USD) before --mode execute "
                               "with a credit-consuming adapter (claude_code) will run. No default is ever "
                               "assumed — this is a deliberate hard stop, not a formality. Has no effect on "
                               "--mode prompt-file (writes files only, never spends anything) or on "
                               "manual_prompt (never calls a paid API itself).")
    parser.add_argument("--per-step", action="store_true",
                          help="--mode execute only: run one adapter call PER ticketplan step (status written "
                               "back immediately after each step) instead of one call for the whole order. "
                               "Opt-in — only adapters with supports_step_execution=True (currently "
                               "claude_code and claude_code_sandboxed) accept this. Genuinely more expensive "
                               "(N calls instead of 1) in exchange for real live step-by-step visibility.")
    parser.add_argument("--dry-run", action="store_true",
                          help="Print the API calls that would be made without making them.")
    args = parser.parse_args()

    if not args.token:
        print("ERROR: no API token. Pass --token or set COMMANDPILOT_API_TOKEN.", file=sys.stderr)
        print("See docs/background-dev-team-runbook.md §1 for how to obtain one.", file=sys.stderr)
        return 1

    adapter = get_adapter(args.adapter)

    if args.mode == "prompt-file":
        return cmd_prompt_file(args, adapter)
    if args.mode == "import-result":
        return cmd_import_result(args, adapter)
    return cmd_execute(args, adapter)


if __name__ == "__main__":
    raise SystemExit(main())
