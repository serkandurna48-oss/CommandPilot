#!/usr/bin/env python3
"""Independent Judge stage (R2).

After an executor run finishes and its result has been imported — i.e. the
work order is `review_ready` — this module runs a SEPARATE, read-only
`claude` process that grades the executor's work against the work order's
acceptance criteria, one criterion at a time. It is deliberately NOT the
executor and does not trust the executor's own self-report: its inputs are
the work order's goal + acceptance criteria, the real `git diff` of what
changed, and the test output artifact (if any) — the executor's review
package is at most a hint, never the source of truth.

Invoked by scripts/run_work_order_daemon.py once a claimed work order reaches
`review_ready` (see that file's maybe_run_judge()). Adapter-independent: it
grades the resulting diff, not how the diff was produced.

Judge process contract (hard):
- A separate `claude -p` invocation, model from env JUDGE_MODEL (default
  "opus"), reusing the same executable lookup as the runner adapter
  (runner_adapters.claude_code._resolve_claude_executable).
- READ-ONLY: --allowedTools "Read,Grep,Glob" — no Bash, no Edit/Write, and
  deliberately never --dangerously-skip-permissions. The judge inspects, it
  never changes anything.
- Timeout from env JUDGE_TIMEOUT_SECONDS (default 600).

Output contract (strict JSON):
    {"criteria": [{"criterion": str, "verdict": "pass|fail|unclear",
                   "evidence": str}],
     "overall": "pass|fail"}
`overall` is PASS only if every criterion is `pass` — recomputed here from
the per-criterion verdicts, never taken on trust from the model, so an
"unclear" or a model that claims overall=pass while a criterion failed both
resolve to overall=fail (fail-closed).

Side effects on a successful judgement:
- A type="review", title="Judge-Urteil" artifact holding the verdict JSON.
- An activity-log line.
- overall=fail → transition review_ready -> rework_requested, with the list
  of failed criteria as the reason. overall=pass → stays review_ready (a
  human still accepts it; the judge never auto-accepts).

Fail-closed on ANY judge problem (no `claude` on PATH, timeout, unparseable
output, malformed verdict, missing criteria): the work order is left exactly
as it was (review_ready), and a level="warning" activity-log line
("Judge nicht gelaufen – manuell prüfen") is written. The judge can block an
acceptance, it can never manufacture one.

Toggle with env JUDGE_ENABLED (default on; "0"/"false"/"no"/"off" disables —
the daemon skips calling this entirely).

Stdlib-only (urllib + subprocess), matching scripts/run_work_order.py and
scripts/run_work_order_daemon.py — never imports the backend package.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_adapters.claude_code import _resolve_claude_executable  # noqa: E402

DEFAULT_MODEL = "opus"
DEFAULT_TIMEOUT_SECONDS = 600
# Keep the diff fed to the judge bounded — a runaway diff would both blow the
# judge's context budget and its cost. The judge can always Read/Grep the
# repo itself for anything the truncated diff cut off.
_MAX_DIFF_CHARS = 20000
_MAX_TEST_OUTPUT_CHARS = 8000
_MAX_REASON_CHARS = 1900  # work_orders transition reason column is capped at 2000


class JudgeError(Exception):
    """Any reason the judge could not produce a trustworthy verdict —
    always handled fail-closed by run_judge() (order stays review_ready)."""


def judge_enabled() -> bool:
    return os.environ.get("JUDGE_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off")


# ─── API (stdlib urllib) ──────────────────────────────────────────────────────
def _call_api(api_url: str, token: str, method: str, path: str,
              payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    url = f"{api_url.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


# ─── Inputs ───────────────────────────────────────────────────────────────────
def gather_diff(repo_root: Path | str = REPO_ROOT) -> str:
    """The real git diff of the executor's work — both the unstaged and
    staged changes in the control-plane repo. Runs on the HARNESS side
    (plain subprocess), which is unrelated to the judge model's read-only
    tool restriction: that restriction is about what the `claude` process may
    do, not what this orchestration script may gather to feed it."""
    parts: list[str] = []
    for cmd in (["git", "diff"], ["git", "diff", "--staged"]):
        try:
            result = subprocess.run(
                cmd, cwd=str(repo_root), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
        except Exception:
            continue
        if result.stdout and result.stdout.strip():
            parts.append(result.stdout)
    return "\n".join(parts)


def _latest_artifact_content(artifacts: list[dict], artifact_type: str) -> str:
    """The content of the most recent artifact of the given type, or ""."""
    matching = [a for a in artifacts if a.get("type") == artifact_type and a.get("content")]
    if not matching:
        return ""
    # artifacts come back ordered by created_at ascending (see
    # work_order_service.get_work_order_children) — take the last.
    return matching[-1].get("content") or ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [gekürzt, {len(text) - limit} weitere Zeichen ausgelassen]"


# ─── Prompt ───────────────────────────────────────────────────────────────────
def build_judge_prompt(goal: str, criteria: list[str], diff_text: str, test_output: str) -> str:
    lines: list[str] = []
    lines.append("Du bist ein UNABHÄNGIGER Prüfer (Judge) für das Ergebnis eines Coding-Agents.")
    lines.append("Du hast NICHT selbst gearbeitet und übernimmst NICHTS ungeprüft vom Executor.")
    lines.append("Deine einzige Aufgabe: prüfe Kriterium für Kriterium, ob das vorliegende Ergebnis es erfüllt.")
    lines.append("Du darfst ausschließlich lesen (Read/Grep/Glob) — nichts ändern, nichts ausführen.")
    lines.append("")
    lines.append("## Ziel des Work Orders")
    lines.append(goal or "(kein Ziel hinterlegt)")
    lines.append("")
    lines.append("## Akzeptanzkriterien (einzeln zu bewerten)")
    for i, c in enumerate(criteria, 1):
        lines.append(f"{i}. {c}")
    lines.append("")
    lines.append("## git diff des Executor-Laufs")
    lines.append("```diff")
    lines.append(_truncate(diff_text, _MAX_DIFF_CHARS) if diff_text.strip() else "(kein Diff — keine Änderungen gefunden)")
    lines.append("```")
    lines.append("")
    lines.append("## Test-/Check-Ausgabe (falls vorhanden, nur als Hinweis)")
    lines.append(_truncate(test_output, _MAX_TEST_OUTPUT_CHARS) if test_output.strip() else "(keine Test-Ausgabe hinterlegt)")
    lines.append("")
    lines.append("Du darfst mit Read/Grep/Glob zusätzlich im Repo nachsehen, wenn der Diff allein nicht reicht.")
    lines.append("")
    lines.append("## Ausgabe — AUSSCHLIESSLICH dieses JSON-Objekt, nichts davor, nichts danach:")
    lines.append("""{
  "criteria": [
    {
      "criterion": "<der exakte Kriteriumstext von oben>",
      "verdict": "pass | fail | unclear",
      "evidence": "<kurze, konkrete Begründung mit Bezug auf Diff/Code/Tests>"
    }
  ],
  "overall": "pass | fail"
}""")
    lines.append("")
    lines.append('Regeln: "pass" nur, wenn das Kriterium nachweisbar erfüllt ist. "fail", wenn nachweisbar nicht erfüllt. '
                 '"unclear", wenn du es aus dem Material nicht sicher entscheiden kannst (zähle NICHT als bestanden). '
                 '"overall" ist "pass" nur, wenn JEDES Kriterium "pass" ist, sonst "fail". '
                 "Für jedes Kriterium von oben genau ein Eintrag.")
    return "\n".join(lines)


# ─── Judge subprocess ─────────────────────────────────────────────────────────
def build_judge_cli_args(model: str, claude_path: str) -> list[str]:
    """The exact argument list for the read-only judge invocation. Factored
    out so it can be asserted on directly (no subprocess needed): read-only
    tools only, the configured model, and — importantly — NOT Bash, NOT
    Edit/Write, and NOT --dangerously-skip-permissions."""
    return [
        claude_path,
        "-p",
        "--output-format", "json",
        "--model", model,
        "--allowedTools", "Read,Grep,Glob",
    ]


def _extract_verdict_json(text: str) -> dict:
    """Parse the judge's text output into a dict. Tolerates a bare JSON
    object or one wrapped in a ```json fence; anything else is a JudgeError
    (handled fail-closed by the caller)."""
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # strip a markdown code fence if present
    if "```" in stripped:
        inner = stripped.split("```", 2)
        if len(inner) >= 2:
            candidate = inner[1]
            if candidate.startswith("json"):
                candidate = candidate[len("json"):]
            try:
                return json.loads(candidate.strip())
            except json.JSONDecodeError:
                pass
    # last resort: last balanced {...} block
    end = stripped.rfind("}")
    start = stripped.find("{")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise JudgeError("Judge-Ausgabe ist kein gültiges JSON")


def _parse_claude_output(stdout: str) -> dict:
    """claude --output-format json wraps the model's text in a `result`
    field; accept that wrapper OR (for tests / other shapes) a direct verdict
    object."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"claude-Ausgabe nicht parsebar: {exc}") from exc
    if isinstance(data, dict) and "criteria" not in data and "result" in data:
        result_text = data.get("result")
        if not isinstance(result_text, str):
            raise JudgeError("claude-Wrapper hat kein textuelles 'result'")
        return _extract_verdict_json(result_text)
    if isinstance(data, dict):
        return data
    raise JudgeError("Unerwartete claude-Ausgabeform")


def _validate_and_normalize(verdict: dict) -> dict:
    """Shape-check the verdict and RECOMPUTE overall from the per-criterion
    verdicts (never trust the model's own `overall`)."""
    if not isinstance(verdict, dict):
        raise JudgeError("Urteil ist kein Objekt")
    criteria = verdict.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise JudgeError("Urteil enthält keine Kriterien")
    normalized: list[dict] = []
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            raise JudgeError(f"criteria[{i}] ist kein Objekt")
        criterion = c.get("criterion")
        v = c.get("verdict")
        if not criterion or not isinstance(criterion, str):
            raise JudgeError(f"criteria[{i}] hat keinen 'criterion'-Text")
        if v not in ("pass", "fail", "unclear"):
            raise JudgeError(f"criteria[{i}].verdict ungültig: {v!r}")
        normalized.append({
            "criterion": criterion,
            "verdict": v,
            "evidence": c.get("evidence") or "",
        })
    overall = "pass" if all(c["verdict"] == "pass" for c in normalized) else "fail"
    return {"criteria": normalized, "overall": overall}


def run_claude_judge(prompt: str, model: str, timeout_s: int, claude_path: str,
                     cwd: str | None = None) -> dict:
    """Run the read-only judge and return the normalized verdict dict. Raises
    JudgeError on no-output/timeout/unparseable/malformed — the caller turns
    that into the fail-closed path."""
    args = build_judge_cli_args(model, claude_path)
    try:
        result = subprocess.run(
            args, input=prompt, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_s,
            cwd=cwd or str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        raise JudgeError(f"Judge-Timeout nach {timeout_s}s") from exc
    except FileNotFoundError as exc:
        raise JudgeError(f"claude nicht ausführbar: {exc}") from exc
    if result.returncode != 0:
        raise JudgeError(f"claude beendete mit exit_code={result.returncode}: {(result.stderr or '')[:300]}")
    verdict = _parse_claude_output(result.stdout)
    return _validate_and_normalize(verdict)


# ─── Writeback helpers ────────────────────────────────────────────────────────
def _append_log(api_url: str, token: str, work_order_id: str, level: str,
                event_type: str, message: str) -> None:
    try:
        _call_api(api_url, token, "POST", f"/api/work-orders/{work_order_id}/activity-log",
                  {"level": level, "event_type": event_type, "message": message[:2000]})
    except Exception as exc:  # audit line is best-effort, never fatal
        print(f"WARNUNG: Judge-Activity-Log konnte nicht geschrieben werden: {exc}", file=sys.stderr)


# ─── Orchestration ────────────────────────────────────────────────────────────
def run_judge(
    api_url: str,
    token: str,
    work_order_id: str,
    *,
    repo_root: Path | str = REPO_ROOT,
    model: str | None = None,
    timeout_s: int | None = None,
    claude_path: str | None = None,
    diff_fetcher: Callable[[Path | str], str] = gather_diff,
) -> dict:
    """Judge one review_ready work order. Returns a small status dict for the
    caller/logs — all real effects go through the API. Never raises for a
    judge problem: those are handled fail-closed (warning log, order
    untouched)."""
    model = model or os.environ.get("JUDGE_MODEL", DEFAULT_MODEL)
    if timeout_s is None:
        try:
            timeout_s = int(os.environ.get("JUDGE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        except ValueError:
            timeout_s = DEFAULT_TIMEOUT_SECONDS

    try:
        order = _call_api(api_url, token, "GET", f"/api/work-orders/{work_order_id}")
    except Exception as exc:
        _append_log(api_url, token, work_order_id, "warning", "judge_not_run",
                    f"Judge nicht gelaufen – manuell prüfen. (Work Order nicht abrufbar: {exc})")
        return {"status": "judge_error", "reason": "fetch_failed", "error": str(exc)}

    criteria = [c for c in (order.get("acceptance_criteria") or []) if isinstance(c, str) and c.strip()]
    if not criteria:
        # R1 makes this impossible for a queued order, but a legacy order
        # could still reach here — fail-closed rather than vacuously "pass".
        _append_log(api_url, token, work_order_id, "warning", "judge_not_run",
                    "Judge nicht gelaufen – manuell prüfen. (Keine Akzeptanzkriterien hinterlegt.)")
        return {"status": "judge_error", "reason": "no_criteria"}

    goal = order.get("goal") or ""
    artifacts = order.get("artifacts") or []
    test_output = _latest_artifact_content(artifacts, "test_output")
    diff_from_artifact = _latest_artifact_content(artifacts, "diff")
    live_diff = diff_fetcher(repo_root)
    diff_text = live_diff or diff_from_artifact
    if live_diff and diff_from_artifact and diff_from_artifact not in live_diff:
        diff_text = live_diff + "\n\n# --- zusätzlich: vom Executor gemeldeter Diff-Artefakt ---\n" + diff_from_artifact

    prompt = build_judge_prompt(goal, criteria, diff_text, test_output)

    try:
        resolved_path = claude_path or _resolve_claude_executable()
        verdict = run_claude_judge(prompt, model, timeout_s, resolved_path, cwd=str(repo_root))
    except JudgeError as exc:
        _append_log(api_url, token, work_order_id, "warning", "judge_not_run",
                    f"Judge nicht gelaufen – manuell prüfen. ({exc})")
        return {"status": "judge_error", "reason": "judge_failed", "error": str(exc)}
    except Exception as exc:  # e.g. _resolve_claude_executable's FileNotFoundError
        _append_log(api_url, token, work_order_id, "warning", "judge_not_run",
                    f"Judge nicht gelaufen – manuell prüfen. ({type(exc).__name__}: {exc})")
        return {"status": "judge_error", "reason": "judge_unavailable", "error": str(exc)}

    # Persist the verdict as a review artifact (always — pass or fail).
    try:
        _call_api(api_url, token, "POST", f"/api/work-orders/{work_order_id}/artifacts",
                  {"type": "review", "title": "Judge-Urteil", "content": json.dumps(verdict, ensure_ascii=False)})
    except Exception as exc:
        # If we can't even persist the verdict, do NOT silently proceed to a
        # transition the user can't see the reason for — fail-closed.
        _append_log(api_url, token, work_order_id, "warning", "judge_not_run",
                    f"Judge gelaufen, aber Urteil nicht speicherbar – manuell prüfen. ({exc})")
        return {"status": "judge_error", "reason": "artifact_write_failed", "error": str(exc)}

    if verdict["overall"] == "pass":
        _append_log(api_url, token, work_order_id, "info", "judge_passed",
                    "Judge: alle Akzeptanzkriterien bestanden. Bleibt review_ready für die menschliche Abnahme.")
        return {"status": "pass", "verdict": verdict}

    failed = [c["criterion"] for c in verdict["criteria"] if c["verdict"] != "pass"]
    reason = _truncate("Judge: nicht abgenommen. Nicht erfüllte Kriterien: " + "; ".join(failed), _MAX_REASON_CHARS)
    _append_log(api_url, token, work_order_id, "info", "judge_failed", reason)
    try:
        _call_api(api_url, token, "PATCH", f"/api/work-orders/{work_order_id}",
                  {"status": "rework_requested", "source": "harness", "reason": reason})
    except Exception as exc:
        _append_log(api_url, token, work_order_id, "warning", "judge_transition_failed",
                    f"Judge-Urteil 'fail', aber Übergang nach rework_requested fehlgeschlagen – manuell prüfen. ({exc})")
        return {"status": "judge_error", "reason": "transition_failed", "error": str(exc), "verdict": verdict}
    return {"status": "fail", "verdict": verdict, "failed_criteria": failed}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the independent Judge stage against a review_ready work order.")
    parser.add_argument("work_order_id")
    parser.add_argument("--api-url", default=os.environ.get("COMMANDPILOT_API_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("COMMANDPILOT_API_TOKEN"))
    args = parser.parse_args(argv)

    if not judge_enabled():
        print("JUDGE_ENABLED ist aus — nichts zu tun.")
        return 0
    if not args.token:
        print("ERROR: kein Token (--token oder COMMANDPILOT_API_TOKEN).", file=sys.stderr)
        return 1

    result = run_judge(args.api_url, args.token, args.work_order_id)
    print(json.dumps(result.get("verdict", result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
