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
6. Integrationen.
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
  den Antworttext zu schreiben (das übernimmt die UI separat).

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
`test_jarvis_chat_prompt.py` — vier Dateien, pytest-discoverbar, laufen über
`scripts/check.ps1` mit.

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
| AI | OpenAI GPT-4o, JSON-Mode | openai==1.54.4 |

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
                  # review_service, usage_service, work_order_service, vault_service
  app/models/     # checkin, plan, project, review, rules, work_order, jarvis
  app/core/       # config.py, safety_rules.py
  app/prompts/    # daily_plan.py, jarvis_chat.py — isolierte AI-Prompt-Konstruktion
  app/db/         # client.py — Supabase-Client-Singleton
  tests/          # pytest-Suite, 6 Dateien: test_work_order_transitions.py,
                  # test_result_import_idempotency.py, test_vault_service.py,
                  # test_daily_plan_vault_context.py, test_jarvis_router.py,
                  # test_jarvis_chat_prompt.py
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
- `chore/commandpilot-ai-setup` ist als eigener Worktree unter
  `Projekte/commandpilot-ai-setup` ausgecheckt — Quelle für `.claude/`, `AGENTS.md`,
  `CLAUDE.md` (dieses Dokument), bis diese Dateien vollständig auf `main` gepflegt
  werden.
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
| `STATUS.md` | Laufende Befunde aus Live-Läufen (chronologisch, neueste zuerst) — kein Soll-Zustand, siehe Datei selbst |
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
- **CLI-Runner-Pfad nicht live gegen `claude` getestet**: `scripts/run_work_order.py
  --mode execute --adapter claude_code` (echter Subprocess, echtes Budget-Limit)
  wurde bisher nur über Unit-Tests mit gefaktem Adapter verifiziert
  (`scripts/test_bounded_retry.py`), nicht als echter CLI-Lauf mit einem
  User-Bearer-Token — siehe `docs/manual-e2e-checklist.md`, Abschnitt
  "Verifizierungsstatus".
- Details und vollständige Risikoliste: siehe
  `docs/commandpilot-current-state-and-business-roadmap.md`.

---

Pfad-spezifische Detailregeln: `.claude/rules/frontend.md`,
`.claude/rules/backend.md`, `.claude/rules/database.md`.
