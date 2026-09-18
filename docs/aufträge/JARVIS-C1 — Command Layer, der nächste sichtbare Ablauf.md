Auftrag-ID: JARVIS-C1
Ausgangscommit: Ergebnis von Q1

Ziel aus Nutzersicht: Ich schreibe im Jarvis-Chat ein Ziel. Jarvis schlägt zwei
Work Orders vor, mit Vorschau. Ich bestätige oder lehne ab. Bestätigte werden
als echte Work Orders angelegt, abgelehnte hinterlassen nichts außer einem
Protokolleintrag.

Wiederverwenden: work_order_service, approval_scopes, activity_logs, das
bestehende SuggestedAction-Modell aus Phase 4.

1. Der Systemprompt darf suggested_actions befüllen, wenn die Nachricht ein
   Ziel beschreibt. Struktur unverändert: title, description, team_type,
   target_repo_name, risk, requires_approval, sources.
2. Im Chat-UI erscheinen Vorschläge als Karten mit Vorschau, je Karte
   Bestätigen und Ablehnen. Nichts passiert ohne Klick.
3. Bestätigen legt über work_order_service eine Work Order mit Approval Scope
   und Activity-Log-Eintrag an. Ablehnen legt nichts an, wird protokolliert.
4. Fall 10 aus Q1 wird angepasst: ohne Bestätigung weiterhin kein Schreibvorgang.

Nicht-Ziele: keine Ausführung, keine Agenten, keine Worktrees, keine Queue,
keine Parallelität. Das ist der nächste Auftrag und hat sein eigenes Tor.

Abnahme:
- Ein Ziel im Chat führt zu genau zwei Vorschlägen mit Vorschau
- Ablehnen legt nachweislich nichts in der Datenbank an
- Bestätigen erzeugt zwei Work Orders, sichtbar in der Operator-Liste, mit
  Approval Scope und Audit-Eintrag
- check.ps1 grün, Browserdurchlauf mit beiden Wegen