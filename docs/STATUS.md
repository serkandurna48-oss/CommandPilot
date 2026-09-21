# STATUS — CommandPilot / Jarvis

Letzte Aktualisierung: 21.09.2026 — main auf `dc1e225`, Merge von
`integration/commandpilot-stable` abgeschlossen und verifiziert.
Diese Datei ist der Einstieg. Wer hier anfängt, weiß, wo alles steht.

## COMMANDPILOT STABLE BASELINE

Dieser Abschnitt beschreibt den tatsächlichen Ist-Zustand von `main` nach
Abschluss des aktuellen Entwicklungszyklus (Fast-Forward-Merge von
`integration/commandpilot-stable` auf `main`, HEAD `dc1e225`, ohne History-
Rewrite, keine neuen Features gegenüber der Integrationsbranch).

### Produktfähigkeiten (aktueller Stand)

- **Daily Planner** — Check-in → KI-Tagesplan → Review, plus Rules und
  Projects, seit längerem stabiler Kern.
- **Home Briefing** (`HomeBriefing.tsx`) — Dashboard wurde von der alten
  Command-Hero/Timeline-Ansicht auf eine kompakte Morgen-Briefing-Ansicht
  umgebaut (Today-Priorität, "Needs your decision", In Progress, Recent
  Activity).
- **Focus Deck Shell** — gemeinsames `app/(app)/layout.tsx` hält genau eine
  `FocusDeckShell`-Instanz (Icon-Rail + persistente Jarvis-Spalte) über alle
  authentifizierten Routen hinweg (Dashboard, Jarvis, Projects, Morning,
  Daily Plan, Daily Review, Operator, Rules, Settings). Im Smoke-Test
  bestätigt: Jarvis-Chat-Zustand (inkl. sichtbarem Fehlerbanner und
  ungesendetem Eingabetext) bleibt beim Wechsel zwischen Routen über die
  Icon-Rail erhalten — Klick-Navigation, nicht volle Browser-Navigation.
- **Jarvis Chat mit Second-Brain-Kontext** (`/jarvis`, `POST
  /api/jarvis/chat`) — ein Retrieval (`vault_service.py`) für Tagesplan und
  Chat, Keyword-Matching, kein Embeddings-Layer, siehe CLAUDE.md-Abschnitt
  "Jarvis" für den vollständigen Vertrag.
- **Q1 Qualitätsnetz** — zehn Testfälle für Retrieval/Chat-Verhalten, grün.
- **C1 Command Layer / Suggested Actions** — Chat kann `suggested_actions`
  zurückgeben, UI zeigt Bestätigen-/Ablehnen-Karten, Bestätigen legt eine
  echte Work Order + Approval Scope + Activity-Log an
  (`suggested_action_service.py`), Ablehnen schreibt einen Audit-Eintrag in
  `suggested_action_decisions` (Migration `013`) ohne Work Order. Serverseitige
  Idempotenz bei gleichzeitigen Confirm-Requests geprüft (siehe frühere
  Abnahme-Notizen unten für Details).
- **Background Operator / Work-Order-System** — Work-Order-CRUD, Runner-
  Harness (`scripts/run_work_order.py`, Adapter-Konzept), Bounded Retry,
  Import-Idempotenz, State Machine für Work-Order-/Step-/AgentRun-Übergänge.
- **Auth-Persistenz-Fix** — Jarvis-Zustand übersteht Auth-Events (Login/
  Logout/Token-Refresh) korrekt, statt verloren zu gehen.
- **Harness-/Import-Fix** — Transitions aus dem Runner/Import-Skript melden
  sich selbst korrekt als Quelle, `agentRunId` bleibt harness-autoritativ
  statt vom Client überschreibbar.

### Architektur (unverändert gegenüber CLAUDE.md, hier nur die Kurzfassung)

- Next.js App Router Frontend, FastAPI Backend, Supabase (Postgres + Auth)
  als einzige Datenpersistenz, OpenAI GPT-4o für Tagesplan- und Jarvis-Chat-
  Generierung.
- Ein Retrieval (`vault_service.py`), zwei Aufrufer (Tagesplan-Prompt,
  Jarvis-Chat) — keine parallele Kontext-Pipeline.
- Eine `FocusDeckShell`-Instanz pro Session über `app/(app)/layout.tsx`,
  keine oberflächenspezifische Logik-Duplikation zwischen Chat/Dashboard.
- Vollständige Details: `CLAUDE.md`, Abschnitte "Jarvis",
  "Projektstruktur", "Auth-/Security-Grundregeln".

### Bestätigte Sicherheitseigenschaften

- Backend leitet `user_id` nie vom Client ab (`get_current_user()`), jeder
  Endpoint auf nutzereigenen Tabellen filtert über `user_id`.
- Vault-Zugriff an `VAULT_OWNER_USER_ID` gebunden, leerer Kontext statt
  Dateisystemzugriff bei Mismatch.
- Jarvis-Chat läuft durch dieselbe Kostenobergrenze (`usage_service`) wie
  die Tagesplan-Generierung.
- Suggested Actions führen nie automatisch etwas aus — Bestätigen/Ablehnen
  ist ein expliziter Nutzerklick, beides wird auditiert (Work Order bzw.
  `suggested_action_decisions`).
- Kein stiller Mock-Fallback im Jarvis-Chat bestätigt: Im ersten Smoke-Test
  nach diesem Merge produzierte ein verdeckter Key-Konflikt (siehe unten)
  einen sichtbaren Fehlerzustand mit Retry-Button in der UI, keine erfundene
  Antwort, kein stiller Fallback.

### Aktueller Teststatus (Stand 21.09.2026, auf main nach Merge geprüft)

- `scripts/check.ps1`: **grün** — 61 Backend-Pytests, Frontend-Type-Check,
  Frontend-Lint. (Hinweis: `.next`-Build-Cache im main-Worktree war nach dem
  Merge veraltet — bezog sich noch auf die vor dem Merge gelöschten Pfade
  `app/dashboard`/`app/jarvis`. Kein Code-Regressionssignal, nach
  `rm -rf frontend/.next` verschwunden.)
- `python scripts/test_import_result_integrity.py`: **grün**
- `python scripts/test_agent_run_session.py`: **grün**
- `python scripts/test_bounded_retry.py`: **grün**
- Manueller Browser-Smoke-Test (echter Login, echter Supabase/Backend/
  OpenAI, main-Worktree, Dev-Server lokal gestartet), zwei Durchläufe:
  - Login: **bestanden**
  - `/dashboard` (Home Briefing): **bestanden**
  - Routenwechsel behält Chat-Zustand: **bestanden** (über Icon-Rail-Klicks,
    nicht über volle Browser-Navigation getestet — letzteres setzt
    erwartungsgemäß React-State zurück)
  - Operator öffnet: **bestanden**
  - Settings öffnet: **bestanden**
  - Logout: **bestanden** (korrekter Redirect auf `/login?next=...`)
  - Jarvis-Antwort auf eine normale Wissensfrage: **bestanden** (zweiter
    Durchlauf, nach Fix des Key-Konflikts unten) — echte, im Vault
    gegründete Antwort inkl. Quelle (`Projekte/Jarvis.md`).
  - Goal-förmige Anfrage → genau zwei Suggested Actions: **bestanden** —
    eine einzelne Chat-Nachricht ("Bereite die nächsten Schritte für die
    CampPilot-Weiterentwicklung mit JK vor und leg mir dafür Work Orders
    an.") erzeugte genau zwei Karten mit Bestätigen/Ablehnen, beide mit
    echten Vault-Quellen (`Projekte/JK-Academy.md`, `Projekte/CampPilot.md`).
  - Eine Suggested Action ablehnen → keine Work Order: **bestanden** — Karte
    zeigt "Rejected", Recent Activity unverändert, Backend-Endpoint
    `POST /api/jarvis/suggested-actions/reject` → 200.
  - Eine Suggested Action bestätigen → genau 1 Work Order + Approval Scope +
    Audit: **bestanden** — Backend-Endpoint
    `POST /api/jarvis/suggested-actions/confirm` → 200, echte Work Order
    "Nächstes Roadmap-Ticket definieren" im Operator sichtbar (Status
    Draft), Approval Scope korrekt dreigeteilt (allowed/requires
    approval/blocked), Activity Log mit Eintrag "Aus Jarvis-Vorschlag
    übernommen (Risiko: medium, genehmigungspflichtig: ja)". Kein Agent
    wurde gestartet (Local Runner: "Not started yet", Agent Runs: "No agent
    runs yet") — absichtlich, nicht Teil dieses Smoke-Tests.

### Bekannte Einschränkungen

- **Korrektur einer früheren Fehldiagnose**: Der erste Smoke-Test dieses
  Zyklus meldete fälschlich einen "ungültigen/abgelaufenen" OpenAI-Key. Der
  tatsächliche Befund: Auf der Entwicklungsmaschine war zusätzlich zum
  korrekten Key in `backend/.env` eine gleichnamige, veraltete
  Shell-Umgebungsvariable `OPENAI_API_KEY` gesetzt. `pydantic-settings`
  (`Settings` in `app/core/config.py`, `env_file=".env"`) priorisiert
  standardmäßig echte Prozessumgebungsvariablen vor Werten aus der
  `.env`-Datei — der Backend-Prozess nutzte also unbemerkt die falsche,
  ungültige Variable statt des korrekten Keys aus der Datei. Nach Neustart
  des Uvicorn-Prozesses ohne diese Shell-Variable griff der echte Key aus
  `backend/.env` sofort — bestätigt per direktem OpenAI-Testaufruf und im
  Browser-Smoke-Test. **Für die Entwicklungsmaschine zu prüfen**: ob diese
  Shell-Variable dauerhaft (z. B. im PowerShell-Profil) gesetzt ist — falls
  ja, sollte sie entfernt oder synchron zu `backend/.env` gehalten werden,
  sonst wiederholt sich dieser stille Vorrang bei jedem frischen Terminal.
- Alle Einschränkungen aus CLAUDE.md, Abschnitt "Bekannte Risiken", gelten
  unverändert fort (Safety-Rules-Dreifach-Duplizierung, Mock-Fallback-
  Risiko in `mockWorkOrders.ts`, CLI-Runner-Pfad nie live gegen `claude`
  getestet).

### Zurückgestellte künftige Arbeit (nicht spekulativ, nur was bereits als
nächster Schritt benannt ist)

- Produktrichtung Schritt 4–7 aus CLAUDE.md (Dashboard-Ausbau, Sprache,
  Integrationen, Hintergrundagenten) — nicht begonnen, bewusst nicht in
  diesem Zyklus.
- `docs/aufträge/JARVIS-Q1` und `JARVIS-C1`: laut CLAUDE.md als "noch nicht
  bearbeitet" markiert, obwohl die zugehörigen Features (Qualitätsnetz,
  Command Layer) bereits in main sind — Auftragsdokumente vs. Code-Realität
  hier ggf. gegenzuprüfen, wenn als nächstes an Q1/C1 weitergearbeitet wird.
- Worktree-Aufräumung (`cp-command-layer`, `cp-focus-deck`, `cp-design`,
  `commandpilot-ai-setup`, iCloud-Duplikate) — Audit ausstehend, siehe
  unten, nichts gelöscht ohne Freigabe.

## Wo die Stränge stehen

| Strang | Ort | Branch | Stand | Nächster Schritt |
|---|---|---|---|---|
| **main** | dev/commandpilot | main | **HEAD `dc1e225`, enthält Focus Deck + Jarvis Rail + Q1 + C1 + Suggested Actions + Home Briefing + Auth-Fix + Harness-Fix, alle Tests grün, Jarvis- und Suggested-Action-Flow live verifiziert** | Cleanup-Audit (Phase 5) auf explizite Freigabe hin abarbeiten |
| integration/commandpilot-stable | dev/cp-home | integration/commandpilot-stable | identisch zu main (Quelle des obigen Merges) | kann nach Bestätigung als Branch aufgeräumt werden |
| Design D1 (Steel-Blue) | dev/cp-design | feat/design-system | verworfen, nie gemerged | Cleanup-Kandidat, siehe Phase 5 |
| Multiagent M1 | dev/cp-multiagent | feat/multiagent | Phase 0 bestanden, nicht Teil dieses Merges | separat weiterverfolgen oder parken |

## Entscheidungen, die stehen

- Freigaben bleiben in der Oberfläche, nie als CLI-Flag
- API-Token nie in einen Agent-Kontext, Serkan startet Runner selbst
- Ein Clone unter dev, Worktrees für Parallelarbeit, iCloud nur als Backup
- Sessions pushen nie und mergen nie nach main ohne Freigabe

## Offene Befunde

| Befund | Wo | Priorität |
|---|---|---|
| Veraltete Shell-Umgebungsvariable `OPENAI_API_KEY` überschied evtl. dauerhaft den korrekten `backend/.env`-Wert | Entwicklungsmaschine, PowerShell-Profil? | prüfen, ob dauerhaft gesetzt |
| Activity-Log: Step-IDs im Feld agent_run_id (8 Fehlschläge, historisch) | import_work_order_result.py | prüfen ob noch aktuell |
| /operator/new verliert Formularzustand | UI | offen |
| Notion sagt CommandPilot "Wartet"/P3, Vault sagt active | Notion | klein |

## Wie man morgen einsteigt

1. Diese Datei lesen
2. `git log --oneline -10` auf main
3. Falls Jarvis lokal einen Auth-Fehler wirft: zuerst prüfen, ob eine
   Shell-Umgebungsvariable `OPENAI_API_KEY` den Wert aus `backend/.env`
   überschreibt, bevor der Key selbst verdächtigt wird
4. Dann erst arbeiten
