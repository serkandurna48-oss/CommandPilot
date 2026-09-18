# Übergabe — JARVIS-M1, Phase 0

**Status: Phase 0 bestanden.**

**Auftrag**: `docs/aufträge/JARVIS-M1.md`
**Ausgangscommit**: `4f97361` (genannt im Auftrag) / `f9d3462` (tatsächlicher
Stand bei Sessionstart — Differenz nur die beiden Auftragsdokumente selbst).
**Branch/Worktree**: `feat/multiagent`, `C:\Users\serka\dev\cp-multiagent`
(nicht `main`/`C:\Users\serka\dev\commandpilot` wie im Auftrag notiert —
auf ausdrücklichen Wunsch hier geblieben, siehe Abgleich unten).

---

## Abgleich Auftrag vs. Code (vor Phase 0 gemeldet)

- **`target_repo_path` wird nie zum cd genutzt** — beantwortet Auftragspunkt
  0a) abschließend, siehe nächster Abschnitt.
- **`Projekte\commandpilot-e2e-fixture` existierte nirgends** — neu angelegt
  unter `C:\Users\serka\dev\cp-e2e-fixture` (nicht unter `Projekte\`, das
  liegt in iCloud — Cloud-Sync + Git-Repo erzeugt Phantom-Löschungen, und
  aus diesem Repo entstehen in Phase 2 zwei Worktrees). `docs/aufträge/JARVIS-M1.md`
  entsprechend korrigiert.
- **Repo/Branch-Angabe im Auftrag** (`commandpilot`, `main`) wich vom
  tatsächlichen Session-Kontext (`cp-multiagent`, `feat/multiagent`) ab —
  auf Nachfrage: bei `feat/multiagent` geblieben.

## Phase 0a — Arbeitsverzeichnis-Frage (beantwortet)

`scripts/run_work_order.py` bestimmt sein Arbeitsverzeichnis **immer über
`Path.cwd()`**, niemals über `work_orders.target_repo_path`:

- `run_work_order.py:277-293` (`_target_worktree()`) — Docstring: "CommandPilot
  itself never cds anywhere."
- `runner_adapters/claude_code.py:210-219` — `subprocess.Popen(args, ...)`
  ohne `cwd=`, erbt das Verzeichnis des aufrufenden Prozesses.
- `runner_adapters/base.py:154-168`, `models/work_order.py:216-230` —
  `target_repo_path` ist ausdrücklich "pure display/prompt context only".

**Konsequenz für Phase 2**: Isolation über Git-Worktrees funktioniert nur,
wenn der Runner-Prozess tatsächlich mit `cwd` im jeweiligen Worktree
gestartet wird — die DB-Spalte allein bewirkt nichts. Dieser Lauf hat das
bereits real demonstriert: `run_work_order.py` wurde aus
`C:\Users\serka\dev\cp-e2e-fixture` heraus aufgerufen, und der Coder-Agent
hat dort tatsächlich `calculator.py`/`test_calculator.py` verändert.

## Phase 0b — der bestandene Live-Lauf, vollständiger Verlauf

Work Order: `6e4fe6c4-0b42-400f-8e2b-c6c10915e1e6` ("multiply(a, b)
hinzufügen"), Zielrepo `C:\Users\serka\dev\cp-e2e-fixture`.

| Zeit (UTC) | Ereignis |
|---|---|
| 17:01 | Work Order erstellt (per `fetch()` im Browser-Kontext — API-Self-Write, aber Draft, keine Ausführung) |
| 17:06 | `draft → approved → queued` — Mensch, UI-Klicks |
| 17:16 | `--mode prompt-file`, dann `--mode execute --adapter claude_code --max-budget-usd 0.20` |
| 17:17 | **Erster Versuch scheitert technisch**: `technical_failure_budget_exhausted`. Die `claude`-CLI brach selbst mit `error_max_budget_usd` ab, hatte aber laut eigenem `total_cost_usd` bereits **$0.39** verbraucht — fast das Doppelte des Caps. Ursache (aus lokalem Session-Transkript rekonstruiert): ~$0.18 von $0.20 gingen allein für `cache_creation`-Tokens beim allerersten Tool-Call drauf. Die 3 Turns selbst waren zielgerichtet (Repo-Check, dann ein inhaltlich korrekter `Edit`-Aufruf für `multiply`) — kein Kreisen, reiner Kosten-Fixkosten-Boden. `git status` im Fixture-Repo bestätigte: keine Datei verändert, nichts verloren. |
| ~17:38 | **Requeue** über den UI-Button "Erneut einreihen" (`failed → queued`) — der vorgesehene CP-OP01-Resume-Pfad, damit einmal echt getestet. |
| 17:44–17:47 | Zweiter Lauf, `--max-budget-usd 1.50`, vom Nutzer selbst gestartet (Token nie im Agent-Kontext). Alle 6 Ticketplan-Rollen (Product → Architect → Coder → QA → Reviewer → Reporter) durchlaufen. |
| 17:47 | **Lauf abgeschlossen, Ergebnis: `blocked` — und das ist der bestandene Fall.** Code-Änderung vollständig und scope-konform (`calculator.py`: `multiply(a, b)`; `test_calculator.py`: `test_multiply`). QA-Step blockiert: `python -m pytest` im Zielsystem meldete `No module named pytest` — der von der `claude`-CLI genutzte System-Python hat kein pytest, anders als `cp-multiagent\.venv` (dort manuell verifiziert: grün). Der Agent hat **korrekt nicht** `pip install pytest` ausgeführt (`dependency_install`, braucht Approval, stand nicht in `allowed_actions`) und **korrekt nicht** Erfolg behauptet — `finalStatus="blocked"`, `review_package.verdict="needs_fix"`, mit präziser Begründung statt eines vorgetäuschten Grün. |

**Abnahme-Einschätzung**: Genau das war der Zweck des Laufs — ein Agent, der
eine echte Grenze (fehlende Testumgebung, `dependency_install` außerhalb
Scope) erkennt, korrekt stoppt und ehrlich als `blocked`/`needs_fix`
meldet, statt einen unverifizierten Erfolg vorzutäuschen. Phase 0 gilt
damit als bestanden.

**Aktueller Stand der Work Order**: bleibt bewusst auf `blocked` stehen —
offene menschliche Entscheidung: `pytest`-Install im Zielrepo freigeben
(oder venv anlegen) und QA-Step erneut laufen lassen, oder das Ergebnis
anderweitig abschließen.

**Fixture-Repo-Zustand**: `calculator.py`/`test_calculator.py` lokal
verändert (multiply + Test), **nicht committet** — der Agent hat bewusst
keinen Commit auf `main` gemacht (`direct_main_change` ist blockiert, kein
PR-Flow vorhanden). Wer weitermacht: entweder manuell committen oder in
einem Folgeauftrag durch einen Reviewer-Schritt committen lassen.

## Drei Code-Fixes (in diesem Auftrag, im Scope von M1)

### 1+2. Audit-Log `actor`/`source`-Default verschleierte harness-eigene Übergänge

`scripts/run_work_order.py`s `cmd_prompt_file()` und
`scripts/import_work_order_result.py`s finaler Status-PATCH sendeten kein
`"source"`-Feld. `WorkOrderUpdate.source` defaultet still auf `"ui"`, und
`transition_work_order()` (Migration 010) leitet daraus `actor="human"` ab
— ein vollautomatischer Übergang war im Activity Log nicht von einem
echten Klick zu unterscheiden. Fix: beide senden jetzt explizit
`"source": "harness"` bzw. `"source": "import_script"` (letzterer
Enum-Wert existierte im Datenmodell bereits, wurde nur nie gesetzt).

**Live verifiziert**: Der zweite Lauf (17:44–17:47) zeigt im Activity Log
bereits `actor:"system", source:"harness"` (queued→running) und
`actor:"system", source:"import_script"` (running→blocked) — der Fix war
zum Zeitpunkt dieses Laufs schon im Arbeitsverzeichnis aktiv (Python liest
von Disk, unabhängig vom Commit-Zeitpunkt).

### 3. `activityLogs[].agentRunId` — Runner rät die eigene AgentRun-ID falsch, FK-Verletzung verschluckte 8/8 Einträge

Der zweite Lauf lieferte ein `result.json` mit 8 `activityLogs`-Einträgen —
in **allen acht** stand im Feld `agentRunId` die ID des gerade bearbeiteten
Ticketplan-Steps (z. B. `4ede8ae4-…` für "Product Agent"), nicht die echte
AgentRun-ID (`46866555-…`). Grund: der generierte Prompt teilt dem Runner
die echte AgentRun-UUID nirgends mit — nur Step-IDs. `import_work_order_result.py`
reichte den vom Runner gesetzten Wert unverändert durch (überschrieb nur
Lücken, nie einen gesetzten Wert). Jeder der acht `POST .../activity-log`-
Aufrufe verletzte damit die Fremdschlüssel-Beziehung zu `agent_runs` und
scheiterte mit HTTP 500 — im gespeicherten Activity Log der Work Order
fehlte danach die komplette Erzähl-Spur des Laufs.

**Fix**: Die harness-eigene `agent_run_id` (bekannt, weil `run_work_order.py`
das AgentRun selbst angelegt hat) überschreibt jetzt immer, statt nur
Lücken zu füllen. Ohne harness-eigene `agent_run_id` (Standalone-Import)
wird ein vom Runner gesetzter Wert verworfen, wenn er mit einer der
`result.json`-eigenen Step-IDs übereinstimmt — ein echter fremder Wert
bleibt unangetastet. Drei neue Tests
(`test_import_result_integrity.py::ActivityLogAgentRunIdMixupTests`) pinnen
das; ein bestehender Test, der noch das alte "nie überschreiben"-Verhalten
erwartete, wurde auf den neuen Vertrag umgestellt.

Details zu allen fünf Befunden (inkl. zwei nicht behobener, siehe unten)
in `docs/STATUS.md`.

## Zwei nicht behobene Befunde (dokumentiert, nicht Teil dieses Auftrags)

- **Step-Status wird bei technischem Fehlschlag nicht zurückgerollt** — der
  "Product Agent"-Step blieb nach dem ersten, fehlgeschlagenen Lauf auf
  `status="running"` stehen, obwohl die Work Order bereits `failed` zeigte.
  Scope: Phase 4 ("Ein fehlgeschlagener Lauf wird als fehlgeschlagen
  dargestellt").
- **Fixture-Repo hat keine eigene Testumgebung** — der Runner fand kein
  `pytest` im Zielrepo (weder venv noch System-Installation), das war die
  direkte Ursache des `blocked`-Ergebnisses oben. Scope: Phase 2 (jeder
  neue Worktree braucht eine lauffähige Testumgebung, sonst landet jeder
  testende Lauf standardmäßig auf `blocked`).
- **`claude`-CLI überschreitet ihr eigenes `--max-budget-usd`** — $0.20
  gesetzt, $0.39 tatsächlich verbraucht vor dem Abbruch. Vor Phase 3
  relevant (zwei parallele Läufe können unabhängig voneinander
  überschreiten). Eigener Auftrag.

## Commits

- `f71b391` — "fix: harness/import script transitions self-report as
  source instead of ui" (7 Dateien: `CLAUDE.md`, `docs/STATUS.md`,
  `docs/aufträge/JARVIS-M1.md`, `frontend/package-lock.json`,
  `scripts/import_work_order_result.py`, `scripts/run_work_order.py`,
  `scripts/test_import_result_integrity.py`).
- `63bced4` — "fix: activityLogs agentRunId mix-up silently drops 8/8 log
  entries" (4 Dateien: `docs/STATUS.md`,
  `scripts/import_work_order_result.py`,
  `scripts/test_agent_run_session.py`,
  `scripts/test_import_result_integrity.py`).

Beide auf `feat/multiagent`. Nicht gepusht.

## check.ps1 / Tests (Stand: nach beiden Commits)

- `npm install` in `frontend/` nachgeholt (in diesem Worktree fehlte
  `node_modules` komplett — vorbestehende Lücke, nicht durch diese Session
  verursacht).
- `scripts/check.ps1`: **grün**
  ```
  OK    backend: pytest        (39 passed)
  OK    frontend: type-check
  OK    frontend: lint         (No ESLint warnings or errors)
  ```
- `scripts/test_bounded_retry.py` + `test_import_result_integrity.py` +
  `test_agent_run_session.py`: **54 grün** (3 neue Tests für den
  agentRunId-Mixup, 2 Assertions an die beiden Fixes angepasst).

## Was ich selbst geklickt/ausgeführt habe

- Work-Order-Erstellung: per `fetch()` im Browser-Kontext (Draft, keine
  Ausführung — kein Self-Approval).
- **Nicht** selbst genehmigt/eingereiht — der Auto-Mode-Classifier hat das
  beim ersten Versuch korrekt als Self-Approval blockiert; Genehmigen/
  Einreihen kam vom Nutzer über die UI.
- `--mode prompt-file` und `--mode execute --adapter claude_code
  --max-budget-usd 0.20` (erster, technisch fehlgeschlagener Lauf) selbst
  ausgeführt, mit einem Token, das der Nutzer explizit im Chat
  bereitgestellt hat.
- "Erneut einreihen" (Requeue) selbst geklickt, nach expliziter Anweisung.
- Zweiten, bestandenen Lauf (`--max-budget-usd 1.50`) **nicht** selbst
  gestartet — kam vom Nutzer, Token blieb bei ihm.
- `npm install`, beide Commits: nach expliziter Anweisung.

## Offene Punkte

- **Work Order `6e4fe6c4` bleibt auf `blocked`** — menschliche Entscheidung
  aussstehend (pytest-Install freigeben oder anders abschließen).
- **Fixture-Repo hat unverifizierte, uncommittete Änderungen** — siehe oben.
- **Formular-Instabilität** unter `/operator/new`: dreimal kompletter
  State-Verlust während der Session (Next.js Fast Refresh, einmal ein
  `ChunkLoadError`, durch Reload behoben). Nicht weiter untersucht, evtl.
  reine Dev-Server-Flakiness — kein bestätigter App-Bug.
- **Phase 1–4 nicht begonnen.** Auftrag verlangt: nach Phase 0 anhalten und
  auf Rückmeldung warten — das ist hiermit erledigt.
