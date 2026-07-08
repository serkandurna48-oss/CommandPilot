import type { WorkOrder, ApprovalScope, WorkOrderStep } from "@/types";
import { AUTONOMOUS_ALLOWED, NEEDS_APPROVAL, BLOCKED_ALWAYS } from "@/lib/safetyRules";
import { isExternalRepoWorkOrder } from "@/lib/workOrderMapper";

const AGENT_ROLES = [
  "Product Agent — Ziel, Nutzerflow, Akzeptanzkriterien prüfen/verfeinern.",
  "Architect Agent — technische Umsetzung, Risiken, Architekturentscheidungen.",
  "Coder Agent — Codeänderungen innerhalb des Approval Scope.",
  "QA Agent — Tests / Lint / Typecheck ausführen.",
  "Reviewer Agent — Bugs, Security, Edge Cases, Scope-Verletzungen.",
  "Reporter Agent — Review Package + Ergebnis-JSON erstellen.",
];

// The machine-readable result block the runner must emit at the end of the
// session. camelCase to match the frontend domain model directly — the
// import bridge (scripts/import_work_order_result.py) is what converts this
// into the backend's snake_case API calls, mirroring how
// frontend/lib/workOrderMapper.ts does the same conversion on read.
const RESULT_JSON_SCHEMA = `{
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
}`;

/**
 * Builds a complete, self-contained runner prompt for Claude Code / Codex
 * from a WorkOrder + its ApprovalScope + its Ticketplan (steps). Meant to be
 * pasted directly into a fresh agent session — it carries its own scope,
 * step plan, and safety rules rather than assuming the runner has any prior
 * context, and it ends by demanding a machine-readable result block that
 * scripts/import_work_order_result.py can feed straight back into
 * CommandPilot.
 */
export function generateRunnerPrompt(order: WorkOrder, scope: ApprovalScope, steps: WorkOrderStep[]): string {
  const lines: string[] = [];

  lines.push(`# Work Order: ${order.title}`);
  lines.push("");
  lines.push("Du bist ein autonomer Coding-Agent (Judge + Executor-Team) mit einem klar begrenzten Arbeitsauftrag.");
  lines.push("Halte dich strikt an den Approval Scope unten. Bei Unklarheit im erlaubten Rahmen: selbst entscheiden und dokumentieren, nicht nachfragen.");
  lines.push("Arbeite den Ticketplan unten Schritt für Schritt ab, in der angegebenen Reihenfolge. Nicht mehrere Steps parallel bearbeiten.");
  lines.push("");

  lines.push("## Work Order Kontext");
  lines.push(`workOrderId: ${order.id}`);
  lines.push(`Ziel: ${order.goal}`);
  lines.push(`Repo: ${order.repo}`);

  // Control-Plane/Target-Repo split (OP-Runner-RepoPath-001). targetRepoPath
  // is display/prompt text only — never used here or anywhere else to cd
  // into, read from, or execute anything at that path.
  if (isExternalRepoWorkOrder(order)) {
    lines.push(`Control Plane Repo: CommandPilot (hier läuft scripts/run_work_order.py, hier läuft auch der Result-Import)`);
    lines.push(
      `Target Repo: ${order.targetRepoName ?? order.repo}` +
        (order.targetRepoPath ? ` (Pfad-Hinweis, rein informativ: ${order.targetRepoPath})` : "")
    );
    lines.push("");
    lines.push("WICHTIG — Cross-Repo-Kontext, unbedingt beachten:");
    lines.push("- You are working in the target repository.");
    lines.push("- Do not expect CommandPilot scripts to exist here.");
    lines.push("- Do not write result.json inside the target repo unless explicitly instructed.");
    lines.push("- Return normal analysis/report, or write the result only to the CommandPilot tmp path if that path is accessible from here.");
  } else {
    lines.push("Control Plane Repo: CommandPilot (kein separates Target Repo — Control Plane und Execution Context sind dasselbe Repo)");
  }

  if (scope.allowedPaths?.length) lines.push(`Erlaubte Pfade: ${scope.allowedPaths.join(", ")}`);
  if (scope.blockedPaths?.length) lines.push(`Gesperrte Pfade (niemals anfassen): ${scope.blockedPaths.join(", ")}`);
  lines.push(`Zeitlimit: ${order.timeLimitMinutes} Minuten (Approval Scope: max. ${scope.maxRuntimeMinutes} Minuten${scope.maxCostUsd ? `, max. $${scope.maxCostUsd}` : ""}). Überschritten → stoppen, finalStatus="blocked", aktuellen Stand ins Ergebnis-JSON.`);
  lines.push("");

  lines.push("## Akzeptanzkriterien (Work Order gesamt)");
  for (const c of order.acceptanceCriteria) lines.push(`- [ ] ${c}`);
  lines.push("");

  if (order.missingContext?.length) {
    lines.push("## Fehlender Kontext (bereits bekannt)");
    lines.push("Diese Punkte fehlen noch — falls nicht bereitgestellt, NICHT raten. finalStatus=\"blocked\", blockedReason auf dem betroffenen Step setzen:");
    for (const m of order.missingContext) {
      lines.push(`- ${m.label}${m.required ? " (erforderlich)" : " (optional)"}`);
    }
    lines.push("");
  }

  lines.push("## Ticketplan (in dieser Reihenfolge abarbeiten)");
  if (steps.length === 0) {
    lines.push("(Kein Ticketplan hinterlegt — arbeite direkt anhand der Akzeptanzkriterien oben und der Agentenrollen unten.)");
  } else {
    for (const s of steps) {
      lines.push(`### Step ${s.orderIndex + 1}: ${s.title}  \`id: ${s.id}\`  (Rolle: ${s.assignedRole})`);
      if (s.description) lines.push(s.description);
      if (s.acceptanceCriteria.length) {
        lines.push("Akzeptanzkriterien für diesen Step:");
        for (const c of s.acceptanceCriteria) lines.push(`- [ ] ${c}`);
      }
      lines.push("");
    }
  }

  lines.push("## Approval Scope (dieses Work Orders)");
  lines.push("");
  lines.push("**Autonom erlaubt (kein Nachfragen nötig):**");
  for (const a of scope.allowedActions) lines.push(`- ${a}`);
  lines.push("");
  lines.push("**Braucht Approval (stoppen, activityLogs-Eintrag mit level=\"approval_required\", betroffenen Step auf status=\"blocked\"):**");
  for (const a of scope.requiresApproval) lines.push(`- ${a}`);
  lines.push("");
  lines.push("**Blockiert (niemals ausführen, auch nicht mit Approval in dieser Session):**");
  for (const a of scope.blockedActions) lines.push(`- ${a}`);
  lines.push("");

  lines.push("## Agentenrollen (nacheinander durchlaufen, pro Ticketplan-Step)");
  for (const r of AGENT_ROLES) lines.push(`- ${r}`);
  lines.push("");

  lines.push("## Harte Safety-Regeln (gelten IMMER, unabhängig vom Approval Scope oben)");
  lines.push("");
  lines.push("Autonom erlaubt:");
  for (const a of AUTONOMOUS_ALLOWED) lines.push(`- ${a}`);
  lines.push("");
  lines.push("Braucht Approval:");
  for (const a of NEEDS_APPROVAL) lines.push(`- ${a}`);
  lines.push("");
  lines.push("Blockiert — niemals, unter keinen Umständen:");
  for (const a of BLOCKED_ALWAYS) lines.push(`- ${a}`);
  lines.push("");

  lines.push("## HARTER STOPP bei Scope-Verletzung");
  lines.push("Wenn eine Aktion nötig wird, die oben als \"Braucht Approval\" oder \"Blockiert\" gelistet ist:");
  lines.push("1. SOFORT stoppen. Keinen weiteren Code ändern, keine weitere Aktion ausführen.");
  lines.push("2. Den aktuellen Step auf status=\"blocked\" setzen, blockedReason mit der konkreten Aktion füllen, die den Stopp ausgelöst hat.");
  lines.push("3. Einen activityLogs-Eintrag mit level=\"approval_required\" hinzufügen, der die Aktion und den Grund benennt.");
  lines.push("4. Im finalen Ergebnis-JSON finalStatus=\"blocked\" setzen — niemals \"review_ready\" vortäuschen, um weiterzukommen.");
  lines.push("Ein blockierter Step ist ein gutes, erwartetes Ergebnis — kein Fehler, den es zu vermeiden gilt.");
  lines.push("");

  lines.push("## Reporting-Anforderung");
  lines.push("- Jede Aktion (auch Zwischenschritte) als activityLogs-Eintrag.");
  lines.push("- Jeder abgeschlossene, blockierte oder fehlgeschlagene Ticketplan-Step erscheint im steps-Array des Ergebnis-JSON — mit seiner exakten id von oben.");
  lines.push("- Am Ende IMMER das komplette Ergebnis-JSON ausgeben — auch bei \"blocked\" oder \"failed\".");
  lines.push("- Keine Secrets lesen, ausgeben oder ins Log schreiben — auch nicht auszugsweise oder maskiert.");
  lines.push("");

  lines.push("## Ergebnis-JSON (Pflicht als letzte Ausgabe der Session)");
  lines.push("Dieses JSON wird 1:1 in `python scripts/import_work_order_result.py` eingelesen — Feldnamen exakt einhalten:");
  lines.push("```json");
  lines.push(RESULT_JSON_SCHEMA);
  lines.push("```");
  lines.push("");
  lines.push(`reviewPackage.recommendedNextStep sollte konkret sein, z.B.: "${order.recommendedNextStep ?? "nächster sinnvoller Schritt für Serkan"}"`);

  return lines.join("\n");
}
