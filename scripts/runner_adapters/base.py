"""RunnerAdapter contract — the seam CommandPilot orchestrates against.

CommandPilot is the Control Plane: work orders, approval scopes, execution
plans, activity logs, review packages, safety, context. It does not become
a coding agent itself. A RunnerAdapter is whatever actually does the work —
Claude Code, Codex, later possibly OpenClaw, or a fully custom local
script. Swapping the adapter must never require touching the Control Plane
(the orchestration in run_work_order.py, or the backend) — only the
adapter implementation.

See docs/runner-adapter-contract.md for the full rationale, the interface
every adapter must implement, and what an adapter must never do.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

# "yes": prepare()+execute() are both real and fully unattended.
# "no": no native execution at all (manual_prompt; also the honest default
#   for anything unresearched, like openclaw).
# "semi_auto": execute() genuinely attempts real automation but has a known,
#   documented gap that can silently limit what it does (e.g. Claude Code's
#   one-time interactive workspace-trust requirement, or permission prompts
#   with no TTY to answer them) — the caller should not treat a "semi_auto"
#   run's success as unconditional the way it would a "yes" adapter's.
AutoExecuteCapability = Literal["yes", "no", "semi_auto"]

# ─── Safety — duplicated on purpose ──────────────────────────────────────────
# Same conceptual list as frontend/lib/safetyRules.ts (UI display) and
# backend/app/core/safety_rules.py (server-side enforcement at ApprovalScope
# creation time). This is the scripts/-side canonical copy — run_work_order.py
# and every adapter import it from here rather than each keeping their own,
# which is what OP-Runner-002 did before this refactor. Keep all three
# (frontend/backend/scripts) in sync by hand; see
# docs/background-dev-team-system-design.md.
BLOCKED_ACTION_KEYWORDS = [
    "deploy", "production data", "prod data", "secret", "send email",
    "e-mail senden", "email senden", "payment", "zahlung", "stripe",
    "reset --hard", "force push", "force-push", "clean -f",
    "direct to main", "direkt auf main", "push to main",
    "export user data", "userdaten exportieren",
]


def find_blocked_keyword(text: str) -> str | None:
    lowered = text.lower()
    for kw in BLOCKED_ACTION_KEYWORDS:
        if kw in lowered:
            return kw
    return None


SAFETY_AUTONOMOUS_ALLOWED = [
    "Repo lesen", "Plan erstellen", "Code ändern innerhalb Scope",
    "Tests / Lint / Typecheck ausführen", "Lokale Artifacts erzeugen",
    "Review Package schreiben",
]
SAFETY_NEEDS_APPROVAL = [
    "Dependencies installieren", "Externe Services anbinden",
    "Migrationen ausführen", "Push / PR erstellen",
    "Laufzeit- oder Kostenlimit erhöhen", "Große Architekturänderungen",
]
SAFETY_BLOCKED_ALWAYS = [
    "Deployments", "Production-Daten ändern", "Secrets anzeigen oder loggen",
    "E-Mails senden", "Zahlungen auslösen",
    "Destructive Git-Kommandos (reset --hard, force push, clean -f)",
    "Direkte Änderungen auf main", "Userdaten exportieren",
]

AGENT_ROLES = [
    "Product Agent — Ziel, Nutzerflow, Akzeptanzkriterien prüfen/verfeinern.",
    "Architect Agent — technische Umsetzung, Risiken, Architekturentscheidungen.",
    "Coder Agent — Codeänderungen innerhalb des Approval Scope.",
    "QA Agent — Tests / Lint / Typecheck ausführen.",
    "Reviewer Agent — Bugs, Security, Edge Cases, Scope-Verletzungen.",
    "Reporter Agent — Review Package + Ergebnis-JSON erstellen.",
]

# Valid as JSON on its own (every value is a descriptive string) — doubles
# as both the prompt's schema block and the literal contents of
# result.schema.json in an adapter's session folder.
RESULT_JSON_SCHEMA = """{
  "workOrderId": "string — exactly the id from '## Work Order Kontext' below",
  "finalStatus": "review_ready | blocked | failed",
  "steps": [
    {
      "id": "string — exactly one of the step ids from '## Ticketplan' below",
      "status": "completed | blocked | failed | skipped",
      "outputSummary": "string | null",
      "blockedReason": "string | null — required if status is 'blocked'"
    }
  ],
  "activityLogs": [
    {
      "level": "info | warning | error | approval_required",
      "eventType": "string — short machine-readable label, e.g. \\"run_completed\\"",
      "message": "string",
      "agentRunId": "string | null"
    }
  ],
  "artifacts": [
    {
      "type": "plan | diff | test_output | review | summary | screenshot | prompt",
      "title": "string",
      "content": "string | null"
    }
  ],
  "reviewPackage": {
    "summary": "string — 1-3 Sätze, was wurde getan",
    "filesChanged": ["string — Pfade relativ zum Repo-Root"],
    "testsRun": ["string — z.B. \\"tsc --noEmit\\", \\"next build\\""],
    "risks": ["string — alles, was ein Mensch vor dem Approve wissen sollte"],
    "openQuestions": ["string — unklare Punkte, die der Judge nicht selbst entscheiden konnte"],
    "needsHumanReview": true,
    "recommendedNextStep": "string",
    "verdict": "ready_for_review | needs_fix | blocked | unsafe"
  }
}"""


def _render_scope_block(scope: dict) -> list[str]:
    """The "## Approval Scope" section — shared verbatim by
    build_runner_prompt() (whole-order prompt) and build_step_prompt()
    (single-step prompt) so the two never drift the way
    BLOCKED_ACTION_KEYWORDS' three copies already do by necessity (that one
    spans languages/processes; this one doesn't need to)."""
    lines: list[str] = []
    lines.append("## Approval Scope (dieses Work Orders)")
    lines.append("")
    lines.append("**Autonom erlaubt (kein Nachfragen nötig):**")
    for a in scope.get("allowed_actions", []):
        lines.append(f"- {a}")
    lines.append("")
    lines.append('**Braucht Approval (stoppen, activityLogs-Eintrag mit level="approval_required", betroffenen Step auf status="blocked"):**')
    for a in scope.get("requires_approval", []):
        lines.append(f"- {a}")
    lines.append("")
    lines.append("**Blockiert (niemals ausführen, auch nicht mit Approval in dieser Session):**")
    for a in scope.get("blocked_actions", []):
        lines.append(f"- {a}")
    lines.append("")
    return lines


def _render_safety_block() -> list[str]:
    """The "## Harte Safety-Regeln" section — order-independent, identical
    regardless of scope/step, shared by both prompt builders."""
    lines: list[str] = []
    lines.append("## Harte Safety-Regeln (gelten IMMER, unabhängig vom Approval Scope oben)")
    lines.append("")
    lines.append("Autonom erlaubt:")
    for a in SAFETY_AUTONOMOUS_ALLOWED:
        lines.append(f"- {a}")
    lines.append("")
    lines.append("Braucht Approval:")
    for a in SAFETY_NEEDS_APPROVAL:
        lines.append(f"- {a}")
    lines.append("")
    lines.append("Blockiert — niemals, unter keinen Umständen:")
    for a in SAFETY_BLOCKED_ALWAYS:
        lines.append(f"- {a}")
    lines.append("")
    return lines


def _render_hard_stop_block() -> list[str]:
    """The "## HARTER STOPP bei Scope-Verletzung" section — shared by both
    prompt builders, unchanged regardless of whether the model sees the
    whole ticketplan or just one step."""
    lines: list[str] = []
    lines.append("## HARTER STOPP bei Scope-Verletzung")
    lines.append('Wenn eine Aktion nötig wird, die oben als "Braucht Approval" oder "Blockiert" gelistet ist:')
    lines.append("1. SOFORT stoppen. Keinen weiteren Code ändern, keine weitere Aktion ausführen.")
    lines.append('2. Den aktuellen Step auf status="blocked" setzen, blockedReason mit der konkreten Aktion füllen, die den Stopp ausgelöst hat.')
    lines.append('3. Einen activityLogs-Eintrag mit level="approval_required" hinzufügen, der die Aktion und den Grund benennt.')
    lines.append('4. Im finalen Ergebnis-JSON finalStatus="blocked" setzen — niemals "review_ready" vortäuschen, um weiterzukommen.')
    lines.append("Ein blockierter Step ist ein gutes, erwartetes Ergebnis — kein Fehler, den es zu vermeiden gilt.")
    lines.append("")
    return lines


def build_runner_prompt(order: dict) -> str:
    """Renders a work order (raw snake_case API aggregate) into the
    complete runner prompt text. Adapter-agnostic — every adapter that
    hands text to an LLM-driven runner uses this same builder; what
    differs between adapters is how the text gets there (paste vs. CLI
    invocation) and how the result comes back, not the content itself.

    This is a deliberate second implementation of
    frontend/lib/generateRunnerPrompt.ts (line-by-line ported, not
    imported) — see docs/background-dev-team-system-design.md §13 for why
    a cross-language import wasn't practical here. Keep both in sync.
    """
    scope = order.get("approval_scope") or {}
    steps = order.get("steps") or []
    lines: list[str] = []

    lines.append(f"# Work Order: {order['title']}")
    lines.append("")
    lines.append("Du bist ein autonomer Coding-Agent (Judge + Executor-Team) mit einem klar begrenzten Arbeitsauftrag.")
    lines.append("Halte dich strikt an den Approval Scope unten. Bei Unklarheit im erlaubten Rahmen: selbst entscheiden und dokumentieren, nicht nachfragen.")
    lines.append("Arbeite den Ticketplan unten Schritt für Schritt ab, in der angegebenen Reihenfolge. Nicht mehrere Steps parallel bearbeiten.")
    lines.append("")

    lines.append("## Work Order Kontext")
    lines.append(f"workOrderId: {order['id']}")
    lines.append(f"Ziel: {order['goal']}")
    lines.append(f"Repo: {order['repo']}")

    # Control-Plane/Target-Repo split (OP-Runner-RepoPath-001). target_repo_path
    # is display/prompt text only — never used here or anywhere in this
    # script to cd into, read from, or execute anything at that path. Keep
    # in sync with frontend/lib/generateRunnerPrompt.ts's identical block.
    target_repo_path = order.get("target_repo_path")
    if target_repo_path:
        lines.append("Control Plane Repo: CommandPilot (hier läuft scripts/run_work_order.py, hier läuft auch der Result-Import)")
        target_line = f"Target Repo: {order.get('target_repo_name') or order['repo']}"
        target_line += f" (Pfad-Hinweis, rein informativ: {target_repo_path})"
        lines.append(target_line)
        lines.append("")
        lines.append("WICHTIG — Cross-Repo-Kontext, unbedingt beachten:")
        lines.append("- You are working in the target repository.")
        lines.append("- Do not expect CommandPilot scripts to exist here.")
        lines.append("- Do not write result.json inside the target repo unless explicitly instructed.")
        lines.append("- Return normal analysis/report, or write the result only to the CommandPilot tmp path if that path is accessible from here.")
    else:
        lines.append("Control Plane Repo: CommandPilot (kein separates Target Repo — Control Plane und Execution Context sind dasselbe Repo)")

    if scope.get("allowed_paths"):
        lines.append(f"Erlaubte Pfade: {', '.join(scope['allowed_paths'])}")
    if scope.get("blocked_paths"):
        lines.append(f"Gesperrte Pfade (niemals anfassen): {', '.join(scope['blocked_paths'])}")
    cost_part = f", max. ${scope['max_cost_usd']}" if scope.get("max_cost_usd") else ""
    lines.append(
        f"Zeitlimit: {order['time_limit_minutes']} Minuten (Approval Scope: max. "
        f"{scope.get('max_runtime_minutes')} Minuten{cost_part}). Überschritten → stoppen, "
        'finalStatus="blocked", aktuellen Stand ins Ergebnis-JSON.'
    )
    lines.append("")

    lines.append("## Akzeptanzkriterien (Work Order gesamt)")
    for c in order.get("acceptance_criteria", []):
        lines.append(f"- [ ] {c}")
    lines.append("")

    missing_context = order.get("missing_context") or []
    if missing_context:
        lines.append("## Fehlender Kontext (bereits bekannt)")
        lines.append('Diese Punkte fehlen noch — falls nicht bereitgestellt, NICHT raten. finalStatus="blocked", blockedReason auf dem betroffenen Step setzen:')
        for m in missing_context:
            req = " (erforderlich)" if m.get("required", True) else " (optional)"
            lines.append(f"- {m['label']}{req}")
        lines.append("")

    lines.append("## Ticketplan (in dieser Reihenfolge abarbeiten)")
    if not steps:
        lines.append("(Kein Ticketplan hinterlegt — arbeite direkt anhand der Akzeptanzkriterien oben und der Agentenrollen unten.)")
    else:
        for s in steps:
            lines.append(f"### Step {s['order_index'] + 1}: {s['title']}  `id: {s['id']}`  (Rolle: {s['assigned_role']})")
            if s.get("description"):
                lines.append(s["description"])
            crit = s.get("acceptance_criteria") or []
            if crit:
                lines.append("Akzeptanzkriterien für diesen Step:")
                for c in crit:
                    lines.append(f"- [ ] {c}")
            lines.append("")

    lines.extend(_render_scope_block(scope))

    lines.append("## Agentenrollen (nacheinander durchlaufen, pro Ticketplan-Step)")
    for r in AGENT_ROLES:
        lines.append(f"- {r}")
    lines.append("")

    lines.extend(_render_safety_block())
    lines.extend(_render_hard_stop_block())

    lines.append("## Reporting-Anforderung")
    lines.append("- Jede Aktion (auch Zwischenschritte) als activityLogs-Eintrag.")
    lines.append("- Jeder abgeschlossene, blockierte oder fehlgeschlagene Ticketplan-Step erscheint im steps-Array des Ergebnis-JSON — mit seiner exakten id von oben.")
    lines.append('- Am Ende IMMER das komplette Ergebnis-JSON ausgeben — auch bei "blocked" oder "failed".')
    lines.append("- Keine Secrets lesen, ausgeben oder ins Log schreiben — auch nicht auszugsweise oder maskiert.")
    lines.append("")

    lines.append("## Ergebnis-JSON (Pflicht als letzte Ausgabe der Session)")
    lines.append("Dieses JSON wird 1:1 in `python scripts/run_work_order.py <id> --mode import-result` eingelesen — Feldnamen exakt einhalten:")
    lines.append("```json")
    lines.append(RESULT_JSON_SCHEMA)
    lines.append("```")
    lines.append("")
    recommended = order.get("recommended_next_step") or "nächster sinnvoller Schritt für Serkan"
    lines.append(f'reviewPackage.recommendedNextStep sollte konkret sein, z.B.: "{recommended}"')
    lines.append("")
    lines.append("## Hinweis: lokale Runner-Session")
    lines.append(f"Dieser Prompt wurde vom lokalen Runner-Harness (scripts/run_work_order.py) erzeugt und liegt unter tmp/work-order-runs/{order['id']}/prompt.md.")
    lines.append("Speichere das Ergebnis-JSON dort als result.json und importiere es mit:")
    lines.append(f"  python scripts/run_work_order.py {order['id']} --mode import-result")

    return "\n".join(lines)


# Deliberately smaller than RESULT_JSON_SCHEMA: a per-step prompt asks for
# exactly what one step's run can honestly report. finalStatus/reviewPackage
# are asked for on the WHOLE-order prompt only — asking a single-step call
# to also judge whether the ENTIRE work order is review-ready would either
# be meaningless (it hasn't seen the other steps' real outcomes) or invite
# exactly the kind of premature "review_ready" claim
# parse_and_validate_result() already guards against on the whole-order
# path. The harness (run_work_order.py's _run_step_by_step()) synthesizes
# finalStatus/reviewPackage itself once every step has actually run.
STEP_RESULT_JSON_SCHEMA = """{
  "workOrderId": "string — exactly the id from '## Work Order Kontext' below",
  "steps": [
    {
      "id": "string — exactly the id of THIS step from '## Dieser Step' below, exactly one entry",
      "status": "completed | blocked | failed | skipped",
      "outputSummary": "string | null",
      "blockedReason": "string | null — required if status is 'blocked'"
    }
  ],
  "activityLogs": [
    {
      "level": "info | warning | error | approval_required",
      "eventType": "string — short machine-readable label, e.g. \\"run_completed\\"",
      "message": "string",
      "agentRunId": "string | null"
    }
  ],
  "artifacts": [
    {
      "type": "plan | diff | test_output | review | summary | screenshot | prompt",
      "title": "string",
      "content": "string | null"
    }
  ]
}"""


def build_step_prompt(order: dict, step: dict, prior_steps: list[dict]) -> str:
    """Single-step sibling of build_runner_prompt() — used by the per-step
    execution path (run_work_order.py's _run_step_by_step(), adapters'
    execute_step()). Renders the SAME work-order/scope/safety context as
    the whole-order prompt (via the shared _render_*_block() helpers above,
    so the two never drift on what's allowed/blocked), but only THIS step's
    detail plus a compact summary of prior steps already run — never the
    full remaining ticketplan, and never prior steps' full transcripts,
    only their outputSummary. This is the deliberate cost control: prompt
    size per call grows with the number of PRIOR STEPS' short summaries,
    not with total conversation history.

    `prior_steps`: the subset of order['steps'] that already ran, each with
    at least id/title/status/outputSummary populated by the harness from
    what it already wrote back to the API — the model is never asked to
    re-derive or re-state what earlier steps did.
    """
    scope = order.get("approval_scope") or {}
    lines: list[str] = []

    lines.append(f"# Work Order: {order['title']} — Step: {step['title']}")
    lines.append("")
    lines.append("Du bist ein autonomer Coding-Agent (Judge + Executor-Team) mit einem klar begrenzten Arbeitsauftrag.")
    lines.append("Halte dich strikt an den Approval Scope unten.")
    lines.append("Bearbeite AUSSCHLIESSLICH den unten beschriebenen Step. Nicht vorgreifen, nicht andere Steps anfassen.")
    lines.append("")

    lines.append("## Work Order Kontext")
    lines.append(f"workOrderId: {order['id']}")
    lines.append(f"Ziel (gesamtes Work Order): {order['goal']}")
    lines.append(f"Repo: {order['repo']}")

    target_repo_path = order.get("target_repo_path")
    if target_repo_path:
        lines.append("Control Plane Repo: CommandPilot (hier läuft scripts/run_work_order.py, hier läuft auch der Result-Import)")
        target_line = f"Target Repo: {order.get('target_repo_name') or order['repo']}"
        target_line += f" (Pfad-Hinweis, rein informativ: {target_repo_path})"
        lines.append(target_line)
        lines.append("")
        lines.append("WICHTIG — Cross-Repo-Kontext, unbedingt beachten:")
        lines.append("- You are working in the target repository.")
        lines.append("- Do not expect CommandPilot scripts to exist here.")
    else:
        lines.append("Control Plane Repo: CommandPilot (kein separates Target Repo — Control Plane und Execution Context sind dasselbe Repo)")

    if scope.get("allowed_paths"):
        lines.append(f"Erlaubte Pfade: {', '.join(scope['allowed_paths'])}")
    if scope.get("blocked_paths"):
        lines.append(f"Gesperrte Pfade (niemals anfassen): {', '.join(scope['blocked_paths'])}")
    lines.append("")

    if prior_steps:
        lines.append("## Bereits erledigte Steps (Kontext, nicht erneut bearbeiten)")
        for p in prior_steps:
            summary = p.get("outputSummary") or p.get("output_summary") or "(kein outputSummary)"
            lines.append(f"- {p['title']} (`id: {p['id']}`, Status: {p['status']}): {summary}")
        lines.append("")

    lines.append("## Dieser Step")
    lines.append(f"### {step['title']}  `id: {step['id']}`  (Rolle: {step['assigned_role']})")
    if step.get("description"):
        lines.append(step["description"])
    crit = step.get("acceptance_criteria") or []
    if crit:
        lines.append("Akzeptanzkriterien für diesen Step:")
        for c in crit:
            lines.append(f"- [ ] {c}")
    lines.append("")

    lines.extend(_render_scope_block(scope))
    lines.extend(_render_safety_block())
    lines.extend(_render_hard_stop_block())

    lines.append("## Reporting-Anforderung")
    lines.append("- Jede Aktion (auch Zwischenschritte) als activityLogs-Eintrag.")
    lines.append(f"- Der Step im steps-Array des Ergebnis-JSON trägt exakt die id `{step['id']}` — genau ein Eintrag.")
    lines.append('- Am Ende IMMER das komplette Ergebnis-JSON ausgeben — auch bei "blocked" oder "failed".')
    lines.append("- Keine Secrets lesen, ausgeben oder ins Log schreiben — auch nicht auszugsweise oder maskiert.")
    lines.append("")

    lines.append("## Ergebnis-JSON (Pflicht als letzte Ausgabe der Session, NUR dieser eine Step)")
    lines.append("```json")
    lines.append(STEP_RESULT_JSON_SCHEMA)
    lines.append("```")

    return "\n".join(lines)


def build_result_example(order: dict) -> dict:
    steps = order.get("steps") or []
    return {
        "workOrderId": order["id"],
        "finalStatus": "review_ready",
        "steps": [
            {"id": s["id"], "status": "completed", "outputSummary": "TODO: was wurde in diesem Step gemacht?", "blockedReason": None}
            for s in steps
        ],
        "activityLogs": [
            {"level": "info", "eventType": "run_completed", "message": "TODO: kurze Beschreibung", "agentRunId": None}
        ],
        "artifacts": [
            {"type": "summary", "title": "TODO", "content": "TODO"}
        ],
        "reviewPackage": {
            "summary": "TODO",
            "filesChanged": [],
            "testsRun": [],
            "risks": [],
            "openQuestions": [],
            "needsHumanReview": True,
            "recommendedNextStep": "TODO",
            "verdict": "ready_for_review",
        },
    }


# Every adapter's collect_result() reads a result JSON from some source
# (file, stdin, an embedded field in a wrapper). Whichever adapter, whatever
# the source, the shape it hands back must satisfy this before
# import_work_order_result.import_result() ever sees it — a missing or
# malformed field there produces confusing per-item API failures instead of
# one clear message naming exactly what's wrong and where.
REQUIRED_RESULT_KEYS = ["workOrderId", "finalStatus", "steps", "activityLogs", "artifacts", "reviewPackage"]
VALID_FINAL_STATUSES = ("review_ready", "blocked", "failed")
VALID_STEP_STATUSES = ("completed", "blocked", "failed", "skipped")
VALID_REVIEW_VERDICTS = ("ready_for_review", "needs_fix", "blocked", "unsafe")
_DONE_STEP_STATUSES = {"completed", "skipped"}


def parse_and_validate_result(raw_text: str, source_desc: str) -> dict:
    """Parses `raw_text` as the work-order result JSON and validates its
    shape — including everything that can be checked from `data` alone,
    with no live work order required (OP-Import-Integrity-001). This is
    deliberately the *only* validation layer that is guaranteed to run: it
    executes before any network call, so it also runs when the caller has
    no token yet (e.g. --dry-run) and independent of whether the live work
    order can be fetched. `source_desc` is a human-readable label for where
    the text came from (a file path, "stdin", "claude_code --output-format
    json result field") — used only to make error messages point somewhere
    useful, never parsed itself.

    validate_result_against_order() below adds the remaining checks that
    genuinely need the real work order (real step ids, step completeness)
    and is best-effort — it can be skipped if the order can't be fetched.
    Per-step and reviewPackage shape checks must NOT live there: they used
    to, and a transient GET failure on the work order silently skipped
    them entirely, letting a malformed result (e.g. an invalid step status,
    or finalStatus='review_ready' with zero completed steps) sail through
    to import_result() and fail confusingly partway through, or not at
    all."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source_desc} at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{source_desc} must contain a JSON object at the top level, got {type(data).__name__}")

    missing = [k for k in REQUIRED_RESULT_KEYS if k not in data]
    if missing:
        raise ValueError(f"{source_desc} is missing required field(s): {', '.join(missing)}")

    if data["finalStatus"] not in VALID_FINAL_STATUSES:
        raise ValueError(
            f"{source_desc}: finalStatus must be one of {'|'.join(VALID_FINAL_STATUSES)}, "
            f"got {data['finalStatus']!r}"
        )

    if not isinstance(data["steps"], list):
        raise ValueError(f"{source_desc}: 'steps' must be a list, got {type(data['steps']).__name__}")

    has_progress = False
    for i, step in enumerate(data["steps"]):
        if not isinstance(step, dict):
            raise ValueError(f"{source_desc}: steps[{i}] must be an object, got {type(step).__name__}")
        status = step.get("status")
        if status not in VALID_STEP_STATUSES:
            raise ValueError(
                f"{source_desc}: steps[{i}].status must be one of {'|'.join(VALID_STEP_STATUSES)}, got {status!r}"
            )
        if status == "blocked" and not step.get("blockedReason"):
            raise ValueError(f"{source_desc}: steps[{i}] has status='blocked' but no blockedReason")
        if status in _DONE_STEP_STATUSES:
            has_progress = True

    review_package = data.get("reviewPackage") or {}
    if not review_package.get("summary"):
        raise ValueError(f"{source_desc}: reviewPackage.summary is missing or empty")
    if review_package.get("verdict") not in VALID_REVIEW_VERDICTS:
        raise ValueError(
            f"{source_desc}: reviewPackage.verdict must be one of {'|'.join(VALID_REVIEW_VERDICTS)}, "
            f"got {review_package.get('verdict')!r}"
        )

    # A work order can only be truthfully "ready for human review" if the
    # execution plan shows it actually got somewhere — a review_ready
    # result whose every step is still pending/blocked/failed would render
    # as a 0% progress bar in the operator UI while claiming to be done.
    if data["finalStatus"] == "review_ready" and not has_progress:
        raise ValueError(
            f"{source_desc}: finalStatus is 'review_ready' but no step has status 'completed' or "
            "'skipped' — progress would be 0%, which review_ready must never report"
        )

    return data


# A per-step result never carries finalStatus/reviewPackage (see
# STEP_RESULT_JSON_SCHEMA's docstring for why) — a separate required-key set
# from REQUIRED_RESULT_KEYS, not a subset check on it.
REQUIRED_STEP_RESULT_KEYS = ["workOrderId", "steps", "activityLogs", "artifacts"]


def parse_and_validate_step_result(raw_text: str, source_desc: str) -> dict:
    """Sibling of parse_and_validate_result() for the per-step execution
    path (run_work_order.py's _run_step_by_step()) — deliberately a
    separate function rather than a parameterized version of
    parse_and_validate_result(): the two validate different required-key
    sets (no finalStatus/reviewPackage here) and different invariants (a
    step result must contain EXACTLY one step, not "at least the real
    ones"). Keeping them separate means neither function's error messages
    have to hedge about which calling context produced them."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source_desc} at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{source_desc} must contain a JSON object at the top level, got {type(data).__name__}")

    missing = [k for k in REQUIRED_STEP_RESULT_KEYS if k not in data]
    if missing:
        raise ValueError(f"{source_desc} is missing required field(s): {', '.join(missing)}")

    if not isinstance(data["steps"], list) or len(data["steps"]) != 1:
        raise ValueError(
            f"{source_desc}: 'steps' must be a list with exactly one entry for a per-step result, "
            f"got {data['steps'] if isinstance(data['steps'], list) else type(data['steps']).__name__}"
        )

    step = data["steps"][0]
    if not isinstance(step, dict):
        raise ValueError(f"{source_desc}: steps[0] must be an object, got {type(step).__name__}")
    status = step.get("status")
    if status not in VALID_STEP_STATUSES:
        raise ValueError(f"{source_desc}: steps[0].status must be one of {'|'.join(VALID_STEP_STATUSES)}, got {status!r}")
    if status == "blocked" and not step.get("blockedReason"):
        raise ValueError(f"{source_desc}: steps[0] has status='blocked' but no blockedReason")

    return data


def validate_result_against_order(
    result: dict, order: dict, source_desc: str, require_all_steps: bool = True
) -> None:
    """Cross-checks an already shape-validated result (see
    parse_and_validate_result()/parse_and_validate_step_result(), one of
    which must run first) against the real work order it claims to belong
    to. Only the checks that genuinely need `order` live here: whether step
    ids are real, and — as of OP-Import-Integrity-001 — whether every real
    step got an update at all. Best-effort by design (see import_result()'s
    caller): if the live work order can't be fetched, this whole function
    is skipped and only the shape-validator's order-independent checks
    apply. Raises ValueError naming the exact offending field so a bad
    result aborts before any API call is made, instead of surfacing as a
    partial import failure.

    `require_all_steps`: True (default) preserves the original
    whole-order-result invariant unchanged for every existing caller. The
    per-step execution path (run_work_order.py's _run_step_by_step()) is
    the only caller that passes False — a single step's result is
    correctly missing updates for every OTHER step in the order; that's
    not a bug there the way it would be for a claimed-complete whole-order
    result."""
    order_steps = order.get("steps") or []
    valid_step_ids = {s["id"] for s in order_steps}
    result_step_ids: set[str] = set()

    for i, step in enumerate(result.get("steps", [])):
        step_id = step.get("id")
        if valid_step_ids and step_id not in valid_step_ids:
            raise ValueError(
                f"{source_desc}: steps[{i}].id {step_id!r} does not match any real step id on "
                f"work order {order.get('id')!r} — known step ids: {sorted(valid_step_ids)}"
            )
        if step_id:
            result_step_ids.add(step_id)

    if not require_all_steps:
        return

    missing_step_ids = valid_step_ids - result_step_ids
    if missing_step_ids:
        raise ValueError(
            f"{source_desc}: result is missing an update for step id(s) {sorted(missing_step_ids)} "
            f"on work order {order.get('id')!r} — every ticketplan step must appear in 'steps' with "
            "a status (completed/blocked/failed/skipped), even one that was only skipped or blocked"
        )


def extract_json_result(text: str) -> dict | None:
    """Best-effort: scan backward for the last balanced top-level {...}
    block whose parsed content looks like a result JSON. Deliberately
    conservative — a missed detection just falls back to "save it
    yourself" (always safe); a wrong auto-import would not be. Shared by
    run_work_order.py's generic `--runner-command` path and any adapter
    whose runtime returns the result JSON embedded in a larger text blob
    (e.g. claude_code's `--output-format json` wrapper's `result` field)."""
    search_end = len(text)
    while True:
        end = text.rfind("}", 0, search_end)
        if end == -1:
            return None
        depth = 0
        start = None
        for i in range(end, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                depth -= 1
                if depth == 0:
                    start = i
                    break
        if start is not None:
            candidate = text[start:end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and "workOrderId" in parsed and "finalStatus" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass
        search_end = end


@dataclass
class AdapterInfo:
    name: str
    capabilities: list[str]
    safety_level: str  # "manual" | "supervised" | "sandboxed"
    supports_live_events: bool
    supports_auto_execute: AutoExecuteCapability
    # Does this adapter's execute() spend real money (LLM API usage) when
    # it runs? True for anything that calls a paid model API on its own
    # initiative (claude_code, codex, openclaw — all "consume credits"
    # conceptually, whether implemented yet or not). False for
    # manual_prompt, which only ever writes local files — the human is the
    # one who later spends money by pasting the prompt into their own paid
    # session, not this adapter. run_work_order.py's budget gate
    # (--max-budget-usd / COMMANDPILOT_CLAUDE_MAX_BUDGET_USD) is required
    # before calling execute() on any adapter with this set to True — see
    # docs/background-dev-team-runbook.md and
    # docs/runner-adapter-contract.md.
    consumes_paid_credits: bool = False
    command_template: str | None = None
    # Can this adapter's execute_step() run ONE ticketplan step per call
    # (see build_step_prompt())? False for every adapter until it actually
    # implements execute_step() — the base class's default raises
    # NotImplementedError, same pattern as supports_auto_execute vs.
    # execute(). run_work_order.py's --per-step flag refuses to start
    # unless this is True, rather than silently falling back to the
    # whole-order path.
    supports_step_execution: bool = False


@dataclass
class ExecuteOutcome:
    exit_code: int
    output_log_path: Path
    result: dict | None  # auto-detected/produced result JSON, if any
    # Actual spend for this one execute() call, if the adapter's runtime
    # reports it (claude_code's --output-format json wrapper has
    # total_cost_usd). None means "unknown" — CP-OP02's bounded-retry loop
    # in run_work_order.py treats an unknown cost conservatively (assumes
    # the whole remaining budget for that attempt) rather than assuming 0,
    # so a cumulative budget ceiling across retries can never be exceeded
    # even for an adapter that doesn't report cost.
    cost_usd: float | None = None
    # True iff this outcome exists because progress.should_stop() returned
    # True mid-run (user hit Stop) rather than a natural failure/timeout/
    # crash. run_work_order.py uses this to write a "Vom Nutzer
    # unterbrochen" blocked_reason instead of a generic failure message.
    interrupted: bool = False


@dataclass
class StepExecuteOutcome:
    """Sibling of ExecuteOutcome for execute_step() — same shape, except
    `step_result` holds the single-step result dict (validated by
    parse_and_validate_step_result()) instead of a whole-order `result`.
    Kept as a separate dataclass rather than reusing ExecuteOutcome with a
    differently-typed field so a caller can never accidentally treat a
    per-step outcome as a whole-order one (or vice versa) — the type
    itself is the guard, not a runtime check."""
    exit_code: int
    output_log_path: Path
    step_result: dict | None
    cost_usd: float | None = None
    interrupted: bool = False


@dataclass
class ProgressReporter:
    """Optional live-progress/interrupt channel passed into execute().

    run_work_order.py (the harness) owns real CommandPilot credentials and
    implements both callables against the existing activity-log/work-order
    endpoints; an adapter never talks to those endpoints directly. Both
    calls are safe to make often — the harness is responsible for its own
    rate-limiting (e.g. the existing ~15s tick), not the adapter.

    An adapter that ignores this entirely (or is called without one, e.g.
    from a test) behaves exactly as before: no live progress, no interrupt
    support.
    """

    # Post a short human-readable status line (e.g. "Schritt 2/5: Tests
    # laufen") as an activity-log entry visible in the live UI.
    report_progress: Callable[[str], None]
    # True once the user has requested a stop (running -> cancelled). An
    # adapter with a long-running subprocess should poll this on the same
    # cadence as report_progress and kill the subprocess if it flips True.
    should_stop: Callable[[], bool]


class RunnerAdapter(ABC):
    """Every adapter (manual_prompt, claude_code, codex, openclaw, ...)
    extends this. run_work_order.py only ever talks to this interface —
    it never knows which concrete runtime it's driving.

    Safety, non-negotiable per adapter (see docs/runner-adapter-contract.md):
    1. Declare `info.capabilities` honestly — what this adapter needs to do
       its job. Used by check_scope_errors() to catch an adapter that
       needs something the work order's scope blocks outright.
    2. check_scope_errors()/check_scope_warnings() run before prepare() or
       execute() touch anything. A non-empty check_scope_errors() must
       abort the run — never proceed "anyway."
    3. Never assume permissions beyond what's declared. An adapter that
       later needs a new capability must add it to `info.capabilities`,
       not silently do the thing.
    """

    info: AdapterInfo

    def check_scope_errors(self, order: dict) -> list[str]:
        """Hard, blocking. Default: this adapter's own declared
        capabilities/command_template must not reference a blocked
        action — independent of (in addition to) the harness's own
        work-order-level validate_preconditions() check on the scope
        itself. Subclasses may add checks; they must not remove this one."""
        errors: list[str] = []
        texts = list(self.info.capabilities)
        if self.info.command_template:
            texts.append(self.info.command_template)
        for text in texts:
            hit = find_blocked_keyword(text)
            if hit:
                errors.append(
                    f"Adapter '{self.info.name}' deklariert '{text}', was auf die blockierte "
                    f"Aktion '{hit}' passt — dieser Adapter darf für dieses Work Order nicht laufen."
                )
        return errors

    def check_scope_warnings(self, order: dict) -> list[str]:
        """Non-blocking. Default: warn if an auto-executing adapter's
        capability isn't mentioned anywhere in the scope's
        allowed/requires_approval text — ambiguous, not necessarily wrong."""
        warnings: list[str] = []
        if self.info.supports_auto_execute in ("yes", "semi_auto"):
            scope = order.get("approval_scope") or {}
            allowed_text = " ".join(
                list(scope.get("allowed_actions", [])) + list(scope.get("requires_approval", []))
            ).lower()
            hint_words = ("ausführen", "ausfuehren", "execute", "run", "code ändern", "code aendern")
            if not any(w in allowed_text for w in hint_words):
                warnings.append(
                    f"Adapter '{self.info.name}' kann automatisch ausführen, aber der Approval Scope "
                    "erwähnt Ausführung/Code-Änderung nirgends — bitte prüfen, ob das gewollt ist."
                )
        return warnings

    @abstractmethod
    def prepare(self, order: dict, session_path: Path) -> Path:
        """Write whatever this adapter needs into session_path (prompt,
        schema, example, ...). Returns the path to the primary artifact
        (e.g. prompt.md) for the caller to point a human/tool at."""

    def execute(
        self,
        order: dict,
        session_path: Path,
        runner_command: str | None,
        max_budget_usd: float | None = None,
        progress: ProgressReporter | None = None,
    ) -> ExecuteOutcome:
        """Adapter-native execution — only meaningful if
        info.supports_auto_execute. Base implementation refuses; adapters
        that support it must override. Not to be confused with
        run_work_order.py's own generic `--runner-command` path, which
        works with any adapter and doesn't go through this method.

        `max_budget_usd`: for any adapter with `info.consumes_paid_credits`,
        run_work_order.py's budget gate has already required an explicit
        `--max-budget-usd`/`COMMANDPILOT_CLAUDE_MAX_BUDGET_USD` value before
        calling this — that value is passed here and should be honored as
        (or combined with, whichever is more restrictive) any per-work-order
        `approval_scope.max_cost_usd`. An adapter that ignores this
        parameter while spending real money is not meeting the contract.

        `progress`: optional live-progress/interrupt channel, see
        ProgressReporter. Only adapters with `info.supports_live_events`
        True are expected to actually call it; others may ignore it."""
        raise NotImplementedError(
            f"Adapter '{self.info.name}' does not support native --mode execute "
            f"(supports_auto_execute={self.info.supports_auto_execute!r})."
        )

    def execute_step(
        self,
        order: dict,
        step: dict,
        prior_steps: list[dict],
        session_path: Path,
        max_budget_usd: float | None = None,
        progress: ProgressReporter | None = None,
    ) -> StepExecuteOutcome:
        """Adapter-native execution of a SINGLE ticketplan step — only
        meaningful if info.supports_step_execution. Base implementation
        refuses; adapters that support it must override. Sibling of
        execute() at step granularity: run_work_order.py's --per-step path
        (_run_step_by_step()) calls this once per step, in order, passing
        each already-completed step's result forward as `prior_steps` —
        see build_step_prompt() for exactly what context that carries.

        `max_budget_usd`/`progress`: same contract as execute() — the
        harness has already enforced the budget gate before this is ever
        called, and `progress` is the same ProgressReporter (report/stop),
        just checked once per step invocation instead of once per whole
        order."""
        raise NotImplementedError(
            f"Adapter '{self.info.name}' does not support --per-step execution "
            f"(supports_step_execution={self.info.supports_step_execution!r})."
        )

    @abstractmethod
    def collect_result(self, session_path: Path, result_file: str | None) -> dict:
        """Return the result JSON dict, ready for import_result(). Raise
        FileNotFoundError (or similar) with a clear message if nothing is
        available yet."""
