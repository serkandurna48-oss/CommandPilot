#!/usr/bin/env python3
"""Local runner harness for the Background Dev Team control plane.

CommandPilot is the Control Plane (work orders, approval scopes, steps,
activity log, review packages — all persisted server-side). It orchestrates
RunnerAdapters; it does not become a coding agent itself. Execution always
happens on the Execution Plane — today that's a human running this script
on their own machine (via the manual_prompt adapter), later possibly
Claude Code / Codex / OpenClaw adapters, or an isolated worker sandbox. See
scripts/runner_adapters/ and docs/runner-adapter-contract.md.

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
from import_work_order_result import ImportError_, call_api, import_result  # noqa: E402
from runner_adapters import ADAPTERS, RunnerAdapter, get_adapter  # noqa: E402
from runner_adapters.base import extract_json_result, find_blocked_keyword, validate_result_against_order  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where cmd_prompt_file() records the AgentRun it created for this session,
# so a later (often separate-process) --mode import-result invocation can
# find it again and close it out (OP-Runner-Session-001). Deliberately a
# small standalone file rather than piggy-backing on run.log (plaintext,
# append-only, not meant to be parsed back) or prompt.md (adapter-owned).
_AGENT_RUN_STATE_FILENAME = "agent_run.json"


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
                      {"status": "running"}, dry_run=args.dry_run)
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
    agent_run_role = steps[0]["assigned_role"] if steps else "coder"
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

    try:
        outcome = adapter.execute(order, session_path, None, max_budget_usd=effective_budget)
    except NotImplementedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        log_line(session_path, f"FEHLER bei adapter.execute(): {exc}")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    log_line(session_path, f"Adapter-natives execute() beendet, exit_code={outcome.exit_code}")
    if outcome.result is not None:
        # collect_result() (called inside cmd_import_result) reads from disk
        # by default — persist the in-memory result here first, mirroring
        # the generic --runner-command branch above, or import would fail
        # with "result file not found" despite outcome.result already
        # holding the parsed data. Caught by this file's own dry-run suite.
        (session_path / "result.json").write_text(
            json.dumps(outcome.result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log_line(session_path, "Ergebnis-JSON aus adapter.execute() als result.json gespeichert.")
        return cmd_import_result(args, adapter)
    print(f"Kein Ergebnis-JSON von Adapter '{adapter.info.name}' erhalten — siehe {outcome.output_log_path}.")
    return outcome.exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("work_order_id")
    parser.add_argument("--mode", required=True, choices=["prompt-file", "import-result", "execute"])
    parser.add_argument("--adapter", default="manual_prompt", choices=list(ADAPTERS.keys()),
                          help="RunnerAdapter to use. Default: manual_prompt (fully manual — copy/paste). "
                               "claude_code is semi-automatic (see docs/runner-adapter-contract.md for the "
                               "one-time workspace-trust step it depends on); codex/openclaw are still "
                               "architectural placeholders only.")
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
