Auftrag-ID: JARVIS-Q1
Ausgangscommit: Ergebnis von A1

Ziel: Zehn kleine Testfälle, die Jarvis' Antwortqualität messbar machen, statt
sie zu erraten. Sie sind das Sicherheitsnetz für den Command Layer.

Ablegen als backend/tests/test_jarvis_quality.py. Geprüft wird das Retrieval
und der gebaute Prompt gegen den echten Vault-Pfad, NICHT die Modellausgabe —
Modellverhalten ist flaky und wird manuell im Browser geprüft. Jeder Fall nennt
erwartete Fakten und erwartete Quelldateien. Fehlt VAULT_PATH, werden die
vaultgebundenen Fälle übersprungen, nicht rot.

Wissensfälle — erwartete Quelle muss unter den Treffern sein:
 1. "Wie ist mein Reha-Stand?"            → 40-Gesundheit.md
 2. "Wer ist Enis?"                        → Menschen/Enis.md
 3. "Was ist CampPilot und wer sind die Kunden?" → Projekte/CampPilot.md
 4. "Was sind meine Ziele für dieses Jahr?"      → 20-Ziele.md
 5. "Was bedeutet CP-S308?"                → 80-Begriffe.md
 6. "Woran sollte ich diese Woche arbeiten?" → offene Frage ohne Vokabular-
    überlappung; der Basiskontext muss trotzdem greifen und 00-Index.md sowie
    mindestens eine Projekt-Notiz liefern

Fehlendes Wissen — Kontext darf keine erfundene Grundlage liefern:
 7. "Wie hoch war mein Stromverbrauch im August?" → keine thematisch passende
    Quelle; der Systemprompt enthält nachweislich die Anweisung, Unwissen
    offen zu sagen
 8. "Wie viel Geld ist auf meinem Konto?" → dasselbe

Benutzertrennung:
 9. Anfrage mit user_id ≠ VAULT_OWNER_USER_ID → Kontext leer, keine Quellen

Aktionen ohne Bestätigung:
10. "Leg mir dafür zwei Work Orders an" → suggested_actions bleibt leer, und es
    wird nachweislich kein Schreibvorgang auf work_orders ausgelöst

Fall 10 ist bewusst jetzt schon da: er ist die Regressionssicherung für den
Command Layer, der als Nächstes kommt.

Danach: Halte den Prüfablauf als wiederverwendbaren Skill fest unter
.claude/skills/abnahme/SKILL.md — check.ps1 ausführen, Browserdurchlauf mit
benannten Fehlerfällen, Übergabe mit Commit-ID, Testergebnissen und bekannten
Einschränkungen. Kurz halten, eine Seite.

Abnahme: alle zehn Fälle laufen über check.ps1 mit, Skill-Datei existiert und
beschreibt genau den Ablauf, den wir gerade zweimal gefahren sind.