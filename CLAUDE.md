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

**Zwei Module:**

1. **Daily Planner** — der stabile Kern (Check-ins, AI-Pläne, Reviews, Rules,
   Projects). Immer vorhanden, unabhängig von Branch/Checkout.
2. **Operator Control Plane / "Background Dev Team"** — Work-Order-gesteuerte
   Ausführung von Coding-Agents über lokale Runner-Adapter. **Existiert nur auf dem
   Branch `feat/operator-control-plane` (bereits gepusht, noch nicht in `main`
   gemerged).** Prüfsatz statt Datumsangabe: *Falls `backend/app/routers/work_orders.py`
   in deinem Checkout existiert, ist der Merge erfolgt — behandle alle
   "[nur auf feat/operator-control-plane]"-Markierungen unten dann als hinfällig.*

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
# Backend: <repo>\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000 (aus backend/)
# Frontend: npm run dev (aus frontend/)

# Frontend einzeln
cd frontend
npm run dev          # Dev-Server
npm run build         # Production-Build
npm run lint          # ESLint (next lint)
npm run type-check    # tsc --noEmit
```

- **Kein Test-Framework im Frontend konfiguriert** (kein Jest/Vitest) — nichts erfinden.
- **Kein Lint/Format-Tool im Backend** (kein ruff/black) — nichts erfinden.
- Backend hat **keine pytest-Suite**. `scripts/test_*.py` (nur auf
  `feat/operator-control-plane`) sind manuelle Standalone-Skripte, nicht
  pytest-discoverbar.
- Aktuelle Messlatte vor jedem Merge: `npm run lint && npm run type-check`
  (Frontend) + manuelle Endpoint-Prüfung (Backend) + die beiden Subagents unten.

## Projektstruktur

```
frontend/
  app/            # dashboard, login, signup, morning, plans/[id], review, rules,
                  # settings, projects
                  # + operator/, operator/new, operator/[id]  [nur auf feat/operator-control-plane]
  components/     # dashboard, layout, morning, plans, projects, review, rules, ui
                  # + components/operator/*  [nur auf feat/operator-control-plane]
  lib/            # api.ts, auth.tsx, i18n.ts, supabase.ts, utils.ts
                  # + generateRunnerPrompt.ts, workOrderMapper.ts, mockWorkOrders.ts,
                  #   safetyRules.ts, operatorStyles.ts  [nur auf feat/operator-control-plane]

backend/app/
  routers/        # auth, health, checkins, plans, projects, reviews, rules
                  # + work_orders.py  [nur auf feat/operator-control-plane]
  services/       # ai_service, checkin_service, plan_service, project_service,
                  # review_service, usage_service
                  # + work_order_service.py  [nur auf feat/operator-control-plane]
  models/         # checkin, plan, project, review, rules
                  # + work_order.py  [nur auf feat/operator-control-plane]
  core/           # config.py
                  # + safety_rules.py  [nur auf feat/operator-control-plane]
  prompts/        # daily_plan.py — isolierte AI-Prompt-Konstruktion
  db/             # client.py — Supabase-Client-Singleton

supabase/
  schema.sql
  migrations/     # 001-005 immer vorhanden; 006-009 nur auf feat/operator-control-plane

scripts/          # Lokale Runner-Harness (run_work_order.py, import_work_order_result.py,
                  # runner_adapters/*)  — existiert NUR auf feat/operator-control-plane

docs/             # existiert NUR auf feat/operator-control-plane, siehe "Docs-Index" unten
```

Vor jeder Annahme über einen Pfad oben: prüfen, ob er im aktuellen Checkout wirklich
existiert (`git worktree list` / `git branch -vv`) — dieses Dokument ist bewusst so
geschrieben, dass es auf beiden Branches korrekt bleibt.

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
  Supabase SQL Editor ausgeführt.
- Standard: idempotent (`IF NOT EXISTS`-Guards). Bekannte Ausnahmen:
  `004_ai_usage_log.sql` (CREATE POLICY ohne Guard) und `006_work_orders.sql`
  (gleiche Einschränkung, nur auf `feat/operator-control-plane`) — beide nur einmal
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

- `main` = nur Daily Planner. `feat/operator-control-plane` = Daily Planner +
  Operator Control Plane (8 Commits, bereits gepusht, noch nicht gemerged).
- Dieses Repo wird häufig in mehreren Git-Worktrees parallel ausgecheckt — vor
  Annahmen über vorhandene Dateien `git worktree list` prüfen.
- Nie ungefragt mergen, rebasen oder pushen. Ein Thema, ein Commit. Nichts committen
  ohne Bestätigung des Entwicklers.

## Test-/Review-Regeln

- Kein automatisierter Test-Stand vorhanden (siehe "Wichtige Befehle"). Vor einem
  Merge: `npm run lint && npm run type-check` + manuelle Prüfung der Kernflows.
- Für tiefere Prüfungen die beiden Subagents nutzen:
  - `commandpilot-regression-check` — Code-vs-Code (Interfaces, Schichtung, Auth,
    Migrationen, Kernflows).
  - `architecture-consistency-check` — Doku-vs-Code (README/docs vs. echte
    Struktur, Mock-Fallback-Risiken, veraltete Annahmen).

## Docs-Index

Existieren **nur auf `feat/operator-control-plane`** (kein `docs/`-Ordner auf `main`):

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

- **Safety-Rules dreifach dupliziert** [nur auf feat/operator-control-plane]:
  `frontend/lib/safetyRules.ts` (nur Anzeige) vs. `backend/app/core/safety_rules.py`
  (echte Enforcement) vs. Runner-Prompt-Text — Drift-Risiko. Bei Änderungen an
  Approval-Scopes zuerst `safety_rules.py` ändern, dann synchronisieren.
- **Mock-Fallback-Risiko** [nur auf feat/operator-control-plane]:
  `frontend/lib/mockWorkOrders.ts` kann bei API-Fehlern still auf Mock-Daten
  zurückfallen und echte Fehler verdecken — nie ohne sichtbaren Fehlerzustand.
- Details und vollständige Risikoliste: siehe
  `docs/commandpilot-current-state-and-business-roadmap.md`.

---

Pfad-spezifische Detailregeln: `.claude/rules/frontend.md`,
`.claude/rules/backend.md`, `.claude/rules/database.md`.
