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
3. **Nächster Schritt** — Aktionen mit Vorschau und Bestätigung — nichts wird
   ausgeführt, ohne dass der Mensch vorher sieht, was passieren würde. Siehe
   `docs/aufträge/JARVIS-C1 — Command Layer, der nächste sichtbare Ablauf.md`.
4. Dashboard.
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

**Eigentümer-Bindung**: `VAULT_OWNER_USER_ID` (Env-Var, optional). Gesetzt
und `user_id` des Requests stimmt nicht überein → leerer Kontext, Logeintrag,
kein Dateisystemzugriff. Leer/ungesetzt (Default) → kein Gate. Kein
Pro-Nutzer-Vault-System — ein Vault, ein Eigentümer, keine Migration.

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
`suggested_actions: list[SuggestedAction]`, in v1 IMMER leer. `SuggestedAction`
ist an `work_order.py`s Feldern ausgerichtet (`title`, `team_type`,
`target_repo_name`, `risk`, `requires_approval`, `sources`) — Vorbereitung
für Produktrichtung Schritt 3 (Command Layer,
`docs/aufträge/JARVIS-C1 — Command Layer, der nächste sichtbare Ablauf.md`),
noch nicht implementiert. Kein Auto-Ausführen von Aktionen aus dem Chat.

**Tests**: `backend/tests/test_vault_service.py`,
`test_daily_plan_vault_context.py`, `test_jarvis_router.py`,
`test_jarvis_chat_prompt.py`, plus (22.09.2026) `test_google_calendar_service.py`,
`test_outlook_calendar_service.py` und `test_notion_tasks_service.py` — alle
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
- Backend hat eine echte pytest-Suite: `backend/tests/` (6 Dateien, davon 4
  Jarvis-bezogen — siehe Abschnitt "Jarvis" —, Setup über
  `backend/requirements-dev.txt`). `scripts/test_*.py` bleiben separate,
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
  migrations/     # 001-012, sequenziell, alle auf main

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
  Supabase SQL Editor ausgeführt. Aktueller Stand: 001–012, alle auf `main`.
- Standard: idempotent (`IF NOT EXISTS`-Guards). Bekannte Ausnahmen:
  `004_ai_usage_log.sql` und `006_work_orders.sql` (beide CREATE POLICY ohne Guard)
  — beide nur einmal ausführen.
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
  `backend/tests/` (pytest, 6 Dateien) deckt Operator-Control-Plane-Kernmechanik
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
| `background-operator-spike.md` | **Superseded** — nicht als aktuelles Design behandeln |

`docs/aufträge/` (eigener Unterordner, nicht in der Tabelle oben): Auftragsdokumente
für einzelne KI-Sessions — `JARVIS-A1` (Fundament/Findings, siehe Abschnitt "Jarvis"),
`JARVIS-Q1` (Qualitätsnetz, zehn Testfälle) und `JARVIS-C1` (Command Layer). Q1 und C1
sind zum Zeitpunkt dieses CLAUDE.md-Updates noch nicht bearbeitet.

## Bekannte Risiken

- **Safety-Rules dreifach dupliziert**: `frontend/lib/safetyRules.ts` (nur Anzeige)
  vs. `backend/app/core/safety_rules.py` (echte Enforcement) vs. Runner-Prompt-Text
  — Drift-Risiko. Bei Änderungen an Approval-Scopes zuerst `safety_rules.py`
  ändern, dann synchronisieren.
- **Mock-Fallback-Risiko**: `frontend/lib/mockWorkOrders.ts` kann bei API-Fehlern
  still auf Mock-Daten zurückfallen und echte Fehler verdecken — nie ohne
  sichtbaren Fehlerzustand.
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
- **`openai`-Sprung 1.54.4 → 3.17.0 (22.09.2026), erzwungen durch `composio`**:
  `import composio` zieht unconditional `composio.core.provider._openai` und
  damit ein reales `openai>=2.48.0` — es gibt keine Möglichkeit, das SDK zu
  nutzen ohne diesen Sprung mitzunehmen. Volle Pytest-Suite ist grün, und die
  von `ai_service.py` genutzte Fläche (`AsyncOpenAI`, `chat.completions.create`,
  `response_format: json_schema`-Dict-Form, die vier Exception-Klassen) ist laut
  offiziellem Changelog vom bekannten 2.0.0-Breaking-Change (Responses-API
  `output`-Typing) nicht betroffen — aber kein Test in diesem Repo ruft die
  echte OpenAI-API auf. Vor dem nächsten Merge einmal Tagesplan **und**
  Jarvis-Chat live im Browser gegen die echte OpenAI-API durchklicken, nicht
  nur `scripts/check.ps1` vertrauen.
- Details und vollständige Risikoliste: siehe
  `docs/commandpilot-current-state-and-business-roadmap.md`.

---

Pfad-spezifische Detailregeln: `.claude/rules/frontend.md`,
`.claude/rules/backend.md`, `.claude/rules/database.md`.
