#!/usr/bin/env python3
"""Import a runner's result JSON back into CommandPilot.

The recorder/import bridge for the Background Dev Team control plane. A
runner session (Claude Code / Codex, driven by the "Generate Runner Prompt"
output in the /operator UI) ends by printing a JSON block matching the
schema in frontend/lib/generateRunnerPrompt.ts. This script takes that JSON
(as a file or via stdin) and writes it into CommandPilot through the
existing, already-authenticated /api/work-orders endpoints — no new backend
code, this is purely a thin HTTP client.

Zero third-party dependencies on purpose (stdlib `urllib` only) so it runs
with any Python 3 interpreter without an `pip install` step — installing a
dependency is itself one of the actions that needs approval per this
project's safety rules (see docs/background-dev-team-system-design.md §5),
so a recorder script that needed one would be a bad first example.

Usage:
    python scripts/import_work_order_result.py result.json --token <TOKEN>
    cat result.json | python scripts/import_work_order_result.py --token <TOKEN>
    python scripts/import_work_order_result.py result.json --dry-run

Auth:
    Pass a Supabase access token via --token, or set COMMANDPILOT_API_TOKEN.
    See docs/background-dev-team-runbook.md for how to obtain one — it is
    your own already-authenticated session token, not a project secret.

Field name convention:
    The result JSON uses camelCase (matching the frontend domain model and
    the prompt that asked the runner to produce it). This script is the
    mapper back into the backend's snake_case API, mirroring
    frontend/lib/workOrderMapper.ts on the way in.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Retries only cover transient failures: 5xx (backend/DB hiccup, e.g. a
# socket blip talking to Supabase — confirmed to happen in practice, not
# hypothetical: a real import hit "[WinError 10035] A non-blocking socket
# operation could not be completed immediately" on a single artifact POST
# while 20 other calls in the same run succeeded) and URLError (connection-
# level issues). 4xx is never retried — a 401/404/422 means something is
# actually wrong with the request/auth, and retrying just wastes time.
_MAX_ATTEMPTS = 3
_RETRY_DELAY_S = 1.0

# Shared validation (clear missing-field/line-number errors) — the two
# scripts have no circular dependency: run_work_order.py imports from this
# file, this file imports from runner_adapters.base, and runner_adapters/
# never imports back from either.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_adapters.base import parse_and_validate_result, validate_result_against_order  # noqa: E402

# Windows consoles often default to a legacy codepage (cp1252) rather than
# UTF-8. Result JSON / activity log text can contain arbitrary Unicode (em
# dashes, arrows, German umlauts) since it comes from an LLM-driven runner —
# without this, a plain print() of that text crashes with
# UnicodeEncodeError the moment it hits a character cp1252 can't represent.
# reconfigure() is Python 3.7+; errors="replace" is a last-resort safety net
# so a truly exotic character degrades to "?" instead of crashing the run.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


class ImportError_(Exception):
    """Raised for a single failed API call — caught per-item so one bad
    step/log/artifact doesn't abort the whole import."""


def call_api(api_url: str, token: str, method: str, path: str, payload: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    url = f"{api_url.rstrip('/')}{path}"
    if dry_run:
        print(f"[dry-run] {method} {path}\n  {json.dumps(payload, ensure_ascii=False)}")
        return {}

    body = json.dumps(payload).encode("utf-8")

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == _MAX_ATTEMPTS:
                detail = exc.read().decode("utf-8", errors="replace")
                raise ImportError_(f"{method} {path} -> HTTP {exc.code}: {detail[:300]}") from exc
            last_exc = exc
        except urllib.error.URLError as exc:
            if attempt == _MAX_ATTEMPTS:
                raise ImportError_(f"{method} {path} -> connection failed: {exc.reason}") from exc
            last_exc = exc
        print(f"  (transient error on attempt {attempt}/{_MAX_ATTEMPTS} for {method} {path}, retrying: {last_exc})")
        time.sleep(_RETRY_DELAY_S)

    # Unreachable in practice (the loop always returns or raises above), but
    # keeps type-checkers and readers honest about the function's contract.
    raise ImportError_(f"{method} {path} -> failed after {_MAX_ATTEMPTS} attempts: {last_exc}")


def step_update_payload(step: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if step.get("status") is not None:
        payload["status"] = step["status"]
    if step.get("outputSummary") is not None:
        payload["output_summary"] = step["outputSummary"]
    if step.get("blockedReason") is not None:
        payload["blocked_reason"] = step["blockedReason"]
    return payload


def activity_log_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "level": entry["level"],
        "event_type": entry.get("eventType", entry.get("event_type", "runner_event")),
        "message": entry["message"],
    }
    if entry.get("agentRunId"):
        payload["agent_run_id"] = entry["agentRunId"]
    if entry.get("metadata"):
        payload["metadata"] = entry["metadata"]
    return payload


def artifact_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "type": artifact["type"],
        "title": artifact["title"],
    }
    if artifact.get("content") is not None:
        payload["content"] = artifact["content"]
    if artifact.get("filePath"):
        payload["file_path"] = artifact["filePath"]
    return payload


def review_package_payload(rp: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": rp["summary"],
        "files_changed": rp.get("filesChanged", []),
        "tests_run": rp.get("testsRun", []),
        "risks": rp.get("risks", []),
        "open_questions": rp.get("openQuestions", []),
        # The runner prompt's example schema is a single boolean, matching
        # the actual ReviewPackage model — a JSON array here is a mistake
        # in the input, not a valid alternate shape. Coerce defensively
        # rather than silently sending garbage to the API.
        "needs_human_review": bool(rp.get("needsHumanReview", True)),
        "recommended_next_step": rp.get("recommendedNextStep"),
        "verdict": rp["verdict"],
    }


def fetch_work_order(api_url: str, token: str, work_order_id: str) -> dict[str, Any]:
    url = f"{api_url.rstrip('/')}/api/work-orders/{work_order_id}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def import_result(result: dict[str, Any], api_url: str, token: str, dry_run: bool) -> int:
    work_order_id = result.get("workOrderId")
    if not work_order_id:
        print("ERROR: result JSON is missing required field 'workOrderId'", file=sys.stderr)
        return 1

    # Cross-check real step ids / valid status & verdict enums before a
    # single API call is made — see validate_result_against_order()'s
    # docstring. Best-effort: if the work order can't be fetched (e.g.
    # --dry-run with no real token, or a transient network issue), warn and
    # fall back to the shape-only validation already done by
    # parse_and_validate_result() rather than blocking the whole import on
    # a check that's explicitly a defense-in-depth extra.
    if not dry_run:
        try:
            order = fetch_work_order(api_url, token, work_order_id)
            validate_result_against_order(result, order, f"result JSON for {work_order_id}")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"WARNUNG: konnte Work Order für Cross-Validation nicht laden ({exc}) — überspringe Step-ID/Status-Check.", file=sys.stderr)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    failures = 0
    successes = 0

    for step in result.get("steps", []):
        step_id = step.get("id")
        if not step_id:
            print(f"SKIP step with no id: {step}", file=sys.stderr)
            failures += 1
            continue
        try:
            call_api(api_url, token, "PATCH", f"/api/work-orders/{work_order_id}/steps/{step_id}", step_update_payload(step), dry_run)
            print(f"OK   step {step_id} -> {step.get('status')}")
            successes += 1
        except ImportError_ as exc:
            print(f"FAIL step {step_id}: {exc}", file=sys.stderr)
            failures += 1

    for entry in result.get("activityLogs", []):
        try:
            call_api(api_url, token, "POST", f"/api/work-orders/{work_order_id}/activity-log", activity_log_payload(entry), dry_run)
            print(f"OK   activity log: {entry.get('eventType', entry.get('event_type'))}")
            successes += 1
        except ImportError_ as exc:
            print(f"FAIL activity log entry: {exc}", file=sys.stderr)
            failures += 1

    for artifact in result.get("artifacts", []):
        try:
            call_api(api_url, token, "POST", f"/api/work-orders/{work_order_id}/artifacts", artifact_payload(artifact), dry_run)
            print(f"OK   artifact: {artifact.get('title')}")
            successes += 1
        except ImportError_ as exc:
            print(f"FAIL artifact {artifact.get('title')}: {exc}", file=sys.stderr)
            failures += 1

    review_package = result.get("reviewPackage")
    if review_package:
        try:
            call_api(api_url, token, "PUT", f"/api/work-orders/{work_order_id}/review-package", review_package_payload(review_package), dry_run)
            print(f"OK   review package: verdict={review_package.get('verdict')}")
            successes += 1
        except ImportError_ as exc:
            print(f"FAIL review package: {exc}", file=sys.stderr)
            failures += 1

    final_status = result.get("finalStatus")
    if final_status:
        try:
            call_api(api_url, token, "PATCH", f"/api/work-orders/{work_order_id}", {"status": final_status}, dry_run)
            print(f"OK   work order final status -> {final_status}")
            successes += 1
        except ImportError_ as exc:
            print(f"FAIL setting final status: {exc}", file=sys.stderr)
            failures += 1

    print(f"\n{successes} succeeded, {failures} failed.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", nargs="?", help="Path to the result JSON file. Omit to read from stdin.")
    parser.add_argument("--api-url", default=os.environ.get("COMMANDPILOT_API_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("COMMANDPILOT_API_TOKEN"))
    parser.add_argument("--dry-run", action="store_true", help="Print the API calls that would be made without making them.")
    args = parser.parse_args()

    if not args.token and not args.dry_run:
        print("ERROR: no API token. Pass --token or set COMMANDPILOT_API_TOKEN.", file=sys.stderr)
        print("See docs/background-dev-team-runbook.md for how to obtain one.", file=sys.stderr)
        return 1

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"ERROR: result file not found: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8")
        source_desc = str(path)
    else:
        raw = sys.stdin.read()
        source_desc = "stdin"

    try:
        result = parse_and_validate_result(raw, source_desc)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return import_result(result, args.api_url, args.token or "", args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
