# STATUS — laufende Befunde

> Sammelstelle für Befunde aus Live-Läufen, die nicht in CLAUDE.md gehören
> (dort steht der Soll-Zustand), aber zu wichtig sind, um nur im Chat-Verlauf
> zu verschwinden. Chronologisch, neueste zuerst.

---

## 2026-09-18 — JARVIS-M1 Phase 0: fünf Befunde aus den ersten beiden echten Runner-Läufen

Kontext: erster echter `scripts/run_work_order.py --mode execute --adapter
claude_code`-Lauf gegen ein neues Zielrepo (`C:\Users\serka\dev\cp-e2e-fixture`),
Work Order `6e4fe6c4-0b42-400f-8e2b-c6c10915e1e6`. Details siehe
`docs/aufträge/JARVIS-M1.md`.

### 1. Audit-Log `actor`/`source`-Default verschleiert harness-eigene Übergänge — behoben in M1

**Befund**: `scripts/run_work_order.py`s `cmd_prompt_file()` setzte den
`queued → running`-Übergang per `PATCH /api/work-orders/{id}` ohne
`"source"`-Feld. `WorkOrderUpdate.source` defaultet still auf `"ui"`, und
`transition_work_order()` (Migration 010) leitet daraus `actor="human"` ab
(`v_actor := case when p_source = 'ui' then 'human' else 'system' end`). Ein
komplett automatischer Harness-Start wurde damit im Activity Log als
menschlicher UI-Klick protokolliert — nicht zu unterscheiden von einem
tatsächlichen Klick auf "Als laufend markieren".

Derselbe Fehler steckte in `scripts/import_work_order_result.py`: der
finale `PATCH .../work-orders/{id}` mit `finalStatus` (review_ready/
blocked/failed) sendete ebenfalls kein `source`, obwohl das Datenmodell
(`WorkOrderTransitionSourceLiteral`) den Wert `"import_script"` exakt für
diesen Zweck bereits vorsah — nur nie gesetzt hat.

**Warum das zählt**: Ein Audit-Log, der Maschine als Mensch protokolliert,
untergräbt genau die Eigenschaft, für die CommandPilot gebaut ist
(nachvollziehbare Kontrolle über automatisierte Aktionen).

**Fix (dieser Auftrag, JARVIS-M1)**:
- `scripts/run_work_order.py::cmd_prompt_file()` — PATCH sendet jetzt
  `"source": "harness"`.
- `scripts/import_work_order_result.py` — finaler Status-PATCH sendet jetzt
  `"source": "import_script"`.
- `scripts/test_import_result_integrity.py` — Assertion angepasst
  (erwartete Payload enthält jetzt `source`).
- Verifiziert: `v_actor` in Migration 010 mappt beides auf `actor="system"`.
- Getestet: `scripts/test_bounded_retry.py` + `test_import_result_integrity.py`
  + `test_agent_run_session.py` (51 Tests) grün, `backend/tests` (39 Tests)
  grün nach dem Fix.

### 2. Step-Status wird bei technischem Fehlschlag nicht zurückgerollt — für Phase 4

**Befund**: Als die Work Order oben durch `technical_failure_budget_exhausted`
auf `failed` ging, blieb der erste Ticketplan-Step ("Product Agent") auf
`status="running"` stehen — sichtbar im UI als "Läuft", obwohl die
übergeordnete Work Order bereits "Fehlgeschlagen" zeigt. Kein Code-Pfad
setzt den zuletzt aktiven Step bei einem harness-seitigen technischen
Fehlschlag zurück (weder auf `failed` noch auf `pending`).

**Warum das zählt**: Abnahmekriterium von Phase 4 lautet explizit "Ein
fehlgeschlagener Lauf wird als fehlgeschlagen dargestellt" — das gilt für
die Work Order, aber nicht konsistent für ihre Steps.

**Status**: nicht behoben — gehört laut Auftrag in den Scope von Phase 4,
nicht Phase 0.

### 3. `claude`-CLI überschreitet ihr eigenes `--max-budget-usd` — für einen eigenen Auftrag, aber vor Phase 3 relevant

**Befund**: Ein Lauf mit `--max-budget-usd 0.20` wurde von der `claude`-CLI
selbst mit `"subtype":"error_max_budget_usd"` abgebrochen — aber laut ihrem
eigenen `total_cost_usd`-Feld erst bei **$0.390591**, fast dem Doppelten des
gesetzten Caps. Ursache (aus dem lokalen Session-Transkript
`~/.claude/projects/.../*.jsonl` rekonstruiert): der allererste Tool-Call
kostete bereits $0.181 von $0.20 — fast ausschließlich `cache_creation`-Tokens
(~26.5k Tokens für System-Prompt/Tool-Schemas/Skill-Liste beim
Session-Aufbau). Die drei Turns selbst waren inhaltlich sinnvoll (Repo-
Bestandsaufnahme, dann ein korrekter, exakt zielgerichteter `Edit`-Aufruf für
die verlangte `multiply`-Funktion) — kein Kreisen, reiner Kosten-Fixkosten-
Boden, der das gesetzte Budget schon vor der ersten abgeschlossenen Aktion
gesprengt hat.

**Warum das zählt**: `--max-budget-usd` ist in `docs/background-dev-team-runbook.md`
als harte, verlässliche Obergrenze dokumentiert (OP-ClaudeBudgetGate-001).
Sie ist es nicht — die CLI überschreitet sie selbst. Vor Phase 3
(Parallelität, zwei gleichzeitige Läufe) relevant: zwei Läufe können damit
potenziell **je** ihr Budget um das Doppelte überschreiten, unabhängig
voneinander.

**Status**: nur festgehalten, kein Fix in diesem Auftrag — eigener Auftrag
später.

### 4. `activityLogs[].agentRunId` — Runner rät die eigene AgentRun-ID falsch, FK-Verletzung verschluckt 8/8 Einträge — behoben in M1

**Befund**: Der zweite Live-Lauf (`--max-budget-usd 1.50`, Ergebnis
`blocked`) lieferte ein `result.json` mit 8 `activityLogs`-Einträgen — in
**allen acht** stand im Feld `agentRunId` die ID des gerade bearbeiteten
Ticketplan-Steps (z. B. `4ede8ae4-…` für "Product Agent"), nicht die echte
AgentRun-ID (`46866555-…`). Grund: `build_runner_prompt()` teilt dem
Runner die echte AgentRun-UUID nirgends mit — der Prompt enthält nur
Step-IDs. Der Runner hat plausibel geraten und die einzige ID verwendet,
die er kannte.

`import_work_order_result.py` sendete diesen Wert unverändert weiter
(`if agent_run_id and not entry.get("agentRunId")` — füllte nur Lücken,
überschrieb nie einen vom Runner gesetzten Wert). Jeder der acht
`POST .../activity-log`-Aufrufe verletzte damit die Fremdschlüssel-
Beziehung `activity_log.agent_run_id → agent_runs.id` (eine Step-ID ist
keine gültige AgentRun-ID) und scheiterte serverseitig mit HTTP 500. Das
Skript zählt das nur als `log_failures` (blockiert nicht den
`finalStatus`-Write), zeigt es aber im Terminal als `FAIL activity log
entry: ...` — im gespeicherten Activity Log der Work Order fehlte danach
die komplette Erzähl-Spur des Laufs (repo_inspected, plan_confirmed,
code_edit ×2, test_run_failed, dependency_install_required,
static_review_completed, run_completed — alle acht).

**Warum das zählt**: Activity Log ist die einzige nachvollziehbare Spur
dessen, was ein Agent tatsächlich getan hat — bei einem `blocked`- oder
`failed`-Lauf oft wichtiger als die finalen Step-Summaries. Ein stiller
8/8-Verlust untergräbt dieselbe Nachvollziehbarkeits-Eigenschaft wie
Befund 1 oben, nur auf der Datenebene statt auf der Attributionsebene.

**Fix (dieser Auftrag, JARVIS-M1)**: `import_work_order_result.py` —
die harness-eigene `agent_run_id` (bekannt, weil `run_work_order.py` das
AgentRun selbst angelegt hat) überschreibt jetzt IMMER, statt nur Lücken
zu füllen. Nur wenn keine harness-eigene `agent_run_id` vorliegt (Stand-
alone-Import), wird der vom Runner gesetzte Wert geprüft: stimmt er mit
einer der `result.json`-eigenen Step-IDs überein, wird er verworfen
(`None`) statt durchgereicht. Ein echter, fremder Wert bleibt in diesem
Fall unangetastet. Drei neue Tests in
`scripts/test_import_result_integrity.py::ActivityLogAgentRunIdMixupTests`
pinnen genau diese drei Fälle; ein bestehender Test in
`scripts/test_agent_run_session.py`, der noch das alte "nie überschreiben"-
Verhalten erwartete, wurde auf den neuen Vertrag umgestellt.

### 5. Fixture-Repo hat keine eigene Testumgebung — für Phase 2/3 einplanen

**Befund**: Der Runner-Agent fand im Zielrepo `C:\Users\serka\dev\cp-e2e-fixture`
kein `pytest` (weder venv noch System-Installation) und konnte das
Akzeptanzkriterium "alle Tests grün" deshalb nicht verifizieren — korrekt
als `blocked` statt als unverifizierten Erfolg gemeldet (kein Bug, siehe
Übergabe `docs/übergaben/M1-phase0.md`). Der von der `claude`-CLI genutzte
Python-Interpreter im Zielverzeichnis ist der System-Python, nicht
`cp-multiagent\.venv` — jedes neue Zielrepo bringt standardmäßig keine
lauffähige Testumgebung mit.

**Warum das zählt**: Phase 2 (Isolation über Git-Worktrees) und Phase 3
(zwei parallele Läufe) erzeugen neue Arbeitsverzeichnisse pro Auftrag. Ohne
eine Vorkehrung für eine lauffähige Testumgebung pro Worktree landet jeder
Lauf, der Tests verifizieren soll, standardmäßig auf `blocked` — nicht,
weil der Agent etwas falsch macht, sondern weil die Umgebung fehlt.

**Status**: nur festgehalten, kein Fix in diesem Auftrag — für Phase 2
einplanen (z. B. Worktree-Setup inkl. venv/Dependency-Bootstrap, oder ein
Vorbedingungs-Check, der das fehlende Testtooling schon vor dem Start
meldet statt es den Agenten in jedem Lauf neu entdecken zu lassen).
