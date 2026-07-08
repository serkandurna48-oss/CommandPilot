# CommandPilot Current State and Business Roadmap

Datum: 2026-07-07  
Review-Typ: Product, Architecture, Safety, Business Roadmap  
Scope: rein lesender Repo-Review plus neue Markdown-Auswertung. Keine Deployments, keine Production-Daten, keine Secrets, keine `.env`-Dateien.

## Executive Summary

### 5 wichtigste Erkenntnisse

| # | Erkenntnis | Bedeutung |
|---|---|---|
| 1 | CommandPilot ist nicht mehr nur ein Daily Planner. | Das Repo enthaelt inzwischen ein echtes Control-Plane-Modell fuer Work Orders, Approval Scopes, Steps, Activity Logs, Artifacts und Review Packages. |
| 2 | Der Daily Planner ist das stabilste nutzbare Modul. | Auth, Check-ins, AI-Planerzeugung, Reviews, Regeln, Projekte als Kontext und AI-Kostenlogging sind vorhanden. |
| 3 | Das Background Dev Team ist ein lokaler, human-invoked Runner-Workflow, kein autonomer Cloud-Worker. | `manual_prompt` und `run_work_order.py` sind nutzbar; `claude_code` ist semi-automatisch; Codex/OpenClaw sind Platzhalter. |
| 4 | Das Sicherheitsmodell ist konzeptionell stark, aber technisch nur teilweise erzwungen. | Scope-Validatoren und Claude-Code-Tool-Mapping helfen, ersetzen aber keine Sandbox, keine echte Policy Engine und keine Laufzeit-Isolation. |
| 5 | Die Produktchance liegt im Execution OS fuer Einzelgruender/Operator, nicht in einem generischen Planner. | Der groesste Hebel ist: Serkan nutzt CommandPilot taeglich fuer reale Arbeit, danach private Beta fuer aehnliche Solo-Builder. |

### 5 groesste Risiken

| # | Risiko | Einstufung |
|---|---|---|
| 1 | Runner-Sicherheit ist noch nicht hart genug fuer unbeaufsichtigte Ausfuehrung. | Safety Critical |
| 2 | API-Fallback auf Mock-Daten kann echte Fehler verdecken. | Must Fix / Safety Critical |
| 3 | Migrationen muessen manuell laufen; Live-Zustand ist aus dem Repo nicht beweisbar. | Must Fix |
| 4 | Projects ist noch kein echtes Project Command Center. | Revenue Enabler |
| 5 | Produktnarrativ, Pricing und Beta-Onboarding sind noch nicht definiert. | Revenue Enabler |

### 5 naechste Schritte

| # | Schritt | Ziel |
|---|---|---|
| 1 | Lokalen Ist-Zustand stabilisieren: Migrationsstatus, API-Smoke, UI-Fallback-Kennzeichnung, Docs aktualisieren. | Keine Scheinstabilitaet. |
| 2 | Serkan-internen Daily Workflow definieren und 7 Tage benutzen. | Reale Nutzungsdaten statt Roadmap-Annahmen. |
| 3 | Einen kleinen echten Work Order Loop mehrfach durchlaufen. | Work Order -> Runner -> Result -> Review validieren. |
| 4 | Claude Code Adapter und Result Validation haerten. | Produktive interne Nutzung ohne Blindflug. |
| 5 | Private-Beta-Angebot formulieren: "Personal Execution OS for solo builders". | Erste zahlbare Richtung testen. |

## Quellenlage und Unsicherheiten

### Gelesene Dateien

| Bereich | Dateien |
|---|---|
| Strategie / Docs | `README.md`, `docs/background-operator-spike.md`, `docs/background-dev-team-system-design.md`, `docs/background-dev-team-runbook.md`, `docs/background-dev-team-qa-checklist.md`, `docs/runner-adapter-contract.md` |
| Migrations / Schema | `supabase/schema.sql`, `supabase/migrations/001_profiles_language_check.sql`, `002_daily_plans_review_context_used.sql`, `003_daily_plans_unique_constraint.sql`, `004_ai_usage_log.sql`, `005_projects_extend.sql`, `006_work_orders.sql`, `007_work_order_steps.sql`, `008_work_orders_team_type.sql` |
| Backend | `backend/app/main.py`, `auth.py`, `core/config.py`, `core/safety_rules.py`, `models/*`, `routers/*`, `services/*`, `prompts/daily_plan.py` |
| Frontend | `frontend/app/*`, `components/dashboard/*`, `components/morning/*`, `components/plans/*`, `components/projects/*`, `components/operator/*`, `components/review/*`, `components/rules/*`, `lib/api.ts`, `lib/auth.tsx`, `lib/i18n.ts`, `lib/workOrderMapper.ts`, `lib/generateRunnerPrompt.ts`, `lib/safetyRules.ts`, `types/index.ts` |
| Runner | `scripts/run_work_order.py`, `scripts/import_work_order_result.py`, `scripts/runner_adapters/*` |

### Nicht vollstaendig auswertbar

| Quelle | Status |
|---|---|
| `plan/CampsPilot-Roadmap-v0.2-v0.3.pdf` | Datei vorhanden, aber lokal nicht zuverlaessig als Text extrahierbar. `pdftotext`, `pypdf`, `PyPDF2` waren nicht verfuegbar. Byte-Suche lieferte keine verwertbare Struktur. |
| `plan/CommandPilot_KI_Zusammenarbeit.pdf` | Datei vorhanden, ebenfalls nicht zuverlaessig extrahierbar. |
| Live-Supabase-Stand | Nicht geprueft. Keine Production-Daten gelesen. Repo zeigt Migrations, aber nicht ob sie live angewendet wurden. |

Alle Aussagen zum "alten Plan" basieren daher auf den Markdown-Dokumenten, README, Migrationsnamen und Codezustand. PDF-Inhalte werden nicht erfunden.

## 1. Alter Plan vs. aktueller Ist-Zustand

### Urspruengliche Richtung

| Planstand | Vermuteter Scope aus Repo-Dokumenten | Status heute |
|---|---|---|
| Initial / v0.1 | AI Morning Command Center: Check-in, AI Daily Plan, Rules, Evening Review, Auth, Supabase Persistenz. | Weitgehend gebaut. |
| v0.2 / Stability Sprint | Stabilisierung, Auth/Workspace, i18n, mobile Navigation, AI-Fehlerhandling, Plan-Duplikate, AI Usage Cap. | Gebaut und im README dokumentiert. |
| v0.3 / Project-Erweiterung | Projects als leichter Backlog und Kontext fuer Daily Plan. | Gebaut, aber eher Kontextliste als Command Center. |
| Background Operator Spike | Mock-only Operator / Second Brain, Work-Order-Modell als Vorschlag, keine DB. | Ueberholt durch echte Work-Order-Persistenz und Runner-Skripte. |
| Background Dev Team | Persistierter Control Plane, Runner Prompt, Import Bridge, Local Runner, Adapter Contract. | Grossteils gebaut, aber noch lokal/manuell und sicherheitstechnisch unreif fuer Autonomie. |

### Was wurde tatsaechlich gebaut?

| Feature | Ist-Zustand | Bewertung |
|---|---|---|
| Auth / Workspace | Supabase Auth, `profiles`, `workspaces`, `workspace_members`, Bootstrap im Backend. | Solide Basis. |
| Daily Check-in | Formular, lokale Drafts, Check-in Persistenz. | Nutzbar. |
| Daily Plan AI | OpenAI Structured Outputs, JSON-Schema, Rules, Reviews, Projects als Kontext, Kostenlogging. | Nutzbar, aber synchroner Request. |
| Evening Review | Review-Formular und Persistenz. | Nutzbar. |
| User Rules | CRUD und Einbindung in Planerzeugung. | Nutzbar. |
| Projects | CRUD mit Status/Priority/Next Action/Risk, Dashboard-Radar, Plan-Kontext. | Nutzbar als Backlog, nicht als echtes Project Command Center. |
| Operator / Work Orders | Liste, Detail, Create Form, Statusflow, Approval Scope, Steps, Logs, Artifacts, Review Package. | Starkes Control-Plane-MVP. |
| Runner Prompt | UI-Generator und Python-Prompt-Builder. | Nutzbar, aber doppelte Template-Pflege. |
| Import Bridge | `import_work_order_result.py` schreibt Result JSON zur API. | Nutzbar, aber token- und manuell abhaengig. |
| Local Runner | `run_work_order.py` mit `prompt-file`, `import-result`, `execute`. | Nutzbar fuer lokale interne Runs. |
| Claude Code Adapter | Implementiert, semi-automatisch, mit Trust-Precondition und Tool-Mapping. | Produktiv testbar, nicht unbeaufsichtigt. |
| Codex Adapter | Datei vorhanden, execute/collect nicht implementiert. | Platzhalter. |
| OpenClaw Adapter | Datei vorhanden, nicht evaluiert. | Platzhalter. |

### Erledigt, offen, ueberholt

| Ticket / Thema | Status | Kommentar |
|---|---|---|
| Daily Planner MVP | Erledigt | Kernflow existiert und ist abgesichert gegen viele Basisausfaelle. |
| Stability Sprint | Erledigt | README listet konkrete Fixes; Code bestaetigt zentrale Punkte. |
| Project Context fuer AI Plan | Erledigt | `plans.py` laedt aktive/wartende Projekte non-fatal. |
| Background Operator Mock Spike | Ueberholt | Mock-Daten existieren noch als Fallback/Seed, aber API und DB sind gebaut. |
| OP-Backend-001 Work Orders | Erledigt im Code | Migration, Models, Router, Service vorhanden. Live-Anwendung nicht bewiesen. |
| OP-Runner-001 Steps/Import/Prompt | Erledigt im Code | Steps, Import Bridge, Runner Prompt vorhanden. |
| OP-Runner-002 Local Harness | Erledigt im Code | `run_work_order.py` vorhanden. |
| OP-Runner-003 Adapter Contract | Erledigt im Code/Doku | Interface und Registry vorhanden. |
| OP-ClaudeAdapter-001 | Teilweise erledigt | Implementiert und dokumentiert, aber semi-auto und ohne Sandbox. |
| Triggered Runner | Offen | Kein Backend-Trigger, kein Scheduler, keine Queue. |
| Sandbox Worker | Offen | Keine OS-/Container-Isolation, keine harte Dateisystem-Allowlist. |
| Codex Adapter | Offen | Placeholder. |
| OpenClaw Adapter | Offen | Placeholder. |
| Project Command Center | Offen | Projects ist simple CRUD-Liste ohne Work Orders, Ziele, Milestones, Decision Logs. |

### Neue Features ausserhalb des alten Planner-Plans

| Feature | Strategische Bedeutung |
|---|---|
| Approval Scope | Macht AI-Arbeit review- und sicherheitsfaehig. |
| WorkOrderSteps / Ticketplan | Verwandelt "AI macht etwas" in sichtbare Arbeitsplanung. |
| Activity Logs | Auditierbarkeit und Vertrauen. |
| Artifacts | Grundlage fuer Review, Wissensspeicher und spaetere Wiederverwendung. |
| Review Packages | Menschliche Freigabe wird produktisiert. |
| Local Runner Harness | Erster realer Execution-Plane-Schritt. |
| RunnerAdapter Contract | Verhindert Vendor-Lock-in auf Claude Code. |
| Claude Code Adapter | Erster echter Adapter jenseits Copy/Paste. |

## 2. Aktuelle technische Architektur

### Frontend-Struktur

| Bereich | Zustand |
|---|---|
| Framework | Next.js 14 App Router, React, TypeScript, Tailwind. |
| Layout | `AppShell`, Sidebar, MobileNav, Header. Protected routes ueber `ProtectedRoute`. |
| API Client | `frontend/lib/api.ts` mit Supabase access token in `Authorization`. |
| i18n | Flat dictionary in `frontend/lib/i18n.ts`, EN/DE, keine externe i18n-Library. |
| Daily Planner | `/morning`, `/plans/[id]`, `/review`, Dashboard-Komponenten. |
| Projects | `/projects`, `ProjectsManager`. |
| Operator | `/operator`, `/operator/new`, `/operator/[id]`, Work-Order-Komponenten. |
| Types | `frontend/types/index.ts`; Work Orders bewusst camelCase, API Mapper in `workOrderMapper.ts`. |

### Backend-Struktur

| Bereich | Zustand |
|---|---|
| Framework | FastAPI, Pydantic, Supabase Python Client. |
| Router | Auth, Health, Checkins, Plans, Reviews, Rules, Projects, Work Orders. |
| Services | DB-Logik getrennt in Services; AI-Service isoliert. |
| Auth | Supabase Bearer Token, `get_current_user`, `ensure_user_workspace`, `require_owned_record`. |
| AI | OpenAI Structured Outputs fuer Daily Plan; Kostenlogging mit `ai_usage_log`. |
| Work Orders | Eigene Models, Service, Router, Safety Validator. |

### Supabase / Migrations

| Bereich | Ist-Zustand |
|---|---|
| Basis-Schema | `workspaces`, `profiles`, `workspace_members`, `life_areas`, `projects`, `user_rules`, `daily_checkins`, `daily_plans`, `evening_reviews`, `ai_usage_log`. |
| Work Orders | `work_orders`, `approval_scopes`, `agent_runs`, `activity_logs`, `artifacts`, `review_packages`, `work_order_steps`. |
| RLS | Nutzerbezogen auf Root-Tabellen, Join-basierte Policies fuer Work-Order-Children. |
| Idempotenz | Viele Migrations sind idempotent; `006_work_orders.sql` enthaelt nicht-idempotente `CREATE POLICY` Statements. |
| Live-Status | Aus Repo nicht belegbar. README/Docs sagen teils, dass Migrationen manuell angewendet werden muessen. |

### Operator / Work Orders

| Komponente | Bewertung |
|---|---|
| Data Model | Sauberer Control Plane: Scope, Steps, Runs, Logs, Artifacts, Review. |
| Create Flow | Work Order + Approval Scope + sechs Default-Steps werden erzeugt. |
| Detail View | Gute Uebersicht: Statusflow, Lifecycle, Execution Plan, Scope, Logs, Artifacts, Review Package. |
| Fallback | Bei API-Fehlern wird auf Mock-Daten gewechselt. Fuer Demo gut, fuer echte Nutzung riskant. |
| Mutationen | Lifecycle-Buttons patchen Status; Import Script schreibt Ergebnisse. |

### Safety / Approval Scope

| Layer | Was existiert | Grenze |
|---|---|---|
| UI Safety Rules | Sichtbare Regeln und Scope-Defaults. | Nur Anzeige und Form-Hilfe. |
| Backend Validator | Blocked Keywords in `allowed_actions`/`requires_approval` werden abgelehnt. | Keyword-basiert, umgehbar durch andere Formulierungen. |
| Runner Preconditions | Scope, blocked actions, status, steps, path safety fuer execute. | Gilt nur fuer lokalen Harness. |
| Claude Tool Mapping | Allowed/Disallowed Tools fuer Claude Code. | Best-effort, nicht vollstaendige Sandbox. |
| Human Review | `review_ready -> accepted/rework_requested` als menschliche Entscheidung. | Qualitaet des Review Packages nicht technisch garantiert. |

### Auth / Workspace

| Punkt | Bewertung |
|---|---|
| Session Validation | Backend validiert Supabase Token. |
| Ownership | `require_owned_record` prueft `user_id`; Child-Routen pruefen Work-Order-Root. |
| Workspace Foundation | Personal Workspace wird idempotent angelegt. |
| Team/B2B Readiness | Datenmodell hat Workspace-Spalten, aber UI/Permissions sind noch Single-User-orientiert. |

### Daily Planner

| Punkt | Bewertung |
|---|---|
| Nutzbarkeit | Hohe Nutzbarkeit fuer Einzelperson. |
| Robustheit | Duplikat-Check, AI-Cap, Fehlercodes, Review-Kontext vorhanden. |
| Grenze | AI-Call synchron; kein Kalender, keine Task-Integration, keine echte Ausfuehrungsverfolgung. |

### Projects

| Punkt | Bewertung |
|---|---|
| Nutzbarkeit | Einfacher Project Backlog mit Status, Priority, Next Action, Risk. |
| Einbindung | Dashboard und AI Daily Plan Kontext. |
| Grenze | Keine Milestones, keine Work Orders pro Projekt, keine Decision Logs, keine Projekt-Reviews. |

## 3. Produktbewertung

### Was heute nutzbar ist

| Modul | Nutzungsreife |
|---|---|
| Daily Planner | Daily internal use moeglich. |
| Rules | Nutzbar fuer Personalisierung. |
| Evening Review | Nutzbar, wenn Disziplin vorhanden ist. |
| Projects | Nutzbar als einfacher Kontext-Backlog. |
| Operator Create/Detail | Nutzbar fuer interne Work Orders. |
| Manual Runner Loop | Nutzbar fuer kleine interne Dev-Aufgaben. |
| Claude Code Adapter | Nutzbar fuer kontrollierte Experimente. |

### Was Demo/Mock ist

| Bereich | Demo-Anteil |
|---|---|
| Operator Fallback | Mock-Daten werden bei API-Fehlern angezeigt. |
| Codex Adapter | Placeholder. |
| OpenClaw Adapter | Placeholder. |
| Background Autonomy | Noch kein echter Hintergrunddienst. |
| Project Command Center | Noch nicht mehr als CRUD plus Dashboard. |

### Was gefaehrlich oder unreif ist

| Risiko | Warum relevant |
|---|---|
| Mock-Fallback verdeckt API-Probleme. | Nutzer koennten denken, sie sehen echte Daten. |
| Runner kann lokal mit `--runner-command` Shell-Kommandos ausfuehren. | Mensch muss command bewusst liefern; trotzdem hoher Blast Radius. |
| Keine Sandbox. | Approval Scope ist nicht gleich technische Isolation. |
| Keine harte Result-Vollstaendigkeit. | Import validiert Top-Level, aber nicht, ob alle geplanten Steps im Result vorkommen. |
| Token aus Browser Local Storage manuell kopieren. | Operational friction und Credential-Risiko. |
| Keine zentrale Policy Engine. | Safety-Regeln existieren dreifach: frontend, backend, scripts. Drift-Risiko. |

### Strategisch stark

| Staerke | Warum sie zaehlt |
|---|---|
| Control Plane / Execution Plane Split | Erlaubt Claude, Codex, OpenClaw oder lokale Worker auszutauschen. |
| Work Order als generisches Primitive | Kann spaeter Sales, Ops, Content, Learning, Admin tragen. |
| Review Package | Macht Agentenarbeit kauf- und vertrauensfaehiger. |
| Local-first Runner | Gute Bruecke zu Self-hosted / Local LifeOS. |
| Daily Loop + Projects + Operator | Gute Kombination aus Planung, Kontext und Ausfuehrung. |

### Unnoetige oder fruehe Komplexitaet

| Thema | Bewertung |
|---|---|
| Zu viele Agent-Rollen im Default | Fuer kleine Tasks koennen sechs Rollen Overhead sein. |
| AgentRun plus WorkOrderSteps | Fachlich begruendbar, aber aktuell doppelt, solange keine echten AgentRun-Events entstehen. |
| Mehrere Safety-Regel-Kopien | Praktisch, aber Drift-anfällig. |
| OpenClaw Slot | Strategisch okay, aber vor Beta kein Muss. |
| Team types offen als String | Flexibel, aber ohne Domain-spezifische UX noch wenig wert. |

### Blocker fuer echten Alltagseinsatz

| Blocker | Prioritaet |
|---|---|
| Live-Migrations/API-Funktionsfaehigkeit muss bewiesen werden. | Must Fix |
| Mock-Fallback muss fuer echte Nutzung anders behandelt werden. | Must Fix |
| Work Orders brauchen Projektverknuepfung und echten "My queue today" Flow. | Should Fix |
| Runner-Result muss strenger validiert werden. | Safety Critical |
| Claude/Codex-Ausfuehrung braucht klare operative Grenzen. | Safety Critical |
| Onboarding/Pricing/Positioning fehlt. | Revenue Enabler |

## 4. AI-Team- und Runner-Bewertung

### Wie weit ist das Background Dev Team wirklich?

| Stufe | Status |
|---|---|
| Control Plane | Gebaut. |
| Work Order Creation | Gebaut. |
| Ticketplan | Gebaut. |
| Prompt-Erzeugung | Gebaut. |
| Manuelle Runner-Ausfuehrung | Gebaut. |
| Ergebnisimport | Gebaut. |
| Review Package | Gebaut. |
| Semi-auto Claude Code | Gebaut, aber mit Trust-Precondition. |
| Codex Adapter | Nicht gebaut. |
| Sandbox Worker | Nicht gebaut. |
| Backend-triggered Runner | Nicht gebaut. |
| Live Events | Nicht gebaut. |
| Multi-agent echte Parallelisierung | Nicht gebaut. |

Kurz: Es ist ein brauchbarer lokaler "Agent Workbench"-Loop, noch kein autonomes Background Dev Team.

### Work Order -> Runner -> Result -> Review

| Schritt | Bewertung |
|---|---|
| Work Order | Gute Struktur: Goal, Criteria, Scope, Steps. |
| Runner Start | Lokal via Script; UI kopiert Befehle. |
| Execution | Manuell oder semi-auto; kein Server-Worker. |
| Result JSON | Gute Idee, aber Schema-Validierung ist noch minimal. |
| Import | Funktional, per API, partial failure tolerant. |
| Review | UI zeigt Review Package und Statusuebergang. |
| Acceptance | Mensch entscheidet. |

### Was fuer Claude Code Adapter noch fehlt

| Luecke | Prioritaet |
|---|---|
| Echte End-to-End-Testmatrix mit mehreren Work Orders. | Must Fix |
| Striktere Tool-/Pfad-Allowlist, nicht nur Best-effort Mapping. | Safety Critical |
| Result Schema vollstaendig validieren: alle Steps, IDs, Status, Artifact-Typen, Review-Felder. | Safety Critical |
| Besserer Umgang mit Permission Denials und partiellen Runs. | Should Fix |
| Kein API Token im Runner-Kontext, weiterhin garantieren. | Safety Critical |
| Cost/timeout UX in UI sichtbar machen. | Should Fix |

### Was fuer Sandbox Worker fehlt

| Luecke | Prioritaet |
|---|---|
| Isolierter Arbeitsbaum pro Work Order. | Safety Critical |
| Dateisystem-Policy: allowed_paths/blocked_paths technisch erzwingen. | Safety Critical |
| Netzwerk-Policy: standardmaessig aus, explizit erlauben. | Safety Critical |
| Prozess-/Shell-Allowlist. | Safety Critical |
| Ressourcenlimits: CPU, RAM, Laufzeit, Kosten. | Must Fix |
| Secret Redaction und Secret Mount Policy. | Safety Critical |
| Diff-only Output und Review vor Apply. | Must Fix |
| Queue/Worker-Protokoll und Heartbeats. | Should Fix |

### Was fuer Codex/OpenClaw Adapter fehlt

| Adapter | Fehlend |
|---|---|
| Codex | CLI real recherchieren, `prepare/execute/collect_result` implementieren, Permission-/Sandbox-Modell klaeren, Live-Test mit Kostenlimit, Result Parsing. |
| OpenClaw | Tool ueberhaupt evaluieren: Install, CLI/API, Safety-Modell, Lizenz, lokaler Betrieb, Ressourcenbedarf, Adapterfaehigkeit. |

### Kritische Safety-Luecken

| Luecke | Konsequenz |
|---|---|
| Prompt-Instructions sind keine Enforcement-Schicht. | Runner kann Scope missachten. |
| Keyword Matching ist keine Policy Engine. | Umformulierungen koennen Regeln umgehen. |
| Kein isolierter Worker. | Lokaler Runner hat Zugriff auf Workspace-Kontext. |
| Result JSON kann unvollstaendig sein. | Review kann "ready" wirken, obwohl Steps fehlen. |
| Mock-Fallback kann Live-Probleme tarnen. | Falsches Vertrauen in Systemzustand. |

## 5. Neue Produktvision

### Produktvision

CommandPilot ist ein persoenliches Business- und Execution-OS fuer Solo-Founder, Operator und kleine Teams. Es verbindet Tagesplanung, Projektfokus und agentenbasierte Arbeitsausfuehrung in einem auditierbaren System: Ziele werden in Work Orders uebersetzt, AI/Runner arbeiten innerhalb definierter Approval Scopes, und der Mensch entscheidet anhand eines Review Packages.

### Zielkunden

| Segment | Schmerz | Passendes Angebot |
|---|---|---|
| Solo-Founder / Indie Hacker | Zu viele parallele Aufgaben, AI-Tools ohne Kontext, fehlende Ausfuehrungssystematik. | Personal Execution OS. |
| Technical Founder | Will Claude/Codex produktiv nutzen, aber sicher und nachvollziehbar. | Background Dev Team Control Plane. |
| Agentic-AI Power User | Nutzt mehrere AI-Tools, braucht Orchestrierung. | Runner Control Plane. |
| Kleine Agentur / Micro-SaaS Team | Viele kleine interne Tasks, Review-Pflicht, wenig Management-Overhead. | Work Orders + Review Packages. |
| Self-hosted Enthusiasten | Wollen lokale Daten und lokale Runner. | Local LifeOS / Business OS. |

### Kernversprechen

| Versprechen | Klartext |
|---|---|
| "Your AI team, with boundaries." | AI arbeitet nur innerhalb expliziter Scopes. |
| "From morning chaos to shipped work." | Tagesplanung wird mit Projekten und Work Orders verbunden. |
| "Review before risk." | Keine externe/irreversible Aktion ohne Review Package. |
| "Bring your runner." | Claude Code, Codex oder spaeter andere Runner statt Vendor-Lock-in. |

### MVP-Scope

| Im MVP | Nicht im MVP |
|---|---|
| Daily Planner, Projects, Work Orders. | Vollautonomer Cloud-Agent. |
| Local Runner mit manual_prompt und Claude Code semi-auto. | Production Deployments durch Agenten. |
| Approval Scope, Steps, Logs, Artifacts, Review Package. | Marketplace, Agent Departments. |
| Interne Nutzung durch Serkan. | Breite Multi-Tenant-B2B-Plattform. |
| Private Beta mit 3-5 Power Usern. | Generische LifeOS-Komplettabdeckung. |

### No-Go-Liste

| No-Go | Grund |
|---|---|
| Kein Agent darf Production-Daten aendern. | Safety. |
| Kein Agent darf Secrets lesen, loggen oder anzeigen. | Safety. |
| Keine Deployments aus CommandPilot heraus vor Sandbox/Policy-Reife. | Safety. |
| Kein Auto-Push/PR ohne explizite Approval Scope und Review. | Safety. |
| Keine Beta mit unbeaufsichtigtem Runner. | Vertrauensrisiko. |
| Kein Feature-Bau ohne Serkan-internen Nutzungsbeweis. | Fokus. |

## 6. Business-Roadmap

### Phase 0: Stabilisierung des aktuellen Systems

| Aufgabe | Prioritaet | Label |
|---|---|---|
| Migrationsstatus lokal und in Supabase sauber verifizieren. | Must Fix | Safety Critical |
| Work-Order API Smoke Test nach QA-Checklist durchlaufen. | Must Fix | Safety Critical |
| Operator-Mock-Fallback in echter Nutzung offensiver kennzeichnen oder deaktivierbar machen. | Must Fix | Safety Critical |
| Runner Result Schema strenger validieren. | Must Fix | Safety Critical |
| Docs mit aktuellem Stand synchronisieren: Create Form existiert, Claude Adapter existiert. | Should Fix | Productivity Multiplier |
| Minimaler Testplan fuer Daily Planner, Projects, Operator, Runner. | Should Fix | Productivity Multiplier |

### Phase 1: Serkan nutzt CommandPilot intern taeglich

| Aufgabe | Prioritaet | Label |
|---|---|---|
| 7-Tage-Nutzungsprotokoll: Morning, Projects, Operator, Evening Review. | Must Fix | Productivity Multiplier |
| Dashboard als echtes "Today Command" ausrichten: Plan + aktive Projekte + Work Orders needing review. | Should Fix | Productivity Multiplier |
| Projects mit Work Orders verknuepfen. | Should Fix | Revenue Enabler |
| Daily Review fragt explizit nach offenen Work Orders/Blockern. | Should Fix | Productivity Multiplier |
| Friction-Liste aus realer Nutzung pflegen. | Must Fix | Productivity Multiplier |

### Phase 2: Background Dev Team entwickelt CommandPilot/CampsPilot produktiv mit

| Aufgabe | Prioritaet | Label |
|---|---|---|
| 5 echte kleine Work Orders ueber manual/Claude Loop abschliessen. | Must Fix | Productivity Multiplier |
| Claude Adapter stabilisieren und bekannte Fehlerklassen dokumentieren. | Must Fix | Safety Critical |
| Diff/Artifact-Qualitaet verbessern: echte Patches, Tests, Risiken. | Should Fix | Productivity Multiplier |
| Work Order Templates fuer Docs, Frontend, Backend, Bugfix. | Should Fix | Productivity Multiplier |
| Sandbox Worker Design konkretisieren. | Should Fix | Safety Critical |

### Phase 3: Private Beta mit echten Nutzern

| Aufgabe | Prioritaet | Label |
|---|---|---|
| Beta-Scope auf Daily Planner + Projects + manual Work Orders begrenzen. | Must Fix | Revenue Enabler |
| Keine unbeaufsichtigten Runner fuer Beta-Nutzer. | Must Fix | Safety Critical |
| Onboarding: "erste 3 Tage mit CommandPilot" Flow. | Should Fix | Revenue Enabler |
| Feedback-Instrumentation: Wo brechen Nutzer ab? | Should Fix | Revenue Enabler |
| Rechtliche Basics: Terms, Privacy, AI data handling. | Must Fix | Safety Critical |

### Phase 4: Erstes zahlbares Produktangebot

| Aufgabe | Prioritaet | Label |
|---|---|---|
| Angebot definieren: Personal Execution OS fuer Builder. | Must Fix | Revenue Enabler |
| Pricing testen: z.B. 19-49 EUR/Monat fuer Planner/Projects, hoeher fuer Runner-Workflows. | Should Fix | Revenue Enabler |
| Billing noch nicht ueberagentisch automatisieren. | Must Fix | Safety Critical |
| Support- und Refund-Prozess definieren. | Should Fix | Revenue Enabler |
| Case Study: Serkan/CampsPilot als Proof. | Should Fix | Revenue Enabler |

### Phase 5: Self-hosted / Local LifeOS / Business OS Option

| Aufgabe | Prioritaet | Label |
|---|---|---|
| Local deployment story: Docker Compose oder documented local setup. | Should Fix | Revenue Enabler |
| Local Runner mit Sandbox als Differenzierungsmerkmal. | Must Fix | Safety Critical |
| Backup/Export/Import. | Should Fix | Revenue Enabler |
| Offline/local-first Datenhaltung pruefen. | Later | Nice to Have |
| Enterprise/self-hosted Lizenzmodell. | Later | Revenue Enabler |

### Phase 6: Skalierung / Agent Departments / Marketplace oder B2B

| Aufgabe | Prioritaet | Label |
|---|---|---|
| Agent Departments: Dev, Ops, Sales, Content, Admin. | Later | Revenue Enabler |
| Marketplace fuer Templates/Adapters. | Backlog | Revenue Enabler |
| Team Workspaces mit Rollen/Rechten. | Later | Revenue Enabler |
| B2B-Angebot fuer kleine Teams. | Later | Revenue Enabler |
| Auditable Agent Governance als Premium Feature. | Later | Revenue Enabler / Safety Critical |

## 7. Priorisierungsmatrix

| Aufgabe | Must/Should/Later/Backlog | Zusatzlabel |
|---|---|---|
| Work-Order API Smoke Test ausfuehren | Must Fix | Safety Critical |
| Migrationsstatus verifizieren | Must Fix | Safety Critical |
| Mock-Fallback fuer echte Nutzung absichern | Must Fix | Safety Critical |
| Result JSON vollstaendig validieren | Must Fix | Safety Critical |
| Claude Code Adapter E2E testen | Must Fix | Safety Critical / Productivity Multiplier |
| Serkan 7-Tage-Dogfooding | Must Fix | Productivity Multiplier |
| Work Orders mit Projects verknuepfen | Should Fix | Revenue Enabler |
| Dashboard Work Orders needing review | Should Fix | Productivity Multiplier |
| Work Order Templates | Should Fix | Productivity Multiplier |
| Sandbox Worker Design | Should Fix | Safety Critical |
| Codex Adapter implementieren | Later | Productivity Multiplier |
| OpenClaw evaluieren | Backlog | Nice to Have |
| Team Workspace Rollen | Later | Revenue Enabler |
| Marketplace | Backlog | Revenue Enabler |

## 8. Technische Roadmap

| Reihenfolge | Ticket | Ziel |
|---|---|---|
| 1 | `OP-Stabilize-001` API Smoke Test + Migrationsstatus dokumentieren. | Sicher wissen, was live funktioniert. |
| 2 | `OP-Safety-001` Result Schema Validator erweitern. | Keine unvollstaendigen Runner-Ergebnisse importieren. |
| 3 | `OP-UX-001` Mock-Fallback als Demo Mode statt stiller Fallback. | Keine falsche Datenwahrnehmung. |
| 4 | `OP-Project-001` Work Orders optional mit Project verknuepfen. | Projektarbeit wird steuerbar. |
| 5 | `OP-Dashboard-001` Work Orders needing approval/review auf Dashboard. | Daily Command Center wird real. |
| 6 | `OP-Claude-002` Claude Adapter Fehlerklassen und Permission Denials besser abbilden. | Produktivere interne Nutzung. |
| 7 | `OP-Sandbox-Design-001` Sandbox Worker Spec. | Weg zu sicherem Triggered Runner. |
| 8 | `OP-Codex-001` Codex CLI recherchieren und Adapter v0 bauen. | Runner-Auswahl. |

## 9. Sicherheitsroadmap

| Stufe | Massnahme | Ziel |
|---|---|---|
| 0 | Keine Secrets lesen/anzeigen; `.env` bleibt tabu. | Basishygiene. |
| 1 | Blocked Actions nicht nur anzeigen, sondern bei Create und Runner Start pruefen. | Bereits teilweise vorhanden. |
| 2 | Result JSON streng validieren. | Import nur valider, kompletter Ergebnisse. |
| 3 | Policy-Konfiguration zentralisieren. | Drift zwischen Frontend/Backend/Scripts reduzieren. |
| 4 | Sandbox Worker mit Dateisystem-/Netzwerk-/Prozess-Grenzen. | Echte Laufzeitkontrolle. |
| 5 | Diff-only Apply: Runner erzeugt Patch, Mensch akzeptiert. | Keine direkten riskanten Aenderungen. |
| 6 | Audit Trail und Tamper-Resistance fuer Activity Logs. | B2B-/Trust-Faehigkeit. |

## 10. Go-to-Market Roadmap

| Zeitraum | Fokus | Ergebnis |
|---|---|---|
| Jetzt | Internes Dogfooding | Serkan nutzt CommandPilot taeglich. |
| 30 Tage | Private Alpha | 2-3 befreundete Power User testen ohne Runner-Autonomie. |
| 60 Tage | Private Beta | 5-10 Nutzer, klares Onboarding, Feedback-Loops. |
| 90 Tage | Paid Pilot | Erstes Angebot, manuell betreut, Founder-nahe Zielgruppe. |
| Danach | Self-hosted/Local | Differenzierung ueber lokale Runner und Datenkontrolle. |

## 11. 7-Tage-Plan

| Tag | Ziel | Ergebnis |
|---|---|---|
| 1 | Migrations/API Smoke Test, aktuelles System starten. | Liste: funktioniert / bricht / unklar. |
| 2 | Daily Planner real nutzen: Morning + Plan + Review. | Erste Friction-Liste. |
| 3 | Projects bereinigen: echte Projekte, Next Actions, Risks. | Projekt-Radar ist nuetzlich. |
| 4 | Eine kleine docs-only Work Order end-to-end. | Erster sauberer Review Package Loop. |
| 5 | Eine kleine Frontend Work Order end-to-end. | Runner-Loop fuer Code validiert. |
| 6 | Dashboard-Frictions bewerten. | Scope fuer Dashboard-Fix. |
| 7 | Roadmap nach echter Nutzung anpassen. | 30-Tage-Plan finalisieren. |

## 12. 30-Tage-Plan

| Woche | Fokus | Deliverables |
|---|---|---|
| 1 | Stabilisierung | Smoke Tests, Result Validation, Demo Mode, Docs. |
| 2 | Daily Internal Use | Dashboard Work Orders, Project-Link, Review-Fragen. |
| 3 | Background Dev Team | 5 echte Work Orders, Claude Adapter Hardenings. |
| 4 | Private Beta Prep | Positioning, Onboarding, Beta-Scope, legal basics. |

## 13. 90-Tage-Plan

| Zeitraum | Ziel | Messbare Definition |
|---|---|---|
| Tage 1-30 | Intern stabil und nuetzlich. | Serkan nutzt es 20+ Tage; 10+ echte Work Orders. |
| Tage 31-60 | Private Beta. | 5 echte Nutzer, 3 davon nutzen es woechentlich. |
| Tage 61-90 | Paid Pilot. | 1-3 zahlende Nutzer oder bezahlte Pilot-Zusagen. |

## 14. Offene Risiken

| Risiko | Wahrscheinlichkeit | Impact | Umgang |
|---|---|---|---|
| Produkt ist zu breit. | Hoch | Hoch | MVP auf Execution OS fuer Builder begrenzen. |
| Runner-Sicherheit reicht nicht fuer Vertrauen. | Hoch | Hoch | Keine Autonomie vor Sandbox/Policy. |
| Daily Planner bleibt isoliert vom echten Arbeitsfluss. | Mittel | Hoch | Projects + Work Orders ins Dashboard ziehen. |
| Nutzer wollen Kalender/Gmail/Slack sofort. | Mittel | Mittel | Erst manuelle Work Orders, Integrationen spaeter. |
| Self-hosted ist operativ teuer. | Mittel | Mittel | Erst lokal dokumentiert, spaeter paketieren. |
| AI-Kosten/Modelle aendern sich. | Hoch | Mittel | Pricing-Konfiguration und Limits aktualisieren. |

## 15. Konkrete naechste Tickets fuer Claude CLI / Codex CLI

### Claude CLI

| Ticket | Beschreibung | Akzeptanzkriterien |
|---|---|---|
| `OP-Claude-002` | Mehrere echte Claude-Code-Adapter-Runs dokumentieren. | Mindestens 3 Work Orders, Ergebnisstatus, Kosten, Fehler, Permission Denials dokumentiert. |
| `OP-Claude-003` | Result Validation vor Import verschaerfen. | Fehlende Step IDs, ungueltige Status, fehlende Review-Felder brechen vor API-Calls ab. |
| `OP-Claude-004` | Permission Denials in Review Package/Activity Log sichtbar machen. | `permission_denials.json` wird als Artifact oder Log-Hinweis importierbar. |
| `OP-Claude-005` | Allowed Tools Mapping testen und begrenzen. | Dokumentierte Matrix: allowed_actions -> Claude Tools; keine destructive git/network tools. |

### Codex CLI

| Ticket | Beschreibung | Akzeptanzkriterien |
|---|---|---|
| `OP-Codex-001` | Codex CLI lokal recherchieren. | `codex --help`/Docs geprueft, echte CLI-Syntax dokumentiert. |
| `OP-Codex-002` | Codex Adapter `execute()` v0 implementieren. | Kann `prompt.md` ausfuehren oder klar scheitern; kein `shell=True` fuer Prompt-Inhalte. |
| `OP-Codex-003` | Codex Result Collection implementieren. | Adapter findet oder liest Result JSON und nutzt zentralen Validator. |
| `OP-Codex-004` | Codex Safety Matrix. | Tool-/Permission-Modell beschrieben; keine Auto-Ausfuehrung ohne klare Grenzen. |

### Sandbox / Worker

| Ticket | Beschreibung | Akzeptanzkriterien |
|---|---|---|
| `OP-Sandbox-Design-001` | Execution Sandbox Spec. | Dateisystem, Netzwerk, Prozess, Secrets, Logs, Diff-Flow beschrieben. |
| `OP-Worker-001` | Triggered Runner Architektur. | Queue, Status, Heartbeat, Failure/Retry, Human Approval Gates beschrieben. |
| `OP-Policy-001` | Zentrale Safety Policy. | Frontend, Backend, Scripts lesen aus einer kanonischen Policy-Quelle oder generierten Artefakten. |

## 16. Schlussbewertung

CommandPilot hat einen echten strategischen Sprung gemacht: Aus einem guten AI Daily Planner ist der Anfang eines persoenlichen Execution OS geworden. Der Code zeigt nicht nur UI-Ideen, sondern ein persistiertes Work-Order-Control-Plane-Modell mit Runner-Vertrag und erstem Claude-Code-Adapter.

Der naechste Engpass ist nicht "mehr Features". Der Engpass ist Beweis: migrationsgesichert, intern taeglich genutzt, Runner-Loop mehrfach real durchlaufen, Safety-Luecken geschlossen, dann erst Private Beta. Wenn diese Reihenfolge eingehalten wird, ist CommandPilot als zahlbares Produkt plausibel: nicht als generischer To-do-Planner, sondern als sicherer Arbeitsraum fuer Menschen, die AI-Agenten produktiv einsetzen wollen, ohne Kontrolle und Kontext zu verlieren.
