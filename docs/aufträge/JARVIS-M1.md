Auftrag-ID: JARVIS-M1
Repo/Branch: C:\Users\serka\dev\commandpilot, main
Ausgangscommit: 4f97361

ZIEL (die Demo, an der abgenommen wird)
Ich schreibe im Jarvis-Chat ein Ziel. Jarvis schlägt zwei Teilaufträge vor.
Ich bestätige. Zwei Agenten arbeiten nachweislich gleichzeitig in zwei
getrennten Arbeitsverzeichnissen. Beide Ergebnisse werden importiert, geprüft
und mir gemeinsam zur Freigabe vorgelegt.

Wiederverwenden, nicht neu bauen: work_orders, approval_scopes, agent_runs,
activity_logs, review_packages, scripts/run_work_order.py, runner_adapters,
scripts/import_work_order_result.py, work_order_service.

Der Runner-Smoke-Test ist Phase 0 dieses Auftrags, kein Vorprojekt.

PHASE 0 — Abgleich und ein echter Lauf. Danach anhalten und berichten.
a) Prüfe am Code, wie run_work_order.py sein Arbeitsverzeichnis bestimmt:
   nutzt es work_orders.target_repo_path, oder immer das cwd? Davon hängt
   Phase 2 ab. Melde die Antwort, bevor du weiterbaust.
b) Lass EINE Work Order vollständig durchlaufen, gegen
   Projekte\commandpilot-e2e-fixture als Zielrepo:
   --mode prompt-file → --mode execute --adapter claude_code
   --max-budget-usd 0.20 → --mode import-result.
   Bekannte Stolpersteine, die kein Grund zum Umbauen sind: Status muss
   approved/queued sein, blocked_actions und allowed_paths dürfen nicht leer
   sein, und claude muss im Zielverzeichnis einmal interaktiv gelaufen sein.
c) Bericht: was lief, was nicht, was der Adapter tatsächlich produziert hat.
   Läuft der Adapter nicht sauber durch: hier anhalten, nicht weiterbauen.

PHASE 1 — Ziel wird zu zwei Teilaufträgen
Der Jarvis-Chat darf suggested_actions befüllen, wenn die Nachricht ein Ziel
beschreibt. Struktur bleibt wie in Phase 4 definiert: title, description,
team_type, target_repo_name, risk, requires_approval, sources.
Im Chat-UI erscheinen die Vorschläge als Karten mit Vorschau, je Karte
Bestätigen und Ablehnen. Ohne Klick passiert nichts.
Bestätigen legt über work_order_service eine echte Work Order mit Approval
Scope und Activity-Log-Eintrag an, inklusive nicht-leerer blocked_actions und
allowed_paths, damit sie ausführbar ist. Ablehnen legt nichts an und wird
protokolliert.

PHASE 2 — Isolation
Jede bestätigte Work Order bekommt ein eigenes git worktree, erzeugt aus dem
Zielrepo, und target_repo_path zeigt darauf. Die Worktrees liegen außerhalb
des Hauptarbeitsverzeichnisses und außerhalb von iCloud. Zwei Läufe dürfen
niemals dasselbe Verzeichnis benutzen. Aufräumen nach dem Lauf: ja, aber erst
nach dem Import, und ein fehlgeschlagener Lauf bleibt zur Untersuchung stehen.

PHASE 3 — Parallelität
Zwei Läufe laufen gleichzeitig. Der Start darf manuell angestoßen sein, ein
kleines Startskript ist erlaubt. Keine Queue, kein Scheduler, keine Heartbeats.
Der Nachweis der Überlappung kommt aus den Zeitstempeln in agent_runs: die
Intervalle von Lauf A und Lauf B müssen sich schneiden.

PHASE 4 — Gemeinsames Ergebnis
Beide Ergebnisse über den bestehenden Result-Import einlesen. Eine Ansicht
zeigt beide Review Packages nebeneinander: geänderte Dateien, ausgeführte
Tests, Risiken, empfohlener nächster Schritt. Annehmen oder Ablehnen je
Auftrag. Ein fehlgeschlagener Lauf wird als fehlgeschlagen dargestellt.

AUSFÜHRUNGS- UND ZUGRIFFSPROBLEME
Was den Ablauf blockiert, darfst du innerhalb dieses Auftrags beheben —
Token-Handhabung, Pfadgrenzen, Rechte, Worktree-Erzeugung, Adapter-Fehler.
Melde jede solche Korrektur einzeln.

NICHT-ZIELE
Kein Design, keine Typografie, keine Farben. Kein Qualitätspaket (JARVIS-Q1
bleibt liegen). Keine echte Queue, keine Sandbox, keine Policy Engine, keine
Crash-Recovery, keine Heartbeats, mehr als zwei Agenten nicht nötig. Keine
Sprache, kein Dashboard, keine Notion-/Kalender-Anbindung.

ABNAHME
Zwei Agentenläufe, deren Zeitintervalle sich nachweislich überschneiden, in
zwei verschiedenen Arbeitsverzeichnissen, mit echten Ergebnissen, beide
gemeinsam in einer Ansicht zur Freigabe. Vorher: scripts/check.ps1 grün,
neue Logik durch Tests abgedeckt, ein Browserdurchlauf durch den kompletten
Weg vom Ziel bis zur Freigabe.

ÜBERGABE
Nach jeder Phase: Commit-IDs, Ausgabe von check.ps1, was du selbst geklickt
oder ausgeführt hast, ungetestete Bereiche, verbleibende Einschränkungen.
Commit nach jeder Phase erlaubt, wenn check.ps1 grün ist und du vorher in
zwei Zeilen sagst, was reingeht. Nicht pushen.
Nach Phase 0 und nach Phase 3 anhalten und auf mich warten.