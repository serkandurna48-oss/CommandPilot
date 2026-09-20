# STATUS — CommandPilot / Jarvis

Letzte Aktualisierung: 20.09.2026.
Diese Datei ist der Einstieg. Wer hier anfängt, weiß, wo alles steht.

## Wo die Stränge stehen

| Strang | Ort | Branch | Stand | Nächster Schritt |
|---|---|---|---|---|
| main | dev/commandpilot | main | A1 fertig, 39 Tests grün | unverändert, Basis für Focus Deck |
| Design D1 (Steel-Blue) | dev/cp-design | feat/design-system | Phase 4 implementiert, danach von Serkan **verworfen** — nicht committen/mergen | ersetzt durch Focus Deck |
| Multiagent M1 | dev/cp-multiagent | feat/multiagent | Phase 0 BESTANDEN | Activity-Log-Bug fixen, dann Phase 1 |
| **Focus Deck (Bronze)** | dev/cp-focus-deck | feat/focus-deck-v2 | Design vollständig LOCKED, **Implementierung Slice 1 läuft gerade** | siehe unten |

**Zielrichtung**: "Focus Deck" (Graphit + Bronze/Copper, permanente
Jarvis-Spalte, fünf-teilige Icon-Navigation) ersetzt die verworfene
Steel-Blue-Richtung aus JARVIS-D1. Design-Referenzen liegen außerhalb des
Git-Repos unter `C:\Users\serka\dev\commandpilot-design-v2\` — nie
committen. Vollständiger Implementierungsplan:
`docs/design/commandpilot-focus-deck-implementation-plan.md`.

**Implementierungsstand (ehrlich, kein "done"-Claim)**: Slice 1
(Design-Foundation-Tokens + neue Shell-Komponente + Settings als erste
migrierte Route) ist in Arbeit im Worktree `cp-focus-deck`. Noch nicht
committet, noch nicht gepusht, noch nicht gemerged. Alle anderen Routen
(Home, Jarvis, Projects, Operator) laufen unverändert auf der alten
AppShell weiter, bis sie in späteren Slices migriert werden.

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