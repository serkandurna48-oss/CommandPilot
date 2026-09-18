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

**Zwei Module, beide vollständig in `main`:**

1. **Daily Planner** — der stabile Kern (Check-ins, AI-Pläne, Reviews, Rules,
   Projects).
2. **Operator Control Plane / "Background Dev Team"** — Work-Order-gesteuerte
   Ausführung von Coding-Agents über lokale Runner-Adapter.

Seit dem 18.09.2026 gibt es genau einen Trunk: `feat/operator-control-plane` wurde
per Fast-Forward nach `main` gemerged und gepusht. Es gibt keine Branch-Gates mehr
("nur auf …") — alles unten Beschriebene existiert in jedem `main`-Checkout.

---

## System-Kontext

CommandPilot ist der Kern eines Systems aus drei Repos:

- **CommandPilot** (dieses Repo) — Daily Planner + Operator Control Plane.
- **secondbrain** — ein Obsidian-Vault mit dauerhaftem qualitativem Wissen über
  den Nutzer: Ziele, Projekte, Menschen, Entscheidungen, Gesundheit, Tools.
  Vertrag laut dessen eigener CLAUDE.md: **CommandPilot liest das Vault als
  Kontextquelle, niemals umgekehrt.**
- **CampPilot / Sommercamps** — eigenständiges Kundenprodukt, kein Teil von
  Jarvis, aber der erste echte Auftraggeber für Operator-Automatisierung.

Source of Truth bleibt außerhalb dieses Systems: Notion (Aufgaben, Status),
GitHub (Code), Google Calendar (Termine), Mail (Korrespondenz). Nichts davon
wird gespiegelt, nur referenziert.

## Produktrichtung

Reihenfolge ist bindend — nicht vorgreifen, nicht überspringen:

1. Text-Chat mit Second-Brain-Kontext und Quellenangaben
2. Aktionssystem mit Vorschau und expliziter Bestätigung
3. gemeinsames Dashboard
4. Spracheingabe/-ausgabe auf denselben Assistenten
5. Integrationen (Notion, Kalender, GitHub, Mail) und proaktive Automationen
6. Hintergrundagenten innerhalb der bestehenden Safety Rules

**Architekturprinzip:** Oberflächen sind austauschbar, Tools und Retrieval sind
das Vermögen. Retrieval- und Kernlogik dürfen keine Oberfläche kennen — Chat,
Sprache und Dashboard rufen dieselben Funktionen auf. Wer das bricht, baut
zweimal.

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
# Voller lokaler Dev-Start (öffnet 2 Fenster)
./start-dev.ps1
# Backend: <repo>\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 (aus backend/)
# Frontend: npm run dev (aus frontend/)

# Frontend einzeln
cd frontend
npm run dev          # Dev-Server
npm run build         # Production-Build
npm run lint          # ESLint (next lint)
npm run type-check    # tsc --noEmit

# Backend-Tests
cd backend
pip install -r requirements-dev.txt   # zieht pytest==8.3.4
python -m pytest tests/               # backend/tests/ — pytest-Suite
```

- **Kein Test-Framework im Frontend konfiguriert** (kein Jest/Vitest) — nichts erfinden.
- **Kein Lint/Format-Tool im Backend** (kein ruff/black) — nichts erfinden.
- Backend hat seit Kurzem eine **pytest-Suite unter `backend/tests/`**
  (`test_work_order_transitions.py`, `test_result_import_idempotency.py`) —
  stdlib-only (`unittest`/`unittest.mock`), aber pytest-discoverbar; dafür
  existiert `backend/requirements-dev.txt`. Diese Tests faken den
  Supabase-Client komplett — sie ersetzen keine manuelle Prüfung gegen ein
  echtes Supabase-Projekt.
- `scripts/test_*.py` (`test_agent_run_session.py`, `test_bounded_retry.py`,
  `test_import_result_integrity.py`) sind weiterhin manuelle
  Standalone-Skripte der Runner-Harness (`python scripts/test_*.py`), bewusst
  getrennt von der pytest-Suite in `backend/tests/`.
- Messlatte vor jedem Merge: `npm run lint && npm run type-check` (Frontend) +
  `python -m pytest tests/` (Backend) + manuelle Endpoint-Prüfung.

## Projektstruktur

```
frontend/
  app/            # dashboard, login, signup, morning, plans/[id], review, rules,
                  # settings, projects, operator/, operator/new, operator/[id]
  components/     # dashboard, layout, morning, plans, projects, review, rules, ui,
                  # operator/*
  lib/            # api.ts, auth.tsx, i18n.ts, supabase.ts, utils.ts,
                  # generateRunnerPrompt.ts, workOrderMapper.ts, mockWorkOrders.ts,
                  # safetyRules.ts, operatorStyles.ts

backend/app/
  routers/        # auth, health, checkins, plans, projects, reviews, rules,
                  # work_orders
  services/       # ai_service, checkin_service, plan_service, project_service,
                  # review_service, usage_service, work_order_service
  models/         # checkin, plan, project, review, rules, work_order
  core/           # config.py, safety_rules.py
  prompts/        # daily_plan.py — isolierte AI-Prompt-Konstruktion
  db/             # client.py — Supabase-Client-Singleton
backend/tests/    # pytest-Suite (siehe "Wichtige Befehle")

supabase/
  schema.sql
  migrations/     # 001–012, fortlaufend

scripts/          # Lokale Runner-Harness (run_work_order.py,
                  # import_work_order_result.py, runner_adapters/*, test_*.py)

docs/             # siehe "Docs-Index" unten
```

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

- `supabase/migrations/NNN_beschreibung.sql`, sequenziell nummeriert (aktuell
  001–012), manuell in der Supabase SQL Editor ausgeführt.
- Standard: idempotent (`IF NOT EXISTS`-Guards). Bekannte Ausnahmen:
  `004_ai_usage_log.sql` und `006_work_orders.sql` (`CREATE POLICY` ohne Guard,
  pre-PG15) — beide nur einmal ausführen.
- Detaillierte Regeln (RLS-Pattern, README-Sync-Pflicht): siehe README.md
  (`.claude/rules/database.md` existiert in diesem Checkout nicht).

## Python-Environment (venv)

Auf der Entwicklungsmaschine können bis zu drei lokale venvs existieren (alle
gitignored, kein Leak-Risiko): Root `venv/` (veraltet/Altlast, nicht verwenden),
Root **`.venv/`** (**kanonisch** — wird tatsächlich von `start-dev.ps1` für den
Uvicorn-Start genutzt), `backend/venv/` (redundant, entsteht durch README's manuelle
Setup-Anleitung). Bei Dependency-/Import-Problemen zuerst gegen Root-`.venv` prüfen.
Kein automatisches Löschen der anderen ohne explizite Anweisung.

## Git-/Branch-Regeln

- **`main` ist der einzige Trunk** und enthält Daily Planner + Operator Control
  Plane vollständig. `feat/operator-control-plane` wurde am 18.09.2026 per
  Fast-Forward gemergt und gepusht.
- Es existiert daneben ein alter, **nicht gemergter** Branch
  `origin/chore/commandpilot-ai-setup` (zweigt vor dem Operator-Control-Plane-
  Merge ab). Er enthält eine ältere Fassung dieser Datei sowie
  `.claude/agents/*.md`, `.claude/rules/*.md` und `AGENTS.md` — keines davon
  ist aktuell in `main`. Vor einer Übernahme dieser Dateien nach `main`
  gegen den jetzigen Stand prüfen, nicht blind mergen.
- Dieses Repo wird häufig in mehreren Git-Worktrees parallel ausgecheckt — vor
  Annahmen über vorhandene Dateien `git worktree list` prüfen.
- Nie ungefragt mergen, rebasen oder pushen. Ein Thema, ein Commit. Nichts committen
  ohne Bestätigung des Entwicklers.

## Test-/Review-Regeln

- Backend hat eine kleine pytest-Suite (`backend/tests/`, siehe "Wichtige
  Befehle") plus manuelle Standalone-Skripte (`scripts/test_*.py`). Frontend
  hat weiterhin keinen automatisierten Test-Stand.
- Vor einem Merge: `npm run lint && npm run type-check` + `python -m pytest
  tests/` (Backend) + manuelle Prüfung der Kernflows.
- Die frühere Doku verwies hier auf zwei Subagents
  (`commandpilot-regression-check`, `architecture-consistency-check`) unter
  `.claude/agents/`. Diese existieren in diesem `main`-Checkout **nicht** —
  sie liegen nur auf dem unmerged Branch `chore/commandpilot-ai-setup` (siehe
  "Git-/Branch-Regeln"). Nicht referenzieren, bis geklärt ist, ob sie
  übernommen werden.

## Docs-Index

`docs/` existiert in `main`:

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

## Bekannte Risiken

- **Safety-Rules dreifach dupliziert**: `frontend/lib/safetyRules.ts` (nur
  Anzeige) vs. `backend/app/core/safety_rules.py` (echte Enforcement) vs.
  Runner-Prompt-Text — Drift-Risiko. Bei Änderungen an Approval-Scopes zuerst
  `safety_rules.py` ändern, dann synchronisieren.
- **Mock-Fallback-Risiko**: `frontend/lib/mockWorkOrders.ts` kann bei
  API-Fehlern still auf Mock-Daten zurückfallen und echte Fehler verdecken —
  nie ohne sichtbaren Fehlerzustand.
- Details und vollständige Risikoliste: siehe
  `docs/commandpilot-current-state-and-business-roadmap.md`.
