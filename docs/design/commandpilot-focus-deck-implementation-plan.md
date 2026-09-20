# CommandPilot — Focus Deck Implementation Plan

Status: **Plan only. Kein Produktcode geschrieben, kein Commit, kein Push,
kein Merge.**

Visuelle Quelle (LOCKED, Design Status abgeschlossen):
`C:\Users\serka\dev\commandpilot-design-v2\03-selected-master\`,
`04-design-system\`, `05-pages\`, `06-mobile\`, `07-final-review\phase6-review.md`.

Analysierte Code-Basis: `commandpilot` (main, `af05d16`) — vollständiges
Produkt (Daily Planner + Operator Control Plane). `cp-design`s JARVIS-D1-
Token-Architektur (drei Ebenen: primitiv/semantisch/interaktiv in
`globals.css`) wird als **Technik** wiederverwendet, nicht als Farbwelt —
Steel-Blue wird durch Bronze/Copper ersetzt, die darunterliegende
CSS-Custom-Property-Struktur bleibt sinnvoll.

---

## 1. Current Architecture Summary

**Frontend** (Next.js 14 App Router): `AppShell` (Sidebar + `<main>` +
MobileNav) um jede geschützte Route. Sidebar: 8 Textlabel-Einträge
(Dashboard/Jarvis/Morning/Review/Projects/Operator/Rules/Settings), volle
Höhe, kein Icon-only-Modus. Kein permanenter Jarvis-Bereich — Jarvis ist
eine isolierte Route (`/jarvis` → `JarvisChat.tsx`, volle Chat-Historie,
Bubble-Darstellung, kein Content-Flow). Keine Route-Kontext-Injection in
Jarvis — nur Second-Brain-Kontext (`vault_service.get_context_for_query`).

**Backend** (FastAPI): Schichtung Router→Service→`db/client.py`, strikt
eingehalten. Work-Order-Statemachine real und vollständig
(`transition_work_order()`, `backend/app/models/work_order.py`), inkl.
`ApprovalScope`-Keyword-Enforcement (`core/safety_rules.py`). **Kein**
generisches Approval-Primitiv — Freigabe existiert ausschließlich als
Work-Order-Statusübergang (`needs_approval`→`queued` via "Requeue",
`review_ready`→`accepted`/`rework_requested` via "Accept"/"Request rework").
Es gibt **keinen** "Approve/Reject einer einzelnen vorgeschlagenen Aktion"-
Endpunkt — das ist der noch nicht gebaute Command Layer (JARVIS-C1,
Produktrichtung Schritt 3 in `CLAUDE.md`).

**Datenmodell-Realität, die für Phase 7 zählt:**
- `Project`: `id, user_id, name, description?, status, priority, next_action?, risk?, created_at, updated_at`. **Kein** `owner`, **kein** `due_date`, **kein** numerischer Fortschritt, **keine** Activity-Log-Anbindung.
- `WorkOrder`: **kein** `risk`-Feld. `ApprovalScope` hat `maxCostUsd`/`maxRuntimeMinutes`, keine Risikostufe.
- `ReviewPackage`: `risks: string[]` (Freitext-Liste), kein Risiko-Level.
- `JarvisSuggestedAction`: **hat** `risk: low/medium/high` + `requires_approval: boolean` — aber v1 liefert `suggested_actions` immer `[]`.
- `WorkOrderDetail.tsx` hat drei Panels, die in keinem Focus-Deck-Bild vorkommen: `LocalRunnerPanel`, `RunnerPromptPanel`, `SafetyRulesPanel`.

## 2. Target UI Architecture

`[Icon Rail (5 Ziele, volle Höhe)] [Jarvis Rail (collapsed/normal/expanded)] [Workspace]`,
Bronze/Copper als einzige Aktionsfarbe, Serif einmal pro View, Statusfarben
getrennt von Bronze. Fünf globale Ziele bündeln die heutigen acht Routen
(siehe `07-final-review/phase6-review.md` Abschnitt 3+8 für die dort schon
dokumentierte offene Frage, die dieser Auftrag jetzt so beantwortet):

| Icon | Bündelt |
|---|---|
| Home | Dashboard, Morning Check-in, Daily Plan, Daily Review |
| Jarvis | Expanded Jarvis Experience |
| Projects | Project-Liste, Project Detail (`/projects/[id]`, neu) |
| Activity | Operator, Work Orders, Agent Runs, Review Packages |
| Settings | Settings, Rules, später Integrationen |

## 3. Gap Analysis (pro Screen, A = echte Daten, B = abgeleitet, C = neue Fähigkeit)

| Screen | Primär gezeigt | Herkunft |
|---|---|---|
| Home | Fokus-Projekt, "Needs your decision", In Progress, Recent Activity | A (Projects/Plans) für Fokus; **C** für "Needs your decision" als einzelne Approve/Reject-Karte — es gibt keinen Endpunkt, der einzelne Entscheidungen dieser Art liefert oder annimmt |
| Jarvis (expanded) | Konversation, Quellen, Basiskontext | A, unverändert zur echten `JarvisChat`-Logik |
| Projects | Liste mit Status/Priorität/Next Action/Risk | A, 1:1 aus `Project` |
| Project Detail | Owner, Due Date, Recent Activity | **C** — `owner`/`due_date` existieren nicht im `Project`-Modell, projektbezogene Activity-Feed existiert nicht |
| Morning Check-in | Freitext, Vitalwerte, Termine | A, 1:1 aus `CheckinCreate` |
| Daily Plan | Prioritäten, Zeitblöcke, "Set aside" | A, 1:1 aus `DailyPlan` |
| Daily Review | Abend-Vitalwerte, Erledigt/Nicht/Carry-over, Reflexion | A, 1:1 aus `ReviewCreate` |
| Operator-Liste | Work Orders mit Status/Repo/Zeit | A, 1:1 aus `WorkOrder` |
| Work Order Detail | Lifecycle, Execution Plan, Approval Scope | A, 1:1 — **aber** `LocalRunnerPanel`/`RunnerPromptPanel`/`SafetyRulesPanel` fehlen im Design |
| Agent Run | Rolle, Status, Input/Output-Summary, Modell, Attempt | A, 1:1 aus `AgentRun` |
| Review Package | Summary, Artefakte, Accept/Request rework | A für Inhalt/Aktionen; **B** für das "Risk: Low"-Badge (echtes Feld ist `risks: string[]` Freitext, kein Level — Badge muss aus der Liste abgeleitet oder das Feld erweitert werden) |
| Settings | Account, Sprache (EN/DE), KI-Modell | A, 1:1 |

**Wichtigster Einzelfund:** Die "Approve/Reject einzelner Entscheidungen"-
Erzählung auf Home ist die visuelle Vorwegnahme von JARVIS-C1 (Command
Layer). Ohne diesen Layer zeigt Home in der Realität nur Work-Order-Status
und Second-Brain-Signale — keine granularen Einzelentscheidungen. Das MUSS
vor Phase C explizit entschieden werden (entweder Command Layer zuerst
bauen, oder Home v1 ohne "Needs your decision" launchen und das Panel erst
mit C1 aktivieren).

## 4. Component Map

| Neu (Foundation) | Ersetzt | Bleibt wiederverwendbar |
|---|---|---|
| `IconRail` | `Sidebar.tsx` (Textlabel-Variante) | `Card`, `Button`, `Input`, `Badge`, `Spinner`/`EmptyState` (Farb-Tokens ändern sich, API bleibt) |
| `JarvisRail` (collapsed/normal/expanded) | `JarvisChat.tsx`s Bubble-Layout (Logik bleibt, Darstellung wird Content-Flow) | `ProjectsManager`-Datenlogik (Fetch/Create/Update), `WorkOrderDetail`-Datenlogik, `LifecycleControls`-Statemachine-Buttons |
| `Workspace`-Grid-Container | `AppShell.tsx`s Sidebar+main-Struktur | `OperatorManager`s Mock-Fallback-Muster (Banner-Text wiederverwenden) |
| `ApprovalCard` (generisches Primitiv) | — (neu, kein Vorgänger) | `LocalRunnerPanel`, `RunnerPromptPanel`, `SafetyRulesPanel` (unverändert einhängen) |
| `ProjectDetailView` | — (neu) | `ExecutionPlan`, `StatusFlowStrip` (nur Styling anpassen) |

## 5. Route Map

| Route heute | Route Ziel | Änderung |
|---|---|---|
| `/dashboard` | `/dashboard` | Inhalt auf Briefing-Sections umgestellt |
| `/jarvis` | `/jarvis` | Wird zum "expanded"-Zustand der globalen Jarvis Rail, keine isolierte Seite mehr |
| `/morning` | `/morning` | Nur Shell-Wechsel |
| `/plans/[id]` | `/plans/[id]` | Nur Shell-Wechsel |
| `/review` | `/review` | Nur Shell-Wechsel |
| `/projects` | `/projects` | Nur Shell-Wechsel |
| — | **`/projects/[id]`** | **Neu** |
| `/operator` | `/operator` | Nur Shell-Wechsel |
| `/operator/new` | `/operator/new` | Nur Shell-Wechsel |
| `/operator/[id]` | `/operator/[id]` | Shell-Wechsel + Ergänzung um Approval-Primitiv-UI für `review_ready` |
| `/rules` | `/rules` (unter Settings-Icon erreichbar) | Nur Navigations-Zuordnung |
| `/settings` | `/settings` | Nur Shell-Wechsel |

## 6. State Ownership

- **Jarvis Layout-State** (`collapsed`/`normal`/`expanded`): Client-State auf
  Shell-Ebene (z. B. `AppShell`/Context), nicht pro Route neu — überlebt
  Navigation, damit "collapsed" auf Mobile-Home und "expanded" auf
  Jarvis-Route konsistent bleibt.
- **Workspace-Inhalt bei Jarvis-Expansion**: bleibt gemountet (CSS Grid
  Spaltenbreite ändert sich, keine Conditional-Unmounts) — Formular-/Scroll-
  Zustand geht nicht verloren, wie in Phase 6 gefordert.
- **Jarvis Route Context** (`surface`, `entity_id`): pro Seite lokal erzeugt
  (z. B. `usePathname()`-Ableitung in der Jarvis-Rail-Komponente), nur als
  Identifier ans Backend gesendet — niemals Entity-Daten selbst.
- **Approval-Entscheidungen**: State lebt im jeweiligen Domain-Objekt
  (Work-Order-Status), das generische `ApprovalCard`-Primitiv ist zustandslos
  (bekommt Props, ruft eine Callback-Funktion auf) — keine eigene
  Datenhaltung.

---

## 7. Migrationsphasen A–H

### PHASE A — Foundation

1. **Dateien betroffen**: `frontend/app/globals.css`, `frontend/tailwind.config.ts`.
2. **Neu**: keine neuen Dateien, nur Token-Werte.
3. **Wiederverwendet**: JARVIS-D1s drei-Ebenen-CSS-Custom-Property-Struktur
   (`--bg-*`, `--text-*`, `--border-*`, `--interactive-*`) — Werte werden auf
   Bronze/Copper + die im Design-System-Board dokumentierten Graphit-Töne
   umgestellt.
4. **Backend-Änderungen**: keine.
5. **Migrationen**: keine.
6. **Tests**: `npm run type-check`, `npm run lint` (keine visuelle Regression
   messbar ohne UI, die die Tokens nutzt — folgt in Phase B).
7. **Browser-Akzeptanz**: `/design-preview`-artige isolierte Testseite (wie
   in JARVIS-D1 Phase 3 bereits etabliert), Vergleich der Farbwerte gegen
   `04-design-system/01-brand-color.png`.
8. **Higgsfield-Referenz**: `04-design-system/01-brand-color.png`,
   `02-typography.png`.
9. **Rollback/Risiko**: niedrig — reine Variablen-Änderung, betrifft noch
   keine Route sichtbar, solange Komponenten weiter alte Klassen nutzen.
10. **STOP-Gate**: Token-Werte gegen Design-System-Board von Serkan
    freigeben lassen, bevor irgendeine Komponente sie nutzt.

### PHASE B — Global Shell

1. **Dateien**: `components/layout/AppShell.tsx`, `Sidebar.tsx`,
   `MobileNav.tsx` (neu strukturiert), neue `components/layout/IconRail.tsx`,
   `components/layout/JarvisRail.tsx`, `components/layout/Workspace.tsx`.
2. **Neu**: `IconRail`, `JarvisRail` (mit 3 Layout-States), `Workspace`-
   Grid-Container, ein Jarvis-Expansion-State-Hook/-Context.
3. **Wiederverwendet**: `ProtectedRoute` aus `lib/auth.tsx` unverändert,
   bestehende Routing-Struktur.
4. **Backend**: keine.
5. **Migrationen**: keine.
6. **Tests**: `type-check`, `lint`; manueller Klick-Test aller 5
   Icon-Ziele plus Jarvis-Expand/Collapse.
7. **Browser-Akzeptanz**: Desktop 1280px+, kein horizontales Scrollen;
   Mobile ~375-500px, Bottom-Nav + Jarvis-FAB + Fullscreen-Overlay;
   `prefers-reduced-motion` respektiert bei der Expansion-Animation.
8. **Higgsfield-Referenz**: `04-design-system/03-layout.png`,
   `08-mobile.png`, `03-selected-master/*` (alle 12 Bilder als
   Shell-Referenz).
9. **Rollback/Risiko**: **hoch** — betrifft jede einzelne Route gleichzeitig
   (AppShell ist der gemeinsame Rahmen). Ein Fehler hier bricht das ganze
   Produkt, nicht nur eine Seite.
10. **STOP-Gate**: Shell auf einer einzigen echten Route (z. B. Settings,
    geringste Komplexität) im Browser zeigen, erst dann auf alle Routen
    ausrollen.

### PHASE C — Home

1. **Dateien**: `app/dashboard/page.tsx`, `components/dashboard/*` (CommandHero,
   SignalNoisePanel, ProjectRadar, DailyCommandTimeline, WeeklyMomentum
   werden ersetzt/umgebaut), `app/morning/page.tsx`, `app/plans/[id]/page.tsx`,
   `app/review/page.tsx` (nur Shell-Einbindung, Inhalt bleibt).
2. **Neu**: Briefing-Section-Komponenten (`TodaySection`,
   `NeedsDecisionSection` **nur falls JARVIS-C1-Entscheidung getroffen**,
   `InProgressSection`, `RecentActivitySection`).
3. **Wiederverwendet**: `CheckinForm`, `PlanView`, `ReviewForm` unverändert
   (nur neue Shell drumherum).
4. **Backend**: keine für Morning/Plan/Review. **Für "Needs your decision"**:
   abhängig von JARVIS-C1-Entscheidung — wenn ja, neuer Endpunkt nötig.
5. **Migrationen**: keine, außer Command-Layer-Entscheidung fällt für Phase C.
6. **Tests**: bestehende Backend-Tests unverändert (kein Endpunkt geändert),
   Frontend type-check/lint.
7. **Browser-Akzeptanz**: mit echtem Account — leerer Tag (kein Plan),
   gefüllter Tag, viele Projekte, wenig Projekte.
8. **Higgsfield-Referenz**: `05-pages/01-home-desktop.png`,
   `06-mobile/01-home-mobile.png`, `05-pages/05-07` (Morning/Plan/Review).
9. **Rollback/Risiko**: mittel — Dashboard ist die erste Seite nach Login,
   Fehler sind sofort sichtbar; "Needs your decision" ohne echte Daten wäre
   ein Rückfall in vorgetäuschte Funktionalität.
10. **STOP-Gate**: Serkan entscheidet VOR Phase C explizit, ob "Needs your
    decision" in v1 entfällt oder JARVIS-C1 vorgezogen wird.

### PHASE D — Jarvis

1. **Dateien**: `components/jarvis/JarvisChat.tsx` (Darstellung auf
   Content-Flow umgestellt, Logik unverändert), `app/jarvis/page.tsx`
   entfällt als eigene Seite oder wird zum expliziten "expanded"-Deep-Link,
   `backend/app/routers/jarvis.py`, `backend/app/services/vault_service.py`
   (neue Funktion für Route-Context), `backend/app/prompts/jarvis_chat.py`
   (Prompt-Erweiterung um Entity-Kontext-Block), `backend/app/models/jarvis.py`
   (`JarvisChatRequest` um optionale `surface`/`entity_id`-Felder erweitern).
2. **Neu**: `get_entity_context_for_surface(surface, entity_id, user_id)`
   in einem neuen oder bestehenden Service — validiert Ownership
   (gleiches Muster wie `require_owned_record()`), lädt die reale Entity,
   baut einen Kontext-Block analog zu `vault_service`.
3. **Wiederverwendet**: komplette bestehende Second-Brain-Pipeline,
   `usage_service`-Kostendeckel unverändert.
4. **Backend-Änderungen**: `JarvisChatRequest` erweitert (rückwärtskompatibel,
   Felder optional), ein neuer Service-Funktions-Pfad, Prompt-Bau erweitert.
5. **Migrationen**: keine (kein neues DB-Schema nötig, wenn `surface`/
   `entity_id` nur zur Laufzeit aufgelöst werden, nicht persistiert).
6. **Tests**: neue Backend-Tests analog `test_vault_service.py`/
   `test_jarvis_chat_prompt.py` für Ownership-Verweigerung (fremder
   `entity_id` → leerer Kontext, kein Datenzugriff) und für korrekte
   Kontext-Injection.
7. **Browser-Akzeptanz**: Frage auf `/projects/[id]` stellen, die nur mit
   Projekt-Kontext beantwortbar ist ("Was blockiert das?"); gleiche Frage
   ohne Kontext (z. B. auf Settings) muss ehrlich "weiß ich nicht" sagen.
8. **Higgsfield-Referenz**: `05-pages/02-jarvis-expanded-desktop.png`,
   `06-mobile/02-jarvis-mobile.png`, `04-design-system/05-jarvis.png`.
9. **Rollback/Risiko**: mittel-hoch — jede Ownership-Lücke hier ist ein
   echtes Datenleck-Risiko (falscher `entity_id` liefert fremde Daten).
   Muss mit derselben Sorgfalt wie `require_owned_record()` geprüft werden.
10. **STOP-Gate**: Sicherheits-/Ownership-Review der neuen Kontext-Funktion,
    bevor sie live geschaltet wird — unabhängig vom Design-Review.

### PHASE E — Projects

1. **Dateien**: `app/projects/page.tsx`, `components/projects/ProjectsManager.tsx`
   (Shell-Wechsel, Inline-Edit bleibt bestehen), neue `app/projects/[id]/page.tsx`,
   neue `components/projects/ProjectDetail.tsx`.
2. **Neu**: `ProjectDetail`-Komponente. **Muss vor Bau entscheiden**: entweder
   `owner`/`due_date` als neue optionale `Project`-Felder ergänzen (Backend +
   Migration) oder aus der Detailansicht entfernen. Activity-Feed für ein
   Projekt existiert nicht — entweder weglassen oder aus Work-Order-Referenzen
   ableiten (`repo`/`project`-Verknüpfung existiert heute nicht strukturiert).
3. **Wiederverwendet**: `api.projects.get/update` (bereits vorhanden für
   Inline-Edit), `ProjectStatus`/`ProjectPriority`-Badges 1:1.
4. **Backend**: **nur falls** `owner`/`due_date` beschlossen werden — neue
   optionale Spalten + `ProjectUpdate`-Erweiterung.
5. **Migrationen**: **nur falls** obiges beschlossen wird —
   `supabase/migrations/013_project_owner_due_date.sql`, idempotent mit
   `IF NOT EXISTS`.
6. **Tests**: bestehende Projekt-Tests (falls vorhanden) erweitern; sonst
   manueller Test von Create/Update/Delete unverändert.
7. **Browser-Akzeptanz**: Navigation Liste→Detail→zurück, Inline-Edit in der
   Liste funktioniert weiterhin parallel zur neuen Detailroute.
8. **Higgsfield-Referenz**: `05-pages/03-projects-desktop.png`,
   `04-project-detail-desktop.png`, `06-mobile/03-projects-mobile.png`.
9. **Rollback/Risiko**: niedrig — additive neue Route, bestehende
   Funktionalität bleibt unberührt, solange Inline-Edit nicht entfernt wird.
10. **STOP-Gate**: Serkan entscheidet über `owner`/`due_date` (echte neue
    Felder vs. aus der Detailansicht streichen), bevor `ProjectDetail`
    gebaut wird.

### PHASE F — Activity (Operator / Work Orders / Agent Runs / Review Packages)

1. **Dateien**: `app/operator/*`, `components/operator/*` (Shell-Wechsel;
   `WorkOrderDetail.tsx` bekommt neue `ApprovalCard`-Integration für
   `review_ready`), neue `components/approval/ApprovalCard.tsx` (generisch).
2. **Neu**: `ApprovalCard` — Props: `subject, action, scope, reason,
   riskLevel?, consequenceSummary?, onApprove, onReject`. Wird in
   `WorkOrderDetail` für `review_ready` (Accept/Request rework) verwendet UND
   perspektivisch für `JarvisSuggestedAction` (sobald C1 kommt).
3. **Wiederverwendet**: `LifecycleControls`-Statemachine **unverändert** (nur
   visuell an `ApprovalCard` angepasst, keine neue Backend-Logik),
   `ExecutionPlan`, `StatusFlowStrip`, `LocalRunnerPanel`, `RunnerPromptPanel`,
   `SafetyRulesPanel` **unverändert eingehängt** (im Focus-Deck-Design bisher
   fehlend — muss ergänzt werden, siehe Abschnitt 3).
4. **Backend**: keine Änderung an der Statemachine selbst. **Optional**:
   `risk_level`/`consequence_summary` als neue optionale Felder auf
   `ApprovalScope` oder `WorkOrder`, falls das generische Primitiv Risiko
   auch für Work Orders zeigen soll (Serkans Vorgabe: "Work Orders müssen
   NICHT zwingend risk_level besitzen" — also keine Pflichtmigration).
5. **Migrationen**: nur falls obiges Feld beschlossen wird — additiv,
   optional, kein Pflichtfeld.
6. **Tests**: bestehende `test_work_order_transitions.py` unverändert
   (Statemachine nicht angefasst); neuer Komponententest/manueller Test für
   `ApprovalCard` mit und ohne `riskLevel`.
7. **Browser-Akzeptanz**: alle 9 `WorkOrderStatus`-Werte durchklicken,
   `LocalRunnerPanel`/`RunnerPromptPanel`/`SafetyRulesPanel` weiterhin
   sichtbar und funktionsfähig.
8. **Higgsfield-Referenz**: `05-pages/08-12` (Operator/Work Order/Agent
   Run/Review Package), `06-mobile/05-07`, `04-design-system/06-workorders-
   agents.png`.
9. **Rollback/Risiko**: mittel — `WorkOrderDetail` ist die komplexeste
   bestehende Komponente (429 Zeilen, viele Abschnitte); Risiko liegt darin,
   beim Shell-Umbau eine der drei "fehlenden" Panels versehentlich
   wegzulassen statt bewusst zu integrieren.
10. **STOP-Gate**: Review, dass `LocalRunnerPanel`/`RunnerPromptPanel`/
    `SafetyRulesPanel` tatsächlich im neuen Layout vorhanden und nicht nur
    "vergessen" sind, bevor die alte Darstellung entfernt wird.

### PHASE G — Settings

1. **Dateien**: `app/settings/page.tsx`, `app/rules/page.tsx`,
   `components/rules/RulesManager.tsx` (nur Shell-Wechsel + Navigations-
   Zuordnung unter Settings-Icon).
2. **Neu**: keine neuen Komponenten, nur Navigations-Konsolidierung
   (Rules ist jetzt über Settings statt eigenes Icon erreichbar — braucht
   einen sichtbaren Link/Tab innerhalb der Settings-Workspace-Ansicht).
3. **Wiederverwendet**: `RulesManager`, Settings-Formular unverändert.
4. **Backend**: keine.
5. **Migrationen**: keine.
6. **Tests**: type-check/lint.
7. **Browser-Akzeptanz**: Settings→Rules-Navigation funktioniert, Sprachwahl
   EN/DE weiterhin korrekt.
8. **Higgsfield-Referenz**: `05-pages/12-settings-desktop.png`.
9. **Rollback/Risiko**: niedrig.
10. **STOP-Gate**: keins zwingend nötig — geringste Komplexität dieser
    Migration, kann auch vorgezogen werden.

### PHASE H — Final Polish

1. **Dateien**: repo-weit — kein neuer Funktionsumfang, nur Härtung.
2. **Neu**: keine.
3. **Wiederverwendet**: alles.
4. **Backend**: keine.
5. **Migrationen**: keine.
6. **Tests**: vollständiger `scripts/check.ps1`-Lauf, alle Browser-
   Akzeptanz-Flows aus A–G erneut, DE **und** EN durchklicken.
7. **Browser-Akzeptanz**: Desktop + Mobile, alle States (empty/loading/
   error/awaiting approval/in progress/blocked/failed/completed) an
   mindestens einer Stelle real ausgelöst, kein horizontales Scrollen,
   sichtbarer Tastaturfokus.
8. **Higgsfield-Referenz**: gesamtes Set als visueller Soll-Abgleich,
   `07-final-review/phase6-review.md` als Konsistenz-Checkliste.
9. **Rollback/Risiko**: niedrig (reine Härtung), aber hoher Aufwand, wenn
   in A–G Abkürzungen genommen wurden.
10. **STOP-Gate**: finale Freigabe durch Serkan vor Merge nach `main`.

---

## 8. Backend/API-Abhängigkeiten

- **Phase D** braucht neue, aber additive `JarvisChatRequest`-Felder
  (`surface?`, `entity_id?`) — kein Breaking Change.
- **Phase E** braucht **optional** neue `Project`-Felder (`owner`,
  `due_date`) — nur falls Serkan das für Project Detail bestätigt.
- **Phase F** braucht **optional** neue Felder für Risiko-Darstellung auf
  Work-Order-Ebene — nur falls das generische Approval-Primitiv das
  einheitlich zeigen soll.
- **JARVIS-C1 (Command Layer)** ist keine Abhängigkeit dieses Plans per se,
  aber Phase C ("Needs your decision") kann ohne ihn nicht ehrlich gebaut
  werden — siehe STOP-Gate Phase C.

## 9. Teststrategie

- `scripts/check.ps1` nach jeder Phase (Backend-Pytest + Type-Check + Lint).
- Neue Backend-Tests für Phase D (Ownership-Verweigerung, Kontext-Injection)
  nach dem Muster von `test_vault_service.py`/`test_daily_plan_vault_context.py`.
- Kein Pixel-perfekter Screenshot-Test — stattdessen visueller Abgleich
  gegen die Higgsfield-Referenzbilder als manuelle Browser-Prüfung pro
  Phase (wie in `manual-e2e-checklist.md` bereits etabliert).
- Browser-Smoke-Test-Matrix pro Phase: Desktop (≥1280px) + Mobile (~375–
  500px, echter Viewport wie in Phase 4/6 dieser Design-Session, da
  Browser-Automatisierung `resize_window` bekanntlich wirkungslos bleibt),
  kein horizontales Scrollen, authentifiziert gegen echtes Backend, DE und
  EN Sprachumschaltung.
- Approval-Primitiv (Phase F) bekommt eigene Tests für Statemachine-
  Konformität — es darf niemals einen Übergang anbieten, den
  `TRANSITIONS` in `LifecycleControls.tsx` nicht ohnehin erlaubt.

## 10. Risiken

1. **JARVIS-C1-Abhängigkeit von Home** — größtes Risiko, siehe Abschnitt 3/7C.
2. **Phase B (Global Shell) hat Blast-Radius = ganzes Produkt** — jeder
   Fehler ist sofort überall sichtbar.
3. **Phase D Ownership-Bugs** — Sicherheitsrisiko, nicht nur UX.
4. **Bronze-vs-Warning-Kontrast** — echter Farbabstand/WCAG-Check nötig,
   nicht durch weitere Bilder lösbar (aus Phase 6 übernommen).
5. **Drei bestehende Operator-Panels vergessen** (`LocalRunnerPanel`,
   `RunnerPromptPanel`, `SafetyRulesPanel`) — realer Funktionsverlust, wenn
   beim Shell-Umbau übersehen.
6. **Fünf-Icon-Navigation verliert Sichtbarkeit für Rules/Morning/Review** —
   Nutzer könnten diese Funktionen schwerer wiederfinden; braucht gute
   Sekundär-Navigation innerhalb von Home/Settings.

## 11. Abnahme-Gates

Nach jeder Phase A–H: `scripts/check.ps1` grün, manueller Browser-Flow auf
Desktop + Mobile mit echtem Backend, DE+EN geprüft, Vergleich gegen die
zugehörigen Higgsfield-Referenzbilder, explizite Freigabe durch Serkan vor
der nächsten Phase. Phase C und Phase D haben zusätzliche, oben benannte
Sonder-Gates (Command-Layer-Entscheidung bzw. Sicherheits-Review).

## 12. Empfohlene Branch-/Worktree-Strategie

**Neuer Worktree**, nicht `cp-design` weiterverwenden — `cp-design`s Phase-4-
Änderungen (Steel-Blue-Jarvis-Umbau) wurden von Serkan explizit verworfen;
ein neuer Branch vermeidet, verworfene Commits versehentlich wieder
einzuschleppen. Vorschlag:

```
Branch: feat/focus-deck  (von main, af05d16)
Worktree: C:\Users\serka\dev\cp-focus-deck
```

Die JARVIS-D1-Token-*Technik* (dreistufige CSS-Custom-Properties) ist es
wert, aus `cp-design`s `globals.css` als Startpunkt zu **kopieren** (nicht
zu mergen) und dann auf Bronze/Copper umzuwerten — das vermeidet, die
verworfene Steel-Blue-Historie mitzuziehen, nutzt aber die bereits
durchdachte Struktur. `cp-multiagent` (JARVIS-M1) bleibt komplett unberührt,
da inhaltlich unabhängig.

Innerhalb von `feat/focus-deck`: ein Commit pro abgeschlossener Phase
(A–H), jeweils erst nach dem zugehörigen STOP-Gate. Kein Merge nach `main`
vor Abschluss von Phase H und Serkans finaler Freigabe.
