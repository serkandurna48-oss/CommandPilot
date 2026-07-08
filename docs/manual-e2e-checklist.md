# Manueller End-to-End-Test: Work-Order-Lifecycle im Browser

Herkunft: OP-E2E-Loop-001. Diese Checkliste existiert, weil der Judge/Executor-Agent
in dieser Session weder ein Browser-Automatisierungs-Tool (Playwright o.ä. — nicht
installiert, Installation wäre `dependency_install` und braucht Approval) noch einen
gültigen API-Token zur Verfügung hatte. Beides ist bei Serkan lokal vorhanden, daher
ist dies der schnellste Weg, den kompletten Loop einmal echt zu verifizieren.

Jeder Schritt ist einem Akzeptanzkriterium aus OP-E2E-Loop-001 zugeordnet. Wenn ein
Schritt nicht wie beschrieben funktioniert, ist das ein echter Bug — bitte mit
Screenshot/Fehlermeldung festhalten.

## Voraussetzungen

- Backend läuft (`http://localhost:8000/docs` sollte erreichbar sein).
- Frontend läuft (`npm run dev` im `frontend/`-Ordner, `http://localhost:3000`).
- Gültiger Supabase-Session-Token (siehe `docs/background-dev-team-runbook.md` §1).

## Checkliste

### AC1 — Neue Work Order in UI erstellen
1. Im Browser einloggen, zu `/operator` navigieren.
2. "New Work Order" klicken, Formular ausfüllen (Titel, Ziel, mind. ein Ticketplan-Step,
   Approval Scope mit mindestens einem Eintrag in `blocked_actions`).
3. Erwartet: Work Order wird erstellt, landet mit Status `draft` in der Liste.

### AC2 — Approve → Queued
4. Work Order öffnen, auf **Approve** klicken. Erwartet: Status wechselt zu `approved`.
5. Auf **Mark Queued** klicken. Erwartet: Status wechselt zu `queued`.

### AC3 — Runner prompt-file starten
6. Token setzen und Runner starten (Befehle stehen im LocalRunnerPanel der Work-Order-Seite,
   Schritt 1 und 3 dort):
   ```powershell
   $env:COMMANDPILOT_API_TOKEN = "<dein-token>"
   python scripts/run_work_order.py <WORK_ORDER_ID> --mode prompt-file --api-url http://localhost:8000 --token $env:COMMANDPILOT_API_TOKEN
   ```
7. Erwartet: Terminal zeigt `Work Order Status -> running`, `Step '...' -> running`,
   `AgentRun <uuid> angelegt (role=..., status=running)`, `ActivityLog-Eintrag 'runner_started' geschrieben`.
   Falls stattdessen `WARNUNG: AgentRun-Antwort enthielt keine 'id'` erscheint: echter Bug, bitte melden.

### AC4 — UI zeigt AgentRun / waiting for result
8. Browser-Seite der Work Order neu laden (oder auf `/operator/<id>` navigieren).
9. Erwartet im **LocalRunnerPanel**: Phase-Badge zeigt **"Wartet auf Ergebnis"** (blau/brand-farben),
   plus der **Current Run Folder** (`tmp/work-order-runs/<id>/`).
10. Erwartet im **Agent Runs**-Abschnitt: ein Eintrag mit Status `running`, Rolle des ersten Steps,
    `model` zeigt z.B. `manual_prompt (prompt-file)`, Startzeit ist gesetzt.

### AC5 — gültiges result.json importieren
11. `tmp/work-order-runs/<id>/prompt.md` in Claude Code/Codex einfügen und laufen lassen, ODER ein
    manuelles Test-`result.json` gemäß `tmp/work-order-runs/<id>/result.schema.json` erstellen (mit
    `finalStatus: "review_ready"`, mindestens einem `completed`-Step, gefülltem `reviewPackage`).
12. Importieren:
    ```powershell
    python scripts/run_work_order.py <WORK_ORDER_ID> --mode import-result --api-url http://localhost:8000 --token $env:COMMANDPILOT_API_TOKEN
    ```
13. Erwartet: `N succeeded, 0 failed`, `work order final status -> review_ready`, `agent run <uuid> -> completed`.

### AC6 — UI zeigt 100% Steps
14. Seite neu laden. Erwartet im **Execution Plan**-Abschnitt: Fortschrittsbalken zeigt 100%
    (vorausgesetzt alle Steps im result.json waren `completed`/`skipped`).

### AC7 — Activity Logs sichtbar
15. Erwartet im **Activity Log**-Abschnitt: Einträge aus dem Import sichtbar (Zeitstempel, Level, Message),
    inkl. des `runner_started`-Eintrags von Schritt 7.

### AC8 — Artifacts sichtbar
16. Erwartet im **Artifacts**-Abschnitt: alle im result.json übergebenen Artifacts sichtbar mit Typ/Titel/Inhalt.

### AC9 — Review Package sichtbar
17. Erwartet im **Review Package**-Abschnitt: Summary, Verdict-Badge, Files Changed, Tests Run,
    Risks, Open Questions, Recommended Next Step — alles aus dem result.json übernommen.

### AC10 — Status review_ready nur bei vollständigem Review Package
18. Gegentest (wichtig!): Versuche versehentlich/absichtlich, eine Work Order ohne Review Package
    auf `review_ready` zu setzen, z.B. per direktem API-Call:
    ```powershell
    curl -X PATCH http://localhost:8000/api/work-orders/<EINE_WORK_ORDER_OHNE_REVIEW_PACKAGE> `
      -H "Authorization: Bearer $env:COMMANDPILOT_API_TOKEN" -H "Content-Type: application/json" `
      -d '{"status":"review_ready"}'
    ```
19. Erwartet: HTTP 400 mit `"Cannot set status to review_ready: no review package exists for this work order yet."`
    (serverseitiger Guard, ergänzt in OP-E2E-Loop-001 — siehe `backend/app/routers/work_orders.py`).
    Der bisherige "Mark Review Ready"-Button in der UI wurde entfernt, da er genau diesen Fall
    unkontrolliert erlaubt hätte.

### AC11 — Accept klicken
20. Auf der Work-Order-Seite (jetzt Status `review_ready`) auf **Accept** klicken.

### AC12 — Danach Status accepted
21. Erwartet: Status-Badge wechselt zu `accepted`, Lifecycle-Buttons verschwinden
    (kein weiterer gültiger Übergang aus `accepted` definiert).

## Bei einem Fehlschlag

Für jeden fehlgeschlagenen Schritt bitte notieren: Schritt-Nummer, was erwartet wurde, was tatsächlich
passiert ist, Browser-Konsole/Netzwerk-Tab-Fehler falls vorhanden, und `run.log` aus dem jeweiligen
`tmp/work-order-runs/<id>/`-Ordner (keine Tokens/Secrets daraus teilen).
