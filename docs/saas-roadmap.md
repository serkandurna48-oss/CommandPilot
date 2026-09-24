# CommandPilot — SaaS-Roadmap (23.09.2026, aktualisiert nach Live-Verifikation)

Ersetzt die historische v0.2/v0.3-Roadmap als aktive Priorisierung. Ziel:
Anmelden → Workspace → Projekte/Kontext → mit Jarvis priorisieren → Auftrag
freigeben → Ausführung + Ergebnis nachvollziehen — für Serkan zuerst, dann
3–5 eingeladene Tester.

**Dieser Stand ersetzt die vorherige Version desselben Dokuments**, die vor
Migration 017 und vor einem echten Livelauf geschrieben wurde. Alles unten
ist entweder live gegen das echte System verifiziert (mit Nachweis) oder
explizit als offen/simuliert markiert — keine Statusangabe ohne Beleg.

## Architekturentscheidung: Web-Kern + optionaler lokaler Runner (Kombination B+A)

Unverändert gegenüber der letzten Fassung: Web-Kern läuft vollständig
serverseitig (Auth, Projects, Daily Planner, Jarvis-Chat + Kontext, Command
Layer). Echte Codeausführung braucht einen lokalen Runner — es gibt keine
Cloud-Ausführungsumgebung. Für Codeausführung: geführtes Pairing (`--pair`,
Settings → "Runner verbinden", `supabase/migrations/017_runner_connections.sql`).

**Neue, live entdeckte Einschränkung**: `scripts/run_work_order_daemon.py`s
Autonom-Polling-Pfad (`--daemon`-Modus, ausgelöst über "Autonom starten")
berechnet `REPO_ROOT` über `Path(__file__).resolve().parent.parent` — das
ist **immer** CommandPilots eigenes Repo, unabhängig vom `cwd`, mit dem der
Daemon gestartet wird, und unabhängig von `target_repo_path` (das laut Code
ohnehin nur Prompt-/Anzeige-Kontext ist). Der Daemon kann also aktuell
**strukturell keine Work Order gegen ein externes Zielrepo ausführen** —
nur `scripts/run_work_order.py` direkt, manuell mit passendem `cwd`
aufgerufen, kann das (siehe Stufe-1-Tabelle unten, dort real so verifiziert).
Nicht in dieser Session behoben — reale Architekturgrenze, die vor einem
echten Multi-Repo-Autonomiebetrieb gelöst werden muss.

## Stufe 1 — Durchgängiger Eigenbetrieb über die Oberfläche

| Ablaufschritt | Status | Beleg / Lücke |
|---|---|---|
| Login/Workspace | Implementiert, verifiziert | — |
| Projekte anlegen/bearbeiten, Persistenz | Implementiert, verifiziert | — |
| Jarvis berücksichtigt Projekte/Kalender/Notion | Implementiert, verifiziert (für den Owner) | Bis 23.09.2026 fälschlich für **jeden** Nutzer, siehe Stufe 2 |
| Jarvis → Vorschlag → Work Order (Draft) | Implementiert, teilweise verifiziert | Ein real bestätigter Vorschlag existiert und ist stabil (`803718c0-...`, Status `draft`, live über Refresh geprüft). **Neu gefunden**: GPT-4o liefert bei mehreren realen Testnachrichten wiederholt nur EINEN statt der geforderten zwei `suggested_actions` — das serverseitige "zwei-oder-keins"-Invariant greift korrekt (`ai_service.py` verwirft und loggt), aber der sichtbare Effekt ist, dass der Vorschlag dem Nutzer gar nicht erst angezeigt wird. Kein Fix in dieser Session (Promptverhalten, kein Bug im engeren Sinn) — als UX-Robustheitslücke für die Roadmap vorgemerkt. |
| Runner-Pairing (`--pair`) | **Implementiert, live end-to-end verifiziert** | Code generiert → im Browser (eigene, bereits authentifizierte Sitzung) bestätigt → Verbindung aktiv, übersteht Refresh, per Token real authentifiziert. **Dabei 3 echte Bugs gefunden und gefixt** (siehe "In dieser Session behobene Bugs" unten). |
| Work Order → echte Ausführung → Ergebnis | **Teilweise, echt getestet** | Echte, isolierte Work Order über den gepaarten Runner-Token direkt mit `run_work_order.py` (cwd = eigenständiges Test-Repo außerhalb von CommandPilot) ausgeführt — Auth, Statemachine, Budget-Tracking, Retry-Logik liefen alle real durch. Der `claude`-CLI-Call selbst scheiterte real am zu knapp gewählten `--max-budget-usd 0.30` (tatsächliche Kosten: $0.53, "Reached maximum budget" nach nur einem Turn) — auf Nutzerentscheidung hin **kein weiterer bezahlter Retry**. Die eigentliche Aufgabenerfüllung (HTML-Datei erzeugen) ist damit **nicht** verifiziert, die Ausführungs-/Auth-/Kostenkontroll-Mechanik schon. |
| Genau eine Work Order pro Bestätigung (kein Duplikat) | **Implementiert, live unter echter Nebenläufigkeit verifiziert** | 5 gleichzeitige `confirm`-Requests mit identischer `request_id` (echter Race, kein Mock) → exakt eine Work Order in der DB, 4× korrekt `already_decided: true`. Abgesichert durch echten `UNIQUE(user_id, request_id)`-Index, nicht nur Anwendungslogik. |
| Widerruf blockiert Runner-Zugriff | **Implementiert, live verifiziert** | Vor dem Fix: widerrufener Token → HTTP 500 (echter Crash). Nach dem Fix: sauberes 401. Live mit echtem, zuvor gepaartem Token reproduziert. |
| Browser-Refresh verliert nichts | **Neu real getestet, ein echter Bug gefunden und gefixt** | Operator-Detailseite fiel bei einem echten (transienten) 503 still auf Mock-Demo-Daten zurück und zeigte "Keine Work Orders" statt eines Fehlers — dieselbe Anti-Pattern-Klasse, die CLAUDE.md für `mockWorkOrders.ts` bereits dokumentiert, hier aber noch nicht behoben war. Gefixt: nur noch ein echtes 404 fällt auf Demo-Daten zurück, jeder andere Fehler zeigt einen sichtbaren Fehlerzustand mit Retry (Muster wie `RunnerConnections.tsx`). Live verifiziert in beide Richtungen (Erfolg und echter Fehler). |
| Frühere Pläne erreichbar | Implementiert, verifiziert (aus Vorsession) | — |

**Abnahmekriterium Stufe 1**: noch nicht vollständig erreicht — der Runner-
Pairing-Teil ist es jetzt (real), die echte Ende-zu-Ende-Codeausführung
eines konkreten Tasks ist es aus Kostengründen (Nutzerentscheidung) noch
nicht.

## Stufe 2 — Private Beta, getrennte Nutzerkonten

| Baustein | Status | Beleg |
|---|---|---|
| user_id-Scoping: Projects, Work Orders, Runner Connections | **Live mit einem echten zweiten Testaccount verifiziert** | Neuer, echter Supabase-Nutzer (`cp-isolation-test-b@commandpilot.local`, eigene `workspace_id`) angelegt, angemeldet, direkt gegen die echte API getestet: `/api/projects/me`, `/api/work-orders/me`, `/api/runner-connections` liefern für diesen Nutzer korrekt leere Listen — kein Datum von Serkans Account sichtbar. |
| 404-statt-403 bei Fremdzugriff | Implementiert (`require_owned_record`, aus Vorsession) | — |
| Runner-Autorisierung pro Nutzer, widerrufbar | Implementiert, live verifiziert | Siehe Stufe 1 |
| Server-Kostenlimits | Implementiert (`usage_service.py`, $0.50/Tag für OpenAI; `--max-budget-usd` für Claude-CLI-Läufe) | Claude-CLI-Budget in dieser Session real getestet — siehe Stufe 1: die Kappung griff, aber später/teurer als beabsichtigt |
| **Vault/Kalender/Notion: Isolation zwischen Nutzern** | **War ein kritischer, live reproduzierter Datenleck — jetzt gefixt** | Mit demselben echten zweiten Testaccount gefragt: "Was steht heute und morgen in meinem Kalender, und welche offenen Notion-Aufgaben habe ich?" → **Antwort enthielt Serkans echten Outlook-Termin und mehrere seiner echten, teils sensiblen Notion-Aufgaben** (Steuererklärung, Versicherungsschäden, medizinischer Befund). Ursache: `VAULT_OWNER_USER_ID` war in `backend/.env` gar nicht gesetzt (Gate faktisch aus), und für Calendar/Notion existierte **überhaupt kein** Eigentümer-Gate — die drei `get_context()`-Funktionen kennen gar keinen `user_id`-Parameter. **Gefixt**: neue `is_personal_integrations_owner()`-Prüfung in `app/core/config.py`, verdrahtet in `routers/jarvis.py` UND `routers/plans.py` vor allen drei externen Quellen; `VAULT_OWNER_USER_ID` jetzt real gesetzt. Live erneut mit demselben Testaccount geprüft: Antwort enthält jetzt korrekt nichts mehr ("kann dazu nichts in deinem Second Brain finden"); Serkans eigener Zugriff über den echten Runner-Token weiterhin korrekt mit echten Daten verifiziert (keine Regression). Zwei neue Regressionstests ergänzt (`test_jarvis_router.py`). |
| Zwei-Konten-Isolationstest | **Durchgeführt** (siehe oben) | Zweiter Testaccount nach Gebrauch wieder gelöscht (Supabase Admin API), Zugangsdaten nirgends persistiert. |

**Kritischer Fund dieser Session**: Bis zu diesem Fix hätte jeder zweite
echte Signup sofort Serkans private Kalender- und Notion-Daten über Jarvis
gesehen. Das ist der schwerwiegendste Befund der gesamten Verifikation und
war der eigentliche Blocker für jede Form von Multi-Tenant-Beta — nicht das
Runner-Pairing.

**Verbleibende Einschränkung (bewusst, dokumentiert)**: Vault/Kalender/Notion
sind weiterhin architektonisch Single-Tenant (eine Instanz, ein
Composio-Account) — der Fix beschränkt den Zugriff auf den einen
konfigurierten Eigentümer, macht daraus aber **keine** Pro-Nutzer-Integration.
Für echte Mehrbenutzer-Integrationen (jeder Tester verbindet seinen eigenen
Kalender/Notion) ist ein separates Stück Arbeit nötig — siehe "Offene
Einzelentscheidungen" unten.

## In dieser Session behobene Bugs (alle live gefunden, nicht nur im Code gelesen)

1. **`.gitignore` fehlte `.cp_runner_token.json`** — ein echtes, lokal
   erzeugtes Runner-Token hätte versehentlich committet werden können.
   Gefixt vor dem ersten echten Pairing-Lauf.
2. **`postgrest-py 2.30.0`s `maybe_single().execute()` gibt bei 0 Treffern
   `None` zurück** (nicht ein Response-Objekt mit `.data=None`) — an drei
   Stellen nicht abgefangen: `runner_connection_service._find_pending_request`,
   `runner_connection_service.poll_pairing_status`,
   `auth._resolve_runner_token`. Live reproduziert: ein abgelaufener
   Pairing-Code und ein widerrufener Runner-Token crashten jeweils mit
   HTTP 500 statt eines sauberen 401/"abgelaufen". Alle drei gefixt; die
   In-Memory-Test-Fakes in `test_runner_connection_service.py` wurden
   korrigiert (sie hatten dieses reale Verhalten nicht nachgebildet, weshalb
   der Bug die Test-Suite unbemerkt passierte), und die betroffenen Tests von
   `assertRaises(Exception)` auf die konkrete `HTTPException(401)` verschärft.
3. **`frontend/app/(app)/operator/[id]/page.tsx` fiel bei JEDEM Fetch-Fehler
   auf Mock-Demo-Daten zurück** (nicht nur bei einem echten 404) — ein
   echter, live reproduzierter transienter 503 zeigte "Keine Work Orders"
   statt eines Fehlers. Gefixt: nur `ApiError` mit `status === 404` fällt
   auf Demo-Daten zurück, jeder andere Fehler zeigt einen sichtbaren
   Fehlerzustand mit Retry-Button (`operator.load_error`-i18n-Key ergänzt).
4. **Kritischer Multi-Tenant-Datenleck** (siehe Stufe 2 oben) — der mit
   Abstand schwerwiegendste Fund.

**Nicht behobene, aber real beobachtete Umgebungs-Eigenheit**: unter starker
gleichzeitiger lokaler Last (viele parallele Skripte/Browser-Tabs während
dieser Session) tritt auf diesem Windows-Rechner gelegentlich
`httpx.ReadError: [WinError 10035]` beim Supabase-REST-Call auf, was der
Endpunkt korrekt als 503 durchreicht. Kein Code-Bug, sondern ein bekanntes
httpx/Windows-Verhalten unter Lastspitzen — der jetzt gefixte Retry-Zustand
(Punkt 3 oben) ist die richtige Abfederung dafür, nicht ein Versuch, das
Transportverhalten selbst zu ändern.

## Stufe 3 — Wiederholbares Onboarding

Unverändert: kein Einladungsmechanismus, kein Onboarding-Flow über
Supabase-Signup hinaus. **Fehlend, nicht begonnen.**

## Stufe 4 — Bezahlbares Angebot

Unverändert: kein Billing, keine Plan-Limits über den bestehenden
Tages-Kostendeckel hinaus. **Fehlend, nicht begonnen.**

## Offene Einzelentscheidungen

1. **Vault/Kalender/Notion pro Nutzer machen?** Aktuell auf "nur der
   konfigurierte Eigentümer" gehärtet (sicher, aber weiterhin Single-Tenant
   für die Inhalte selbst). Für echte eingeladene Tester bräuchte jeder
   seinen eigenen Composio-Connect — nicht in dieser Session gebaut.
2. **Daemon-Autonomiepfad auf ein externes Zielrepo erweitern** — aktuell
   strukturell auf `REPO_ROOT` (CommandPilot selbst) festgelegt, siehe oben.
3. **Realistische Kostenschätzung für Claude-CLI-Läufe**: ein triviales
   "eine HTML-Datei anlegen"-Ticket kostete beim ersten Turn bereits $0.53
   (großer einmaliger Cache-Creation-Overhead durch den Runner-Prompt selbst)
   — Budget-Empfehlungen/Dokumentation für Nutzer sollten das wohl nach oben
   korrigieren, damit `--max-budget-usd 0.30`-artige Versuche nicht
   routinemäßig scheitern.
4. **Jarvis "genau zwei Vorschläge"-Regel**: GPT-4o hält sich in der Praxis
   nicht zuverlässig daran (real zweimal nur einen geliefert, korrekt
   verworfen, aber dem Nutzer dadurch nichts angezeigt) — Prompt- oder
   Schema-Anpassung (z. B. Retry bei genau einem Treffer, oder das Modell
   explizit um "genau zwei, andernfalls keinen" bitten lassen) wäre ein
   sinnvoller nächster Schritt, nicht in dieser Session umgesetzt.
