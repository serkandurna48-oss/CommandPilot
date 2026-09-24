# CLAUDE.md — CommandPilot

> Single Source of Truth für KI-Assistenten in diesem Repo.
> Bei Widerspruch zum Code gilt: **Code schlägt dieses Dokument** — dann bitte hier updaten.

---

## Was ist CommandPilot

Personal Operating System: aus einem morgendlichen Brain-Dump (Energie, Schlaf,
Stimmung, feste Termine, Aufgaben) erzeugt eine KI einen strukturierten Tagesplan
(Prioritäten, Zeitblöcke, Energie-Strategie, Review-Fragen). Nutzer hinterlegen
persönliche Regeln, die die KI berücksichtigt, und schließen den Tag mit einem
Abendreview ab. Alles wird pro authentifiziertem Nutzer/Workspace in Supabase
persistiert.

**Zwei Module, beide vollständig auf `main`** (Operator Control Plane per
Fast-Forward-Merge nach `77e18cb` am 18.09. auf `main` gemerged und gepusht —
frühere "[nur auf feat/operator-control-plane]"-Markierungen sind hinfällig):

1. **Daily Planner** — der stabile Kern (Check-ins, AI-Pläne, Reviews, Rules,
   Projects).
2. **Operator Control Plane / "Background Dev Team"** — Work-Order-gesteuerte
   Ausführung von Coding-Agents über lokale Runner-Adapter (`backend/app/routers/
   work_orders.py`, `scripts/run_work_order.py`, `docs/`).

---

## System-Kontext

CommandPilot ist der Kern, nicht das einzige System:

- **CommandPilot** (dieses Repo) — Tagesplanung + Operator Control Plane, der
  aktive Arbeitsraum.
- **secondbrain-Vault** — die Wissensschicht. Vertrag: **CommandPilot liest das
  Vault, nie umgekehrt.** Das Vault ist keine Datenbank, die CommandPilot
  beschreibt.
- **CampPilot** — eigenständiges Kundenprodukt, kein Modul von CommandPilot.
  Nicht mit CommandPilots Operator Control Plane verwechseln, auch wenn
  Work Orders CampPilot als Target-Repo referenzieren können.

Source of Truth für externe Information bleibt außerhalb dieses Systems: Notion,
GitHub, Kalender, Mail. Nichts davon wird nach CommandPilot gespiegelt oder
dupliziert — es wird referenziert, wenn gebraucht, nicht vorab synchronisiert.
Seit 22.09.2026 gilt das auch technisch für Kalender/Notion: `google_calendar_service.py`,
`outlook_calendar_service.py` und `notion_tasks_service.py` fragen live über
Composio ab, bei jedem Jarvis-Chat neu — kein Sync-Job, keine Kopie in
Supabase. Siehe Abschnitt "Jarvis" unten.

## Produktrichtung

Bindende Reihenfolge für die nächsten Ausbaustufen:

1. **Erledigt** — Second-Brain-Kontext in die Tagesplanung holen. Siehe
   Abschnitt "Jarvis" unten.
2. **Erledigt** — Text-Chat auf derselben Retrieval-Funktion wie (1) — keine
   zweite, parallele Kontext-Pipeline. `/jarvis`, siehe Abschnitt "Jarvis".
3. **Erledigt (20.09.2026)** — Aktionen mit Vorschau und Bestätigung — nichts
   wird ausgeführt, ohne dass der Mensch vorher sieht, was passieren würde.
   Umgesetzt als Suggested-Action-Confirm/Reject-Flow, siehe Abschnitt
   "Jarvis" unten (Response-Vertrag) sowie
   `docs/aufträge/JARVIS-C1 — Command Layer, der nächste sichtbare Ablauf.md`.
4. **Nächster Schritt** — Dashboard.
5. Sprache.
6. **Teilweise vorgezogen (22.09.2026)** — Integrationen: Kalender (Google
   Calendar UND Outlook, unabhängig voneinander — Serkan nutzt Outlook
   tatsächlich mehr) und Notion (My Tasks) sind für Jarvis-Chat UND
   Tagesplan-Generierung angebunden (alle über denselben Composio-Zugriff,
   `routers/jarvis.py` bzw. `routers/plans.py`), auf expliziten Wunsch
   außerhalb dieser Reihenfolge. Siehe Abschnitt "Jarvis" unten. Weitere
   Integrationen (Mail, GitHub)
   bleiben offen.
7. Hintergrundagenten — innerhalb der bestehenden Safety Rules
   (`backend/app/core/safety_rules.py`, Approval Scopes), nicht als
   Erweiterung, die sie umgeht.

**Architekturprinzip:** Oberflächen sind austauschbar, Retrieval und Kern sind
das eigentliche Vermögen. Chat, Sprache und Dashboard rufen dieselben
Kernfunktionen auf — keine oberflächenspezifische Logik-Duplikation. Bei jeder
neuen Oberfläche zuerst prüfen: ruft sie eine bestehende Kernfunktion auf, oder
baut sie eine neue, parallele?

---

## Jarvis (Second-Brain Chat + Tagesplan-Kontext)

Setzt Produktrichtung Schritt 1+2 um. Ein Retrieval, zwei Aufrufer — kein
Duplikat. Entstanden über JARVIS-A1 (`docs/aufträge/`), das u. a. die
ursprüngliche Version dieses Abschnitts nachgezogen hat.

**Kern**: `backend/app/services/vault_service.py`. Liest den Obsidian-Vault
unter `VAULT_PATH` (Env-Var; leer/unlesbar → leerer Kontext plus Logeintrag,
wirft nie eine Exception — auch nicht bei ungültigem UTF-8 in einer
Vault-Datei, die betroffene Datei wird übersprungen, der Rest weiterverarbeitet).
Kein Embeddings, keine Vektordatenbank — reines Keyword-Matching, zwei Ebenen:

- **Basiskontext** (immer dabei): `00-Index.md` komplett + eine Zeile pro
  Entitäts-Notiz (Titel/erste Zeile + Frontmatter `type`/`status`/`priority`/
  `updated`). **Frontmatter-Vertrag**: Frontmatter erscheint NUR hier als
  Text — sie fließt nicht ins Scoring der Treffer-Ebene ein. Eine Anfrage,
  die "aktiv" erwähnt, scored nicht höher gegen eine Notiz mit
  `status: active` als gegen eine ohne. Kein Frontmatter-Matching, absichtlich
  (Nicht-Ziel).
- **Treffer-Ebene**: Keyword-gescorte Abschnitte zur konkreten Anfrage,
  Überschrift/Dateiname höher gewichtet als Fließtext, Frontmatter spielt hier
  keine Rolle.

`get_context_for_query(query, user_id, total_token_budget=2200,
base_token_budget=1200, vault_path=None)` liefert `(block, hit_sources,
base_sources)`. `block` (Basis- + Treffer-Text kombiniert) geht vollständig
ins Prompt; von den Quellen wird standardmäßig nur `hit_sources` angezeigt —
die Treffer, die die Antwort tatsächlich getragen haben. `base_sources` (die
Landkarten-Einträge) sind separat verfügbar, aber nicht Default-sichtbar,
weil sie bei jeder Anfrage gleich groß sind und als "Quellen" nur Rauschen
wären. `base_token_budget` wird intern auf `total_token_budget` gedeckelt;
budgetiert wird der fertig formatierte Block inklusive der
`### Quelle: ...`-Label-Zeilen, nicht nur der rohe Treffertext.

**Eigentümer-Bindung**: `VAULT_OWNER_USER_ID` (Env-Var). Gesetzt und
`user_id` des Requests stimmt nicht überein → leerer Kontext, Logeintrag,
kein Dateisystemzugriff. **Seit 23.09.2026 in `backend/.env` tatsächlich
gesetzt** (Serkans echte user_id) — vorher war die Variable trotz
existierendem Code schlicht nicht konfiguriert, das Gate damit faktisch aus.
Siehe "Bekannte Risiken" für den live reproduzierten Datenleck, den das
verursacht hat, und `is_personal_integrations_owner()`
(`app/core/config.py`), das dieselbe Prüfung jetzt auch vor Calendar/Notion
schaltet. Kein Pro-Nutzer-Vault-System — ein Vault, ein Eigentümer, keine
Migration.

**Zwei Aufrufer, ein Retrieval:**
- `plan_service.get_vault_context_for_checkin(checkin, user_id)` —
  Tagesplan-Prompt (`prompts/daily_plan.py`, `vault_context`-Parameter)
  bekommt den Kontext als abgegrenzten Block mit der Anweisung, ihn als
  Hintergrund zu nutzen und nichts zu erfinden. Ohne Vault verhält sich die
  Plan-Generierung exakt wie vorher, Endpunkt-Signatur unverändert.
- `routers/jarvis.py` — `POST /api/jarvis/chat`, authentifiziert über
  `get_current_user`, `user_id` nie vom Client. Läuft durch dieselbe
  Kostenobergrenze (`usage_service`, CP-203) wie die Tagesplan-Generierung —
  Chat ist beliebig oft aufrufbar, ohne Cap ein offener Geldhahn.
  Prompt-Konstruktion in `prompts/jarvis_chat.py`: Systemprompt zwingt
  Deutsch, verbietet Erfindung, verlangt offenes Eingeständnis bei fehlendem
  Wissen — und verbietet dem Modell explizit, selbst eine "Quellen:"-Zeile in
  den Antworttext zu schreiben (das übernimmt die UI separat). Ton-Regel
  (seit 22.09.2026, nach Nutzer-Feedback zweimal nachjustiert): locker/
  Bro-Style, aber Substanz und Präzision bleiben — kein Widerspruch, siehe
  Beispielsatz direkt im Prompt. Erste Version war zu steif, zweite zu
  slang-lastig für ernste Themen (Business-Strategie); aktueller Stand ist
  bewusst "locker im Ton, scharf im Inhalt", nicht die Mitte zwischen beidem.
  Zusätzlich: Regel, den Mehrwert einer Antwort explizit zu benennen (WARUM
  etwas zählt), nicht nur WAS im Kontext steht.
  **Fix (23.09.2026, live im Browser gefunden)**: `build_chat_prompt()` gab
  dem Modell nirgends das heutige Datum — Kalender-/Notion-Kontext liefert
  nur absolute ISO-Timestamps, ohne Anker kann das Modell "heute"/"morgen"
  nicht korrekt zuordnen. Live reproduziert: Jarvis sagte "Du hast heute den
  ganzen Tag bei VW eingeplant", obwohl der zitierte Kalendereintrag auf den
  Folgetag datiert war. `daily_plan.py`s `build_user_prompt()` hatte dieses
  Problem nicht (übergibt `checkin['checkin_date']` bereits). Fix: eine
  führende `HEUTIGES DATUM: <ISO> (<Wochentag>)`-Zeile vor dem Kontextblock,
  UTC (nicht lokalisiert — `ZoneInfo("Europe/Berlin")` scheitert auf
  Windows-Dev-Maschinen ohne `tzdata`-Paket, genau deshalb übergeben
  `google_calendar_service.py`/`outlook_calendar_service.py` die Zeitzone
  auch nur als String an Composio, statt sie lokal aufzulösen). Nach dem Fix
  live erneut geprüft: korrekte Antwort ("Morgen hast du was Fixes
  eingeplant... Heute scheint nichts Fixes im Kalender zu stehen."). Test:
  `test_jarvis_chat_prompt.py::test_prompt_grounds_the_model_in_todays_date`.

**Externer Kontext (Kalender ×2 + Notion, seit 22.09.2026)**:
`backend/app/services/google_calendar_service.py`,
`outlook_calendar_service.py` und `notion_tasks_service.py` — drei
unabhängige Quellen, alle mit demselben Nie-wirft-Vertrag wie
`vault_service.py`: fehlende Config, kein verbundener Account oder ein
Composio-Fehler ergeben `("", [])`, nie eine Exception. Google und Outlook
sind bewusst zwei getrennte Kalender-Services statt einem — Serkan nutzt
beide, keiner weiß vom anderen, ihre Aufrufer (`routers/jarvis.py`,
`routers/plans.py`) mergen die Ergebnisse. Alle drei laufen über
`backend/app/services/composio_client.py` (schlanker
`Composio(api_key=...)`-Singleton). Gate: `COMPOSIO_API_KEY` +
`COMPOSIO_USER_ID` (Composio-eigene User-ID, an die die Accounts angebunden
sind — Single-Tenant wie `VAULT_OWNER_USER_ID`, keine
Per-Supabase-Nutzer-Zuordnung, dieselbe User-ID für alle drei Quellen).
Notion zusätzlich `NOTION_TASKS_DATABASE_ID` (die "My Tasks"-Datenbank).
`google_calendar_service` deckt ein festes Fenster gestern–übermorgen ab
(`GOOGLECALENDAR_EVENTS_LIST`), `outlook_calendar_service` dasselbe Fenster
über `OUTLOOK_GET_CALENDAR_VIEW` (Response unter `data.value[]`, nicht
`data.items`/`data.events` wie bei Google — beide Services haben deshalb
eigene, nicht geteilte Extraktionslogik), `notion_tasks_service` liest offene
Zeilen aus der Tasks-Datenbank (`NOTION_QUERY_DATABASE`). Alle drei
formatieren ihre Treffer im selben `### Quelle: ...`-Stil wie
`vault_service.format_context_block`, mit unterscheidbaren Labels
("Kalender – Google" / "Kalender – Outlook" / "Notion — Offene Aufgaben") und
werden in `routers/jarvis.py::chat()` direkt an den vom Vault gelieferten
`context_block` angehängt (`"\n\n".join(...)`, leere Blöcke rausgefiltert) —
die Prompt-Schicht (`prompts/jarvis_chat.py`) sieht dadurch weiterhin nur
einen einzigen Kontext-String, keine Signaturänderung nötig. Seit 22.09.2026
genauso in `routers/plans.py` (Tagesplan-Generierung) verdrahtet — direkt im
Router nach demselben Muster, NICHT in
`plan_service.get_vault_context_for_checkin` selbst (die bleibt vault-only,
unverändert). Für den Tagesplan wird nur der formatierte Block verwendet,
nicht die strukturierten `sources` — dort gibt es keine Pro-Quelle-UI wie im
Jarvis-Chat.
Alle drei `get_context()`-Funktionen geben `(block, sources)` zurück, nicht
nur einen String — `sources` im selben `[{"file": ..., "heading": ...}]`-Shape
wie `vault_service`s `hit_sources`, aber eigenständig: `JarvisChatResponse`
hat dafür eigene Felder `calendar_sources` (Google+Outlook zusammengeführt)
und `task_sources` (`app/models/jarvis.py`), getrennt von `sources`/
`base_sources` (bleiben vault-only). Anders als vault_service budgetiert die
Kappung hier ganze Zeilen, nie mitten im Text — ein abgeschnittenes
Kalender-Event wäre irreführend, ein weggelassenes nicht.
Frontend: `components/jarvis/JarvisChat.tsx` zeigt beide Feldgruppen als
eigene `SourcesDisclosure`-Blöcke ("Kalender" / "Offene Aufgaben (Notion)"),
gleiches Muster wie `sources`/`base_sources` — die Google/Outlook-Herkunft
steckt nur im `file`-Label je Eintrag, nicht in eigenen UI-Sektionen.

**Work Orders als vierte Kontextquelle (seit 22.09.2026)**:
`backend/app/services/work_orders_context_service.py` — anders als die drei
oben liest diese Quelle CommandPilots eigene Datenbank direkt
(`work_order_service.get_work_orders_for_user`), kein externer Dienst, kein
Composio. Entstanden aus einem echten Fehlfund: Serkan fragte Jarvis "geh die
neueste Work Order mit mir durch", und Jarvis antwortete anhand einer
ähnlich klingenden Notion-Aufgabe ("Update KSV Baunatal", Status "Next"),
weil es schlicht keine Work-Order-Kontextquelle gab. Gleicher Vertrag wie die
anderen: `get_context(user_id, token_budget=500) -> (block, sources)`,
`("", [])` bei fehlender user_id oder DB-Fehler, nie eine Exception. Zeigt
die neuesten 10 Work Orders (`created_at desc`, bereits so aus
`get_work_orders_for_user`), Format `- <Titel> [<Repo>, falls ≠ commandpilot]
— Status: <status>`. Nur in `routers/jarvis.py::chat()` verdrahtet, NICHT in
`routers/plans.py` (Tagesplan) — naheliegende Erweiterung, aber bewusst nicht
Teil dieser Änderung. Eigenes Response-Feld `work_order_sources`
(`app/models/jarvis.py`), eigener `SourcesDisclosure`-Block in
`JarvisChat.tsx` ("Work Orders", `ClipboardList`-Icon).
**Test-Falle**: Jeder Test, der `POST /api/jarvis/chat` real durchläuft, MUSS
`jarvis_router.work_orders_context_service.get_context` mocken (typischerweise
`return_value=("", [])`) — sonst versucht der Service einen echten
Supabase-Call gegen die Test-Fake-URL und die Test-Suite wird spürbar
langsamer (bei diesem Fund: 3s → 20s), ohne dass ein Test fehlschlägt. Siehe
`test_jarvis_router.py` und `test_jarvis_quality.py` für die aktuelle
Mock-Liste.

**Frontend**: `/jarvis` (`frontend/app/jarvis/page.tsx` +
`components/jarvis/JarvisChat.tsx`), geschützte Route im bestehenden
AppShell (`ProtectedRoute`). Eingabefeld, Verlauf, Quellenliste unter jeder
Antwort (nur `sources`, nicht `base_sources`), sichtbarer Lade-/Fehlerzustand
mit Retry — nie stiller Mock-Fallback (siehe "Bekannte Risiken").

**Response-Vertrag** (`app/models/jarvis.py`): `JarvisChatResponse` hat
`suggested_actions: list[SuggestedAction]` — **seit 20.09.2026 implementiert**
(Produktrichtung Schritt 3, Command Layer,
`docs/aufträge/JARVIS-C1 — Command Layer, der nächste sichtbare Ablauf.md`;
eine frühere Version dieses Abschnitts beschrieb es noch als "immer leer,
nicht implementiert" — das war zum damaligen Zeitpunkt korrekt, ist es
jetzt nicht mehr). `prompts/jarvis_chat.py` weist das Modell an, bei einer
erkennbar umsetzbaren Anfrage genau zwei `SuggestedAction`-Einträge zu
füllen, sonst bleibt die Liste leer — ausgerichtet an `work_order.py`s
Feldern (`title`, `team_type`, `target_repo_name`, `risk`,
`requires_approval`, `sources`). Bestätigung/Ablehnung laufen über
`GET /api/jarvis/suggested-actions/decisions`,
`POST /api/jarvis/suggested-actions/confirm` und `.../reject`
(`routers/jarvis.py`), fachlich umgesetzt in
`services/suggested_action_service.py`: Confirm legt über
`work_order_service.create_work_order()` eine echte Work Order an,
abgesichert gegen Doppelbestätigung durch einen Unique-Index
(`013_suggested_action_decisions.sql`, 409 bei zweitem Versuch auf dieselbe
Entscheidung). Frontend: `components/jarvis/JarvisChat.tsx` zeigt dafür eine
`SuggestedActionCard` mit Confirm/Reject-Buttons. Weiterhin gültig: kein
Auto-Ausführen ohne diesen expliziten Bestätigungsschritt — das war und
bleibt der Kern von Schritt 3.

**Tests**: `backend/tests/test_vault_service.py`,
`test_daily_plan_vault_context.py`, `test_jarvis_router.py`,
`test_jarvis_chat_prompt.py`, plus (22.09.2026) `test_google_calendar_service.py`,
`test_outlook_calendar_service.py`, `test_notion_tasks_service.py` und
`test_work_orders_context_service.py`, sowie (20.09.2026, Command Layer)
`test_jarvis_quality.py` (die zehn JARVIS-Q1-Fälle) und
`test_suggested_action_service.py` (Confirm/Reject, Idempotenz) — alle
pytest-discoverbar, laufen über `scripts/check.ps1` mit. `test_jarvis_router.py`
enthält seit 22.09.2026
zusätzlich zwei Fälle für den externen Kontext: Kalender/Notion landen im
`context_block`, und ein Composio-Fehler bricht den Chat nicht ab (200 statt 500).

**Prüfen**: `scripts/check.ps1` — ein Befehl, ohne Argumente, aus dem
Repo-Root. Läuft nacheinander Backend-Pytest (`backend/tests`),
Frontend-Type-Check und Frontend-Lint, gibt am Ende eine Zusammenfassung mit
Exit-Code aus (0 = alles grün). `npm run build` ist bewusst nicht enthalten
— scheitert ohne `.env` am Prerendering aller geschützten Seiten, das ist
bekannt und kein Regressionssignal.

---

## Stack & Versionen

| Komponente | Technologie | Version |
|---|---|---|
| Frontend | Next.js (App Router) | 14.2.16 |
| UI | React | 18.3.1 |
| Styling | Tailwind CSS | 3.4.x |
| Language | TypeScript | ^5 |
| Backend | FastAPI | 0.115.4 |
| Validation | Pydantic v2 | 2.13.4 |
| Supabase Client | supabase-py | 2.30.0 |
| Database/Auth | Supabase (Postgres + Auth) | — |
| AI | OpenAI GPT-4o, JSON-Mode | openai==3.17.0 (22.09.2026 von 1.54.4 hochgezogen — composio zwingt openai>=2.48.0, siehe unten) |
| Externer Kontext | Composio SDK (Google Calendar, Outlook, Notion) | composio==0.22.0 |

## Wichtige Befehle

```bash
# Empfohlen: alles auf einmal prüfen, aus dem Repo-Root, ohne Argumente
.\scripts\check.ps1
# Läuft Backend-Pytest + Frontend-Type-Check + Frontend-Lint nacheinander,
# Zusammenfassung + Exit-Code am Ende. npm run build bewusst nicht enthalten
# (scheitert ohne .env am Prerendering aller geschützten Seiten).

# Voller lokaler Dev-Start (öffnet 2 Fenster)
./start-dev.ps1
# Backend: & <repo>\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 (aus backend/)
# Frontend: npm run dev (aus frontend/)

# Frontend einzeln
cd frontend
npm run dev          # Dev-Server
npm run build         # Production-Build
npm run lint          # ESLint (next lint)
npm run type-check    # tsc --noEmit

# Backend-Tests einzeln
pip install -r backend/requirements-dev.txt   # pytest, einmalig
python -m pytest backend/tests/ -v
```

- **Kein Test-Framework im Frontend konfiguriert** (kein Jest/Vitest) — nichts erfinden.
- **Kein Lint/Format-Tool im Backend** (kein ruff/black) — nichts erfinden.
- Backend hat eine echte pytest-Suite: `backend/tests/` (14 Dateien, Stand
  23.09.2026 — zehn davon Jarvis-/Second-Brain-bezogen, siehe Abschnitt
  "Jarvis" für die vollständige Liste; die restlichen vier decken
  Operator-Kernmechanik ab: `test_work_order_transitions.py`,
  `test_work_order_daemon_trigger.py`, `test_result_import_idempotency.py`,
  `test_project_model.py`. Bei Zweifel `Get-ChildItem backend/tests` neu
  zählen statt dieser Zahl zu trauen — sie driftet erfahrungsgemäß schnell),
  Setup über `backend/requirements-dev.txt`. `scripts/test_*.py` bleiben separate,
  absichtlich stdlib-only Standalone-Skripte (`python scripts/
  test_bounded_retry.py` etc.) — nicht pytest-discoverbar, das ist Design,
  kein Fehlen.
- Aktuelle Messlatte vor jedem Merge: `scripts/check.ps1` + die drei
  `scripts/test_*.py` + manuelle Kernflow-Prüfung im Browser.

## Projektstruktur

```
frontend/
  app/            # dashboard, login, signup, morning, plans/[id], review, rules,
                  # settings, projects, operator/, operator/new, operator/[id], jarvis/
  components/     # dashboard, layout, morning, plans, projects, review, rules, ui,
                  # components/operator/*, components/jarvis/JarvisChat.tsx
  lib/            # api.ts, auth.tsx, i18n.ts, supabase.ts, utils.ts,
                  # generateRunnerPrompt.ts, workOrderMapper.ts, mockWorkOrders.ts,
                  # safetyRules.ts, operatorStyles.ts

backend/
  app/routers/    # auth, health, checkins, plans, projects, reviews, rules,
                  # work_orders, jarvis
  app/services/   # ai_service, checkin_service, plan_service, project_service,
                  # review_service, usage_service, work_order_service, vault_service,
                  # google_calendar_service, outlook_calendar_service,
                  # notion_tasks_service, composio_client, work_orders_context_service
                  # (22.09.2026)
  app/models/     # checkin, plan, project, review, rules, work_order, jarvis
  app/core/       # config.py, safety_rules.py
  app/prompts/    # daily_plan.py, jarvis_chat.py — isolierte AI-Prompt-Konstruktion
  app/db/         # client.py — Supabase-Client-Singleton
  tests/          # pytest-Suite (Dateizahl hier vor 22.09.2026 schon nicht
                  # aktuell gepflegt — nicht als exakte Quelle nehmen, siehe
                  # tatsächliches Verzeichnis). Neu am 22.09.2026:
                  # test_google_calendar_service.py, test_outlook_calendar_service.py,
                  # test_notion_tasks_service.py, test_work_orders_context_service.py
  requirements.txt, requirements-dev.txt  # dev-only: pytest

supabase/
  schema.sql
  migrations/     # 001-016, sequenziell, alle auf main

scripts/          # check.ps1 — ein-Befehl-Prüfung, siehe "Wichtige Befehle".
                  # Sonst: lokale Runner-Harness (run_work_order.py,
                  # import_work_order_result.py, runner_adapters/*), plus
                  # test_bounded_retry.py, test_import_result_integrity.py,
                  # test_agent_run_session.py (stdlib-only Standalone-Tests)

docs/
  aufträge/       # Auftragsdokumente für KI-Sessions (JARVIS-A1, -Q1, -C1 —
                  # letztere zwei sind noch nicht bearbeitet)
  # sonst siehe "Docs-Index" unten

.claude/
  rules/          # frontend.md, backend.md, database.md — pfadspezifische Detailregeln
  agents/         # commandpilot-regression-check.md, architecture-consistency-check.md

AGENTS.md         # Agent-Konventionen für dieses Repo (Codex/generisches Format)
```

Vor jeder Annahme über einen Pfad oben: prüfen, ob er im aktuellen Checkout wirklich
existiert (`git worktree list` / `git branch -vv`) — dieses Repo wird häufig über
mehrere Git-Worktrees/Branches parallel bearbeitet.

## Auth-/Security-Grundregeln

- Supabase Auth (E-Mail/Passwort). Frontend sendet
  `Authorization: Bearer <supabase_access_token>`.
- Backend leitet `user_id` **niemals** vom Client ab — immer über
  `get_current_user()` (`backend/app/auth.py`), das den Token gegen Supabase validiert.
- Jeder neue Endpoint auf einer nutzereigenen Tabelle **muss** über
  `require_owned_record()` bzw. ein explizites `.eq("user_id", user.id)` filtern —
  404 (nicht 403) bei Nicht-Eigentümerschaft, um Existenz nicht zu leaken.
- `ensure_user_workspace()` bootstrapt Profile + persönlichen Workspace +
  `workspace_members`-Zeile idempotent — muss idempotent bleiben.
- Service-Role-Key ausschließlich im Backend, nie ans Frontend exponieren.

## DB-/Migration-Regeln

- `supabase/migrations/NNN_beschreibung.sql`, sequenziell nummeriert, manuell in der
  Supabase SQL Editor ausgeführt. Aktueller Stand: 001–016, alle auf `main`
  (016 fügt `work_orders.daemon_run_requested_at` hinzu — siehe "Bekannte
  Risiken" zum Live-Ausführungsstand).
- Standard: idempotent (`IF NOT EXISTS`-Guards). Bekannte Ausnahmen:
  `004_ai_usage_log.sql`, `006_work_orders.sql`, `007_work_order_steps.sql` und
  `013_suggested_action_decisions.sql` (alle vier `CREATE POLICY` ohne Guard,
  jede Migrationsdatei dokumentiert das selbst inline) — alle vier nur einmal
  ausführen.
- Detaillierte Regeln (RLS-Pattern, README-Sync-Pflicht): siehe
  `.claude/rules/database.md`.

## Python-Environment (venv)

Auf der Entwicklungsmaschine können bis zu drei lokale venvs existieren (alle
gitignored, kein Leak-Risiko): Root `venv/` (veraltet/Altlast, nicht verwenden),
Root **`.venv/`** (**kanonisch** — wird tatsächlich von `start-dev.ps1` für den
Uvicorn-Start genutzt), `backend/venv/` (redundant, entsteht durch README's manuelle
Setup-Anleitung). Bei Dependency-/Import-Problemen zuerst gegen Root-`.venv` prüfen.
Kein automatisches Löschen der anderen ohne explizite Anweisung.

## Git-/Branch-Regeln

- `main` = vollständiger Stand (Daily Planner + Operator Control Plane), seit dem
  Fast-Forward-Merge von `feat/operator-control-plane` nach `77e18cb` (18.09.,
  gepusht). `feat/operator-control-plane` existiert als Branch weiter, ist aber
  vollständig in `main` enthalten — nicht mehr die "fortgeschrittenere" Quelle.
- `chore/commandpilot-ai-setup` ist überholt: `.claude/` und `AGENTS.md` sind
  inzwischen deckungsgleich auf `main`, `CLAUDE.md` ist auf `main` weiter
  gepflegt worden und dort aktueller als auf diesem Branch. Kein aktiver
  Quell-Branch mehr für diese Dateien.
- Dieses Repo wird häufig in mehreren Git-Worktrees parallel ausgecheckt — vor
  Annahmen über vorhandene Dateien `git worktree list` prüfen.
- Nie ungefragt mergen, rebasen oder pushen. Ein Thema, ein Commit. Nichts committen
  ohne Bestätigung des Entwicklers.

## Test-/Review-Regeln

- Automatisierter Test-Stand vorhanden, aber schmal (siehe "Wichtige Befehle"):
  `backend/tests/` (pytest, 14 Dateien) deckt Operator-Control-Plane-Kernmechanik
  (State Machine, Bounded Retry, Import-Idempotenz) UND die Jarvis-Wissensschicht
  (Retrieval, Budget, Ownership-Gate, Chat-Endpunkt/-Prompt) ab. `scripts/test_*.py`
  (stdlib) bleiben separat für die Runner-Harness — kein E2E-, kein
  Frontend-Test-Framework. Vor einem Merge: `scripts/check.ps1` +
  `scripts/test_*.py` + manuelle Prüfung der Kernflows im Browser.
- Für tiefere Prüfungen die beiden Subagents nutzen:
  - `commandpilot-regression-check` — Code-vs-Code (Interfaces, Schichtung, Auth,
    Migrationen, Kernflows).
  - `architecture-consistency-check` — Doku-vs-Code (README/docs vs. echte
    Struktur, Mock-Fallback-Risiken, veraltete Annahmen).

## Docs-Index

| Datei | Inhalt |
|---|---|
| `commandpilot-current-state-and-business-roadmap.md` | Zentrales Ist-Zustand-/Risiko-/Roadmap-Dokument — hier zuerst lesen für Produktkontext |
| `background-dev-team-system-design.md` | Architektur des Work-Order-Systems |
| `background-dev-team-runbook.md` | Schritt-für-Schritt: Work Order → Runner → Result → Review |
| `background-dev-team-qa-checklist.md` | QA-Checkliste vor Freigabe des Runners |
| `runner-adapter-contract.md` | Interface-Vertrag für Runner-Adapter |
| `ai-usage-and-cost-audit.md` | Audit der AI-Kosten/-Nutzung |
| `manual-e2e-checklist.md` | Manuelle Browser-E2E-Checkliste |
| `saas-roadmap.md` (23.09.2026) | Aktive SaaS-Priorisierung (Stufen 1–4), ersetzt die alte v0.2/v0.3-Roadmap als Referenz |
| `background-operator-spike.md` | **Superseded** — nicht als aktuelles Design behandeln |

`docs/aufträge/` (eigener Unterordner, nicht in der Tabelle oben): Auftragsdokumente
für einzelne KI-Sessions — `JARVIS-A1` (Fundament/Findings, siehe Abschnitt "Jarvis"),
`JARVIS-Q1` (Qualitätsnetz, zehn Testfälle — **erledigt**: `backend/tests/
test_jarvis_quality.py` plus `.claude/skills/abnahme/SKILL.md`) und `JARVIS-C1`
(Command Layer — **erledigt**, siehe Abschnitt "Jarvis", Response-Vertrag).
Zusätzlich `JARVIS-D1` (Design-System-Durchgang) und `JARVIS-M1` (paralleler
Multi-Agent-Work-Order-Durchgang) — beide ohne eigenen Abschnitt in diesem
Dokument, im Ordner aber vorhanden.

## Bekannte Risiken

- **Behoben (23.09.2026), aber als schwerwiegendster bisheriger Fund
  festgehalten: kritischer Multi-Tenant-Datenleck über Jarvis.** Live mit
  einem echten zweiten Supabase-Testaccount reproduziert: dessen Jarvis-Chat
  bekam Serkans echten Outlook-Kalendertermin und mehrere seiner echten,
  teils sensiblen Notion-Aufgaben (Steuererklärung, Versicherungsschäden,
  ein medizinischer Befund) angezeigt. Ursache doppelt: `VAULT_OWNER_USER_ID`
  war trotz existierendem Gate-Code nie in `backend/.env` gesetzt (Gate
  faktisch aus), und für `google_calendar_service`/`outlook_calendar_service`/
  `notion_tasks_service` gab es **überhaupt kein** Eigentümer-Gate — ihre
  `get_context()`-Funktionen kennen gar keinen `user_id`-Parameter, es ist
  ein Composio-Account für den gesamten Prozess. Fix: neue
  `is_personal_integrations_owner()`-Prüfung (`app/core/config.py`),
  verdrahtet in `routers/jarvis.py` UND `routers/plans.py` vor allen drei
  externen Quellen; `VAULT_OWNER_USER_ID` jetzt real gesetzt. Live erneut
  mit demselben Testaccount verifiziert: Antwort enthält jetzt korrekt
  nichts mehr; Serkans eigener Zugriff weiterhin mit echten Daten bestätigt
  (keine Regression). Zwei neue Regressionstests in `test_jarvis_router.py`
  (`test_non_owner_never_gets_calendar_or_notion_context`, positiver Gegentest
  mit gepatchtem `is_personal_integrations_owner`). **Bleibt architektonisch
  Single-Tenant** — der Fix beschränkt auf den einen Eigentümer, macht daraus
  keine Pro-Nutzer-Integration; das ist weiterhin eine offene Entscheidung
  für echte eingeladene Tester (siehe `docs/saas-roadmap.md`).
- **Safety-Rules dreifach dupliziert**: `frontend/lib/safetyRules.ts` (nur Anzeige)
  vs. `backend/app/core/safety_rules.py` (echte Enforcement) vs. Runner-Prompt-Text
  — Drift-Risiko. Bei Änderungen an Approval-Scopes zuerst `safety_rules.py`
  ändern, dann synchronisieren.
- **Mock-Fallback-Risiko**: `frontend/lib/mockWorkOrders.ts` kann bei API-Fehlern
  still auf Mock-Daten zurückfallen und echte Fehler verdecken — nie ohne
  sichtbaren Fehlerzustand.
- **Runner-Pairing statt Browser-Token (23.09.2026) — jetzt live
  end-to-end verifiziert, nicht mehr nur getestet.**
  `supabase/migrations/017_runner_connections.sql` (gegen die Live-DB
  ausgeführt) + `app.auth._resolve_runner_token()` (akzeptiert einen
  `cprun_`-präfixierten Runner-Token transparent neben einem echten
  Supabase-JWT, gleiche `CurrentUser`-Form) + `scripts/
  run_work_order_daemon.py --pair` (Device-Flow) + Settings-UI "Runner
  verbinden" (`components/settings/RunnerConnections.tsx`). Ersetzt den
  vorherigen Refresh-Token-Workflow als empfohlenen Weg.
  **Live-Lauf fand 3 echte Bugs, alle gefixt**: (1) `.gitignore` fehlte
  `.cp_runner_token.json`; (2) `postgrest-py 2.30.0`s
  `maybe_single().execute()` gibt bei 0 Treffern bares `None` zurück statt
  eines Response-Objekts — traf `_find_pending_request`,
  `poll_pairing_status` UND `auth._resolve_runner_token`, alle drei
  crashten mit HTTP 500 statt sauberem 401/"abgelaufen" (ein abgelaufener
  Pairing-Code bzw. ein widerrufener Token reproduzierten das live); die
  In-Memory-Test-Fakes bildeten dieses Verhalten nicht nach, weshalb die
  Suite grün blieb — jetzt korrigiert, Tests von `assertRaises(Exception)`
  auf die konkrete `HTTPException(401)` verschärft; (3) Widerruf blockiert
  seither auch tatsächlich (vorher 500, jetzt 401), live mit einem echten
  gepaarten Token reproduziert. Details und der vollständige Testverlauf
  (inkl. eines real budget-limitierten `claude`-CLI-Laufs) in
  `docs/saas-roadmap.md`.
- **Fix (23.09.2026): `LifecycleControls.tsx` verschluckte jeden API-Fehler
  still.** Beide Handler (`handleClick`, `handleAutonomousStartClick`) hatten
  `try/finally` ohne `catch` — ein PATCH-Fehler (abgelaufene Session, 403,
  oder das fehlende `daemon_run_requested_at`-Schema ohne Migration 016)
  ließ den Button nur in den Ruhezustand zurückfallen, ohne dass der Nutzer
  je erfuhr, warum. Betraf JEDE Lifecycle-Aktion (Genehmigen/Abbrechen/Als
  laufend markieren/Autonom starten), nicht nur den Migrationsfall. Fix:
  sichtbare, schließbare Fehlerbox (`error`-State), live gegen die echte
  fehlende Migration 016 verifiziert (PGRST204 erscheint jetzt lesbar statt
  nur in der Browser-Konsole).
- **Neu (23.09.2026): `components/morning/PlanHistory.tsx`** — `GET
  /api/plans/me` existierte im Backend, wurde vom Frontend aber nie
  aufgerufen; frühere Tagespläne waren nur über eine bereits bekannte URL
  erreichbar. Gleiches Muster wie `CheckinHistory.tsx`s eigene Lücke (siehe
  deren Docstring), auf `/morning` unter dem Check-in-Formular eingehängt,
  jede Zeile verlinkt nach `/plans/[id]`. Live geprüft: reale Historie samt
  Navigation zu einem alten Plan funktioniert.
- **CLI-Runner-Pfad jetzt live gegen `claude` getestet (22.09.2026)**: `scripts/
  run_work_order.py --mode execute --adapter claude_code` lief mehrfach echt
  (reale, budget-gedeckelte Claude-Kosten, u.a. ein $1.40/24-Turn-Lauf) — dabei
  drei reale Bugs gefunden und gefixt: ein Windows-`shutil.which()`-Auflösungsfehler
  (`claude`-Shim führte zu stillem Hang), ein Budget-Gap zwischen
  `--max-budget-usd` und ungesetztem `approval_scope.max_cost_usd` (führte zum
  unbegrenzten $1.40-Charge, der den Fix motivierte) und ein False-Positive beim
  Trust-Dialog-Scan (schnitt einen echten, erfolgreichen Lauf ab, weil sein
  eigener Ergebnistext die Trust-Phrase zitierte). Siehe Kommentare in
  `scripts/runner_adapters/claude_code.py`. `--mode prompt-file` lief ebenfalls
  echt gegen eine laufende Work Order. Live-Progress/Stop (`ProgressReporter`,
  22.09.2026 ergänzt) wurde per echtem Browser-Test verifiziert: Stop-Button
  löst reale `running -> cancelled`-Transition aus, inkl. Activity-Log-Eintrag.
  **Weiterhin offen**: Supabase-Realtime-Cross-Tab-Sync (siehe nächster Punkt)
  und ein echter `--mode execute`-Lauf, der über den Stop-Button während eines
  laufenden `claude`-Subprozesses unterbrochen wird (bisher nur der reine
  Status-Transition-Pfad ohne aktiven Subprozess verifiziert).
- ~~Migration 015 (Supabase Realtime) nicht gegen das Live-Projekt ausgeführt~~ —
  **behoben (22.09.2026).** Ein erster Zwei-Tab-Test zeigte, dass ein `Stop`-Klick
  in Tab 1 nicht automatisch in Tab 2 ankam, weil `015_enable_realtime_work_orders.sql`
  noch nicht im Supabase SQL Editor ausgeführt war (Migrationen sind hier bewusst
  nie automatisiert). Serkan hat die Migration danach manuell ausgeführt; ein
  wiederholter Zwei-Tab-Test bestätigt: ein `Stop`-Klick in einem Tab propagiert
  jetzt ohne Reload in einen komplett unberührten zweiten Tab (`work_orders`-Status
  wechselt dort automatisch von `running` auf `cancelled`).
- **Per-Step-Ausführung (`--per-step`) + Sandbox-Adapter (`claude_code_sandboxed`,
  22.09.2026)**: echte Step-für-Step-Ausführung mit sofortigem Status-Write-back
  (`scripts/run_work_order.py::_run_step_by_step()`) und ein Docker-isolierter
  Autonomie-Modus (`scripts/runner_adapters/claude_code_sandboxed.py`), beide
  durch gemockte Tests abgedeckt (`scripts/test_step_execution.py`,
  `scripts/test_sandbox_adapter.py`, beide grün).
  **Sandbox-Adapter live gegen echtes Docker getestet (ohne `claude`-Aufruf,
  kein Geld ausgegeben)** — dabei zwei reale Bugs gefunden und gefixt:
  1. `git worktree add` (ursprünglicher Ansatz) erzeugt eine `.git`-DATEI mit
     absolutem Windows-Hostpfad zurück zum Hauptrepo — im Linux-Container
     nicht auflösbar, jedes `git`-Kommando DES AGENTEN im Container schlägt
     fehl ("not a git repository"), obwohl die Dateien sichtbar/editierbar
     sind. Fix: `git clone --local` statt `git worktree add` — eigenständiges
     `.git`-Verzeichnis, kein Hostpfad-Bezug, funktioniert identisch im
     Container. `_extract_diff()` (läuft immer auf dem Host, nie im
     Container) war davon nie betroffen.
  2. `shutil.rmtree(..., ignore_errors=True)` beim Cleanup gab bei
     schreibgeschützten Git-Objektdateien (Windows markiert Git-Pack-/Object-
     Dateien read-only) still auf und ließ das Sandbox-Verzeichnis
     zurück — genau das "verwaiste Sandbox-Verzeichnis"-Risiko, vor dem der
     Modul-Docstring warnt. Fix: `onexc`-Hook, der die Read-only-Flag löscht
     und den Löschversuch wiederholt — live verifiziert, dass danach
     wirklich nichts mehr übrig bleibt.
  **Bekannte, live verifizierte Einschränkung (CRLF)**: `_extract_diff()`s
  eigener Diff ist nachweislich sauber (läuft immer mit dem Host-Git gegen
  den Host-Checkout). Führt der Agent aber selbst `git status`/`git diff`
  IM Container aus, sieht er jede getrackte Datei als "modifiziert" mit
  symmetrischer +/− Zeilenzahl — echte CRLF/LF-Normalisierungs-Drift
  zwischen Windows-Host-Git (Checkout) und Linux-Container-Git (keine
  Konvertierung konfiguriert). Harmlos fürs eigentliche Ergebnis (der
  extrahierte Diff), aber potenziell verwirrend für den Agenten selbst —
  nicht gefixt in diesem Durchgang, siehe Adapter-Docstring.
  `scripts/sandbox/Dockerfile` baut lokal erfolgreich und wurde real
  hochgefahren (Node v20.20.2, Python 3.11.2, git 2.39.5, `claude` CLI
  2.1.197 — alle vier Versionen live per `docker run` bestätigt, nicht nur
  build-erfolgreich). **In der UI verdrahtet (`frontend/components/operator/
  LocalRunnerPanel.tsx`)**: ein "Step-für-Step-Ausführung"-Toggle (hängt
  `--per-step` an beide Befehle) und ein eigener Command-Block "4c" für
  `claude_code_sandboxed` (Docker-Hinweis-Box) — vorher nur per CLI-Flag
  erreichbar, jetzt aus dem Operator-UI kopierbar, exakt wie die
  bestehenden Runner-Befehle.
  **Weiterhin offen (braucht echtes Geld/Token, nicht in diesem Durchgang
  gemacht)**: ein echter `--per-step`-Lauf gegen die reale `claude`-CLI
  (braucht `COMMANDPILOT_API_TOKEN`), und ein echter `claude_code_sandboxed`-
  Lauf, der `claude` tatsächlich im Container aufruft (bisher nur die
  Container-Mechanik selbst — Mount, Git, Cleanup — ohne echten `claude`-
  Aufruf verifiziert). Siehe `docs/manual-e2e-checklist.md`.
- **Autonomer Trigger-Daemon (`scripts/run_work_order_daemon.py`, 22.09.2026)
  — unit-getestet (14 Tests, `scripts/test_run_work_order_daemon.py`), UI-Pfad
  live verifiziert, Daemon selbst noch nicht live gelaufen**: der "Autonom
  starten"-Button (`LifecycleControls.tsx`, Status `queued`) wurde live im
  Browser bestätigt — Bestätigungsdialog korrekt, PATCH feuert korrekt (nach
  einem nötigen Backend-Neustart, der stale liefen Code hatte), Fehlerfall
  sauber abgefangen (kein Crash). Der eigentliche Fehler beim Testen war
  erwartbar und kein Bug: `Could not find the 'daemon_run_requested_at'
  column ... in the schema cache` (PGRST204) — **Migration 016 wurde noch
  nicht gegen das Live-Projekt ausgeführt** (wie jede Migration hier bewusst
  nie automatisiert). Der Daemon-Prozess selbst (`run_work_order_daemon.py`)
  wurde bisher nur gegen gemockte `call_api()`/`subprocess.run()`-Aufrufe
  getestet, nicht live gegen einen echten laufenden Backend + eine echte
  Work Order durchgeklickt. **Vor erstem echten Einsatz**: Migration 016 im
  Supabase SQL Editor ausführen, dann Daemon lokal starten, "Autonom
  starten" klicken, beobachten dass er den Auftrag abholt und
  `run_work_order.py` wirklich anstößt (siehe
  `docs/background-dev-team-runbook.md` § Autonomer Daemon).
  **Fix (23.09.2026, gefunden bei Code-Review vor dem ersten Live-Lauf, noch
  ohne Migration/Geld möglich)**: `--adapter` defaultete auf `manual_prompt`,
  das `supports_auto_execute="no"` hat — ein ohne explizites `--adapter
  claude_code`/`claude_code_sandboxed` gestarteter Daemon hätte jede
  angefragte Work Order stillschweigend verschluckt: `claim()` löscht
  `daemon_run_requested_at`, danach lehnt `run_work_order.py`s eigener
  Execute-Guard `manual_prompt` ab, bevor auch nur ein `agent_run`- oder
  `activity_log`-Eintrag entsteht — die Work Order fällt zurück auf
  `queued`, der "Autonom starten"-Button erscheint einfach wieder, ohne
  Erklärung. `main()` prüft jetzt `get_adapter(args.adapter).info
  .supports_auto_execute` vor dem ersten Poll und bricht mit klarer
  Fehlermeldung ab, wenn der Adapter `"no"` ist — drei neue Tests in
  `scripts/test_run_work_order_daemon.py::MainAdapterValidationTests`.
- **`openai`-Sprung 1.54.4 → 3.17.0 (22.09.2026), erzwungen durch `composio`**:
  `import composio` zieht unconditional `composio.core.provider._openai` und
  damit ein reales `openai>=2.48.0` — es gibt keine Möglichkeit, das SDK zu
  nutzen ohne diesen Sprung mitzunehmen. Volle Pytest-Suite ist grün, und die
  von `ai_service.py` genutzte Fläche (`AsyncOpenAI`, `chat.completions.create`,
  `response_format: json_schema`-Dict-Form, die vier Exception-Klassen) ist laut
  offiziellem Changelog vom bekannten 2.0.0-Breaking-Change (Responses-API
  `output`-Typing) nicht betroffen — aber kein Test in diesem Repo ruft die
  echte OpenAI-API auf.
  **Jarvis-Chat: live verifiziert (23.09.2026)** — echte Anfrage über
  `/api/jarvis/chat` gegen die echte OpenAI-API durchgeklickt (`gpt-4o` via
  `AsyncOpenAI`, `response_format: json_schema`), Antwort kam strukturiert
  und korrekt zurück, alle vier Kontextquellen (Vault, Google/Outlook-
  Kalender, Notion, Work Orders) live befüllt — der `openai`-Sprung selbst
  ist also nicht das Problem. Dabei aber ein echter, unabhängiger Bug
  gefunden und gefixt: siehe Jarvis-Abschnitt oben, "HEUTIGES DATUM"-Fix.
  **Tagesplan: nur Rendering eines bestehenden Plans live geprüft, keine
  frische Generierung** — für 23.09.2026 existierte bereits ein Plan, ein
  echter Generierungslauf (der den `openai`-Aufrufpfad tatsächlich neu
  auslöst) steht noch aus.
- Details und vollständige Risikoliste: siehe
  `docs/commandpilot-current-state-and-business-roadmap.md`.

---

Pfad-spezifische Detailregeln: `.claude/rules/frontend.md`,
`.claude/rules/backend.md`, `.claude/rules/database.md`.
