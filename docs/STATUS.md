# STATUS — CommandPilot / Jarvis

Letzte Aktualisierung: 20.09.2026 (Focus Deck Slice 2 Stand).
Diese Datei ist der Einstieg. Wer hier anfängt, weiß, wo alles steht.

## Wo die Stränge stehen

| Strang | Ort | Branch | Stand | Nächster Schritt |
|---|---|---|---|---|
| main | dev/commandpilot | main | A1 fertig, 39 Tests grün | unverändert, Basis für Focus Deck |
| Design D1 (Steel-Blue) | dev/cp-design | feat/design-system | Phase 4 implementiert, danach von Serkan **verworfen** — nicht committen/mergen | ersetzt durch Focus Deck |
| Multiagent M1 | dev/cp-multiagent | feat/multiagent | Phase 0 BESTANDEN | Activity-Log-Bug fixen, dann Phase 1 |
| **Focus Deck (Bronze)** | dev/cp-focus-deck | feat/focus-deck-v2 | Design vollständig LOCKED, **Slice 1 fertig (committet), Slice 2 (globale Shell-Migration) implementiert und QA-geprüft, noch nicht committet** | siehe unten |
| Jarvis Q1 (Qualitätsnetz) | dev/cp-command-layer | feat/jarvis-command-layer | done, committet (`8afeb9e`) | — |
| Jarvis C1 (Command Layer) | dev/cp-command-layer | feat/jarvis-command-layer | **done** — echte Browser-Abnahme (Flow A/B/C + Idempotenz) bestanden, `scripts/check.ps1` grün (61 Backend-Tests inkl. Q1), noch nicht committet | Abnahme durch Serkan, dann committen |

**Zielrichtung**: "Focus Deck" (Graphit + Bronze/Copper, permanente
Jarvis-Spalte, fünf-teilige Icon-Navigation) ersetzt die verworfene
Steel-Blue-Richtung aus JARVIS-D1. Design-Referenzen liegen außerhalb des
Git-Repos unter `C:\Users\serka\dev\commandpilot-design-v2\` — nie
committen. Vollständiger Implementierungsplan:
`docs/design/commandpilot-focus-deck-implementation-plan.md`.

**Jarvis C1 — done, echte Browser-Abnahme bestanden** (2026-09-20, echtes
Backend/Auth/Supabase/OpenAI, kein Mock): Ziel im Chat → genau zwei
`suggested_actions` (strukturiertes JSON aus einem OpenAI-Call, reply +
suggested_actions, gleiches Strict-Schema-Muster wie `daily_plan.py`) →
Karten mit Bestätigen/Ablehnen im Chat-UI → Bestätigen legt über
`work_order_service` eine echte Work Order + Approval Scope + Activity-Log an,
Ablehnen legt nichts an, aber einen Audit-Eintrag in der Tabelle
`suggested_action_decisions` (Migration `013`, in Supabase ausgeführt und
verifiziert). Idempotenz nicht nur clientseitig, sondern serverseitig mit
zwei echten gleichzeitigen Confirm-Requests (identisches `request_id`, via
`Promise.all`) geprüft — genau eine Work Order, kein Duplikat. Drei echte
Chat-Durchläufe im Browser: Flow A (Vorschlag ablehnen → keine Work Order,
Reject-Audit vorhanden), Flow B (Vorschlag bestätigen → Work Order + Scope +
Activity-Log, sichtbar im Operator), Flow C (neuer Chat, beide Vorschläge
bestätigen → zwei neue Work Orders). Insgesamt 5 echte Work Orders während
der Abnahme erzeugt (17→22), alle nachvollziehbar. Q1-Fall-10 angepasst:
Vorschläge dürfen entstehen, der Chat-Endpunkt selbst schreibt aber nie eine
Work Order. `scripts/check.ps1` grün, Q1 (10/10) weiterhin grün.

**Implementierungsstand (ehrlich, kein "done"-Claim über Serkans Freigabe
hinaus)**:

- **Slice 1** (Design-Foundation-Tokens + `FocusDeckShell` + Settings als
  erste migrierte Route) ist fertig, von Serkan abgenommen und committet
  (`76881a8`, "feat: introduce focus deck foundation and settings shell").
- **Slice 2** (globale Shell-Migration: alle authentifizierten Routen —
  Dashboard, Jarvis, Projects, Morning, Daily Plan, Daily Review, Operator/
  Work Orders, Rules, Settings — laufen jetzt unter einem gemeinsamen
  `app/(app)/layout.tsx`, das genau eine `FocusDeckShell`-Instanz über
  Routenwechsel hinweg hält) ist implementiert und QA-geprüft (Desktop +
  Mobile, Jarvis-State-Persistenz über Routenwechsel bestätigt), aber noch
  **nicht committet, nicht gepusht, nicht gemerged** — wartet auf Serkans
  Freigabe. Kein Redesign der Page-Inhalte in diesem Slice, nur
  Shell-Migration. `AppShell.tsx`/`Sidebar.tsx`/`MobileNav.tsx` existieren
  im Repo weiter (bewusst nicht gelöscht), werden aber inzwischen von
  keiner Route mehr importiert.

## Was heute erreicht wurde

- Ein Trunk statt drei Ständen, alles auf GitHub
- Jarvis v1 live: Chat mit Second-Brain-Kontext und Quellen, im Browser bestätigt
- A1 durch: Vault an Eigentümer gebunden, Unicode-Fehler, Budget-Deckel,
  Quellen entrauscht, check.ps1 als gemeinsamer Prüfbefehl
- Design: Token-Architektur in drei Ebenen, Interaktionsmatrix, /design-preview
- M1 Phase 0 bestanden: Agent hat multiply + test_multiply geschrieben,
  pytest scheiterte an der Umgebung, Agent meldete korrekt blocked/needs_fix

## Entscheidungen, die stehen

- Akzentfarbe: Steel-Blue, Interaktionszustände auf brand-400/500
- Schrift: Inter + JetBrains Mono, System-Stack als Fallback
- Drei Farbfamilien: Akzent (Aktion), Status (Zustand), Kategorie (Lebensbereich)
- Freigaben bleiben in der Oberfläche, nie als CLI-Flag
- API-Token nie in einen Agent-Kontext, Serkan startet Runner selbst
- Ein Clone unter dev, Worktrees für Parallelarbeit, iCloud nur als Backup
- Sessions pushen nie und mergen nie nach main — das macht Serkan nach Abnahme

## Offene Befunde

| Befund | Wo | Priorität |
|---|---|---|
| Activity-Log: Step-IDs im Feld agent_run_id (8 Fehlschläge) | import_work_order_result.py | M1, sofort |
| Fixture hat keine Testumgebung, Agent findet kein pytest | cp-e2e-fixture | M1 Phase 2 |
| Step-Status wird bei technischem Fehlschlag nicht zurückgesetzt | M1 Phase 4 | mittel |
| claude-CLI überschreitet --max-budget-usd um ~100 % | eigener Auftrag später | vor Phase 3 relevant |
| /operator/new verliert Formularzustand | UI | offen |
| A1-Browsertest nie durchgeführt | — | offen, 5 Minuten |
| Notion sagt CommandPilot "Wartet"/P3, Vault sagt active | Notion | klein |

## Wie man morgen einsteigt

1. Diese Datei lesen
2. `git log --oneline -10` in jedem Worktree
3. Die jüngste Datei in `docs/übergaben/` des jeweiligen Strangs
4. Dann erst arbeiten
