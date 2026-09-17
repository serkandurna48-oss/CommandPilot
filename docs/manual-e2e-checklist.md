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

## Golden Path

AC1–AC12 oben **sind** der Golden Path (Create → Approve → Queue → Run →
Import → Accept). Ab hier: die zusätzlichen Pfade, die CP-OP01–03
eingeführt haben (Human-Resume-Kanten, Cancel, Auto-Retry, idempotenter
Import) — Herkunft: CP-OP04. Placeholder-Konvention wie im Runbook:
`YOUR_WORK_ORDER_ID` ohne spitze Klammern (ein bares `<...>` wird von
PowerShell als Input-Redirection geparst und ist ein harter Parse-Fehler).

### AC13 — needs_approval → queued (Requeue)

22. Eine Work Order in Status `needs_approval` bringen (z.B. per direktem
    API-Call, da kein UI-Pfad dorthin führt, wenn kein echter Runner das
    auslöst):
    ```powershell
    curl -X PATCH http://localhost:8000/api/work-orders/YOUR_WORK_ORDER_ID `
      -H "Authorization: Bearer $env:COMMANDPILOT_API_TOKEN" -H "Content-Type: application/json" `
      -d '{"status":"needs_approval","source":"harness","reason":"manual test setup"}'
    ```
23. Work-Order-Seite neu laden. Erwartet: Lifecycle Controls zeigen
    **Requeue** und **Cancel**, kein **Accept**/**Request Rework**.
24. Auf **Requeue** klicken. Erwartet: Status wechselt zu `queued`; im
    Activity Log ein neuer Eintrag `status_transition`
    (`needs_approval → queued`, `actor: human`, `source: ui`).

### AC14 — blocked → queued (Requeue)

25. Wie AC13, aber Zielstatus `blocked` statt `needs_approval`. Gleiches
    erwartetes UI-Verhalten (Requeue + Cancel sichtbar, Requeue führt zu
    `queued`).

### AC15 — failed → queued (Requeue)

26. Wie AC13, aber Zielstatus `failed`. Gleiches erwartetes Verhalten.
    Zusätzlich: falls die Work Order zuvor durch Retry-Erschöpfung (AC18
    unten) auf `failed` gelandet ist, prüfen, dass der **Failed-Banner**
    (roter Kasten oberhalb der Lifecycle Controls) nach dem Requeue
    verschwindet.

### AC16 — rework_requested → queued (Requeue)

27. Eine Work Order über den Golden Path bis `review_ready` bringen, dann
    **Request Rework** klicken statt Accept. Erwartet: Status wechselt zu
    `rework_requested`, Lifecycle Controls zeigen **Requeue** und
    **Cancel**.
28. Auf **Requeue** klicken. Erwartet: Status wechselt zu `queued`.

### AC17 — Cancel aus jedem erlaubten Zustand (inkl. Confirm-Dialog)

29. Für jeden nicht-terminalen Status (`draft`, `approved`, `queued`,
    `running`, `needs_approval`, `blocked`, `failed`, `review_ready`,
    `rework_requested`): **Cancel** klicken.
30. Erwartet: ein Inline-Bestätigungskasten erscheint (kein Klick löst
    sofort etwas aus) mit **"Yes, cancel"**/**"No, keep it"**.
31. Auf **"No, keep it"** klicken. Erwartet: Bestätigungskasten
    verschwindet, Status unverändert.
32. **Cancel** erneut klicken, dann **"Yes, cancel"**. Erwartet: Status
    wechselt zu `cancelled`, Lifecycle Controls zeigen danach keine
    Buttons mehr (terminal).
33. Aus `accepted` und `cancelled` selbst: erwartet **kein** Cancel-Button
    (beide sind terminal, keine ausgehenden Kanten).

### AC18 — Technischer Fehler → Auto-Retry

34. Eine Work Order bis `running` bringen (AC1–AC3), dann einen
    technischen Fehler erzwingen — am einfachsten, indem `claude` temporär
    vom PATH entfernt wird (der Adapter löst dann zuverlässig
    `FileNotFoundError` in `_resolve_claude_executable()` aus) oder ein
    absichtlich zu niedriges `--max-budget-usd` (z.B. `0.001`) gesetzt
    wird, sodass die CLI selbst sofort abbricht:
    ```powershell
    python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode execute --adapter claude_code --max-budget-usd 0.001 --token $env:COMMANDPILOT_API_TOKEN
    ```
35. Erwartet im Terminal-Output: `Attempt 1/3 — starte adapter.execute()`,
    dann bei technischem Fehler `Attempt 2/3` (sofern der Working Tree
    zwischen den Versuchen unverändert war).
36. Erwartet in der UI nach Neuladen: **Agent Runs**-Abschnitt zeigt
    mindestens zwei Einträge für dieselbe Work Order — der zweite mit
    sichtbarem `Attempt 2`-Label, eingerückt/mit Retry-Icon markiert, und
    dem Text "Auto-retry — technical failure in attempt 1".
37. Work Order bleibt währenddessen auf Status `running` (kein
    Zwischenstatus für den Retry selbst).

### AC19 — Technischer Fehler + Dirty Worktree → kein Retry

38. Wie AC18, aber vor dem erneuten Start absichtlich eine unversionierte
    Datei im Repo anlegen (`echo test > dirty-test.txt`) — simuliert einen
    Attempt, der bereits Dateien verändert hat, bevor er technisch
    fehlschlägt.
39. Erwartet: nur **ein** Attempt wird gestartet, kein Retry. Terminal
    zeigt `... UND der Working Tree hat sich seitdem verändert ...
    kein Auto-Retry, menschliches Eingreifen nötig`.
40. Erwartet in der UI: Status `failed`, **Failed-Banner** mit dem Text zu
    `technical_failure_with_worktree_changes`.
41. Aufräumen: `dirty-test.txt` wieder löschen.

### AC20 — Retry-Erschöpfung → failed

42. Wie AC18, aber den technischen Fehler bei allen 3 Versuchen erzwingen
    (z.B. `claude` für die Dauer des gesamten Tests vom PATH entfernt
    lassen).
43. Erwartet: nach Attempt 3 kein weiterer Versuch. Terminal zeigt
    `Technischer Fehler, 3/3 Versuche ausgeschöpft`.
44. Erwartet in der UI: Status `failed`, **Failed-Banner** mit dem Text zu
    `technical_failure_retries_exhausted`. **Agent Runs**-Abschnitt zeigt
    3 Einträge (Attempt 1, 2, 3), alle mit Status `failed`.

### AC21 — Cancel zwischen Attempts

45. Wie AC18 (technischer Fehler bei Attempt 1), aber unmittelbar nach dem
    ersten Fehlschlag — bevor Attempt 2 startet — die Work Order in einem
    zweiten Terminal/Browser-Tab auf `cancelled` setzen (Cancel-Button
    oder direkter API-Call).
46. Erwartet: kein Attempt 2 wird gestartet. Terminal zeigt `Work Order
    wurde cancelled — kein weiterer Retry`.
47. Erwartet in der UI: Status `cancelled`; der zuletzt offene `agent_run`
    aus Attempt 1 zeigt Status `failed` (nicht `running` hängengeblieben).

### AC22 — Doppelter Result-Import

48. Golden Path bis AC5 (result.json importiert, Status `review_ready`)
    durchführen.
49. Denselben Import-Befehl mit derselben `result.json` erneut ausführen:
    ```powershell
    python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode import-result --api-url http://localhost:8000 --token $env:COMMANDPILOT_API_TOKEN
    ```
50. Erwartet: Befehl läuft erfolgreich durch (`N succeeded, 0 failed`),
    Status bleibt `review_ready` (Same-State-Transition ist ein No-op,
    kein zusätzlicher `status_transition`-Audit-Eintrag).
51. Erwartet in der UI: **Activity Log** und **Artifacts** zeigen exakt
    dieselbe Anzahl Einträge wie nach dem ersten Import — keine
    Duplikate.

### AC23 — Partieller Import + Recovery

52. Eine Work Order bis `running` bringen, ein gültiges `result.json` mit
    mindestens 2 Artifacts vorbereiten.
53. Backend kurz stoppen (oder Netzwerk kappen), Import starten, Backend
    nach dem ersten Artifact-POST wieder verfügbar machen — oder
    einfacher: einen ungültigen `work_order_id`-Pfad für einen der Aufrufe
    simulieren, sodass mindestens ein Artifact-POST fehlschlägt, während
    der Rest durchläuft. Ziel: ein Import, bei dem einige, aber nicht alle
    Items erfolgreich geschrieben wurden.
54. Erwartet: `finalStatus=review_ready` wird **nicht** gesetzt (Atomic
    Gate greift), Terminal zeigt `refusing to set finalStatus='review_ready'`.
55. Denselben Import-Befehl mit derselben `result.json` erneut ausführen,
    diesmal ohne den künstlichen Fehler.
56. Erwartet: alle zuvor fehlgeschlagenen Items werden jetzt geschrieben,
    bereits erfolgreich importierte Items werden nicht dupliziert (gleiche
    `dedup_key`-Werte wie beim ersten Versuch), `finalStatus=review_ready`
    wird jetzt gesetzt.

## Bei einem Fehlschlag

Für jeden fehlgeschlagenen Schritt bitte notieren: Schritt-Nummer, was erwartet wurde, was tatsächlich
passiert ist, Browser-Konsole/Netzwerk-Tab-Fehler falls vorhanden, und `run.log` aus dem jeweiligen
`tmp/work-order-runs/<id>/`-Ordner (keine Tokens/Secrets daraus teilen).
