Auftrag-ID: JARVIS-A1
Repo/Branch: C:\Users\serka\dev\commandpilot, main
Ausgangscommit: e86ee41

Ziel: Der Jarvis-Ablauf aus dem heutigen Browsertest bleibt, wird aber sicher,
sauber belegbar und mit einem Befehl prüfbar.

Aufgabe 1 — Prüfbefehl (zuerst, alles Weitere nutzt ihn):
scripts/check.ps1, das nacheinander ausführt und am Ende eine Zusammenfassung
mit Exit-Code liefert:
  - backend: .venv\Scripts\python.exe -m pytest backend/tests -q
  - frontend: npm run type-check
  - frontend: npm run lint
npm run build bleibt bewusst draußen — es scheitert ohne .env am Prerendering
aller geschützten Seiten, das ist bekannt und kein Regressionssignal.
Der Befehl muss aus dem Repo-Root laufen und ohne Argumente funktionieren.

Aufgabe 2 — Vault an den Eigentümer binden (Codex-Befund 1, P1):
Neue Env-Var VAULT_OWNER_USER_ID. Die user_id des anfragenden Nutzers wird von
routers/jarvis.py und von plan_service an das Retrieval durchgereicht. Stimmt
sie nicht überein: leerer Kontext plus Logeintrag. Leere VAULT_OWNER_USER_ID
verhält sich wie heute. Keine Migration, keine Pro-Nutzer-Verwaltung.

Aufgabe 3 — Fehlervertrag (Befund 3):
UnicodeDecodeError zusätzlich zu OSError fangen, betroffene Datei überspringen,
Rest weiterverarbeiten.

Aufgabe 4 — Budget (Befund 2):
Basisbudget auf das Gesamtbudget deckeln. Budgetiert wird der formatierte
Kontext inklusive Quellenlabels. Die Codex-Reproduktion (Index 10.000 Zeichen,
Gesamtbudget 50) wird als Test aufgenommen.

Aufgabe 5 — Quellen entrauschen (aus dem Browsertest vom 18.09.):
Die Antwort zeigte 24 Quellen, getragen haben sie vier. Trenne in der API-
Antwort und in der UI zwischen den Treffern, die in die Antwort eingeflossen
sind, und dem Basiskontext. Sichtbar ist standardmäßig nur Ersteres.
Zusätzlich: Systemprompt so anpassen, dass das Modell keine "Quellen:"-Zeile
mehr in den Antworttext schreibt — die UI listet sie bereits.

Aufgabe 6 — Vertrag korrigieren (Befund 4):
Frontmatter wird in der Basisebene ausgegeben, aber nicht für die Query
gewichtet. Docstring und CLAUDE.md präzisieren. Keine Implementierung.

Aufgabe 7 — CLAUDE.md nachziehen:
Sie kennt die fünf Jarvis-Phasen noch nicht. Vault-Service, Jarvis-Router,
/jarvis-UI, die sechs Testdateien und scripts/check.ps1 ergänzen.

Nicht-Ziele: keine Work Orders aus dem Chat, keine Sprache, kein Dashboard,
keine Embeddings, kein Frontmatter-Matching, keine Migration.

Abnahme:
- scripts/check.ps1 läuft grün durch, ein Befehl, ohne Argumente
- Browserdurchlauf: "Wie ist mein Reha-Stand?" liefert dieselbe Qualität wie
  heute, aber mit höchstens einer Handvoll sichtbarer Quellen und ohne
  "Quellen:"-Zeile im Antworttext
- user_id ≠ VAULT_OWNER_USER_ID → leerer Kontext, nachweisbar
- Datei mit ungültigem UTF-8 im Vault → übrige Dateien werden weiter gefunden

Übergabe: Commit-ID, Ausgabe von check.ps1, was du selbst im Browser geklickt
hast, ungetestete Bereiche, verbleibende Einschränkungen. Nicht pushen.