---
name: abnahme
description: Abnahme-Ablauf für CommandPilot vor einem Merge — scripts/check.ps1, gezielte Tests, Browserdurchlauf, Übergabeformat. Nutzen, wenn ein Feature/Fix bereit zur Abnahme ist.
---

# Abnahme

Ein-Befehl-Prüfung plus Browserdurchlauf, bevor etwas als "done" markiert oder
gemergt wird. Kein Ersatz für Code-Review — nur die deterministische Basis.

## 1. Automatisiert

```powershell
.\scripts\check.ps1
```

Läuft Backend-Pytest (`backend/tests`) + Frontend-Type-Check + Frontend-Lint,
gibt am Ende eine Zusammenfassung mit Exit-Code aus (0 = grün).
`npm run build` ist bewusst nicht enthalten — scheitert ohne `.env` am
Prerendering geschützter Seiten, kein Regressionssignal.

Zusätzlich, falls das geprüfte Thema betroffen ist, gezielt:

```bash
python -m pytest backend/tests/test_jarvis_quality.py -v
```

Zehn Fälle (JARVIS-Q1): Wissensretrieval (1–6), Fehlendes-Wissen-Ehrlichkeit
(7–8), Benutzertrennung (9), No-Action-Regression (10). Fälle 1–8 hängen am
echten `VAULT_PATH` (nicht am synthetischen Test-Vault) und **skippen**, wenn
er fehlt oder nicht lesbar ist — das ist korrektes Verhalten, kein Fehlschlag.
Fälle 9–10 laufen immer.

`scripts/test_*.py` (stdlib, Runner-Harness) separat bei Bedarf:
`python scripts/test_bounded_retry.py` etc. — nicht pytest-discoverbar.

## 2. Browserdurchlauf

`./start-dev.ps1` (Backend :8000, Frontend :3000), dann manuell:

- Login → Dashboard lädt ohne Fehler.
- Kernflow des geänderten Bereichs einmal vollständig durchspielen (z. B. bei
  Jarvis: `/jarvis` öffnen, eine Frage stellen, Antwort + Quellen prüfen).
- Sichtbarer Fehlerzustand bei absichtlich provoziertem Fehler (z. B. Server
  kurz stoppen) — nie stiller Mock-Fallback (siehe CLAUDE.md "Bekannte
  Risiken", `frontend/lib/mockWorkOrders.ts`).

**Benannte Fehlerfälle, auf die geachtet wird:**

- Stiller Mock-/Fallback-Fehlerzustand statt sichtbarer Fehlermeldung.
- `user_id` aus dem Client statt aus `get_current_user()` (Auth-Bypass).
- Fremder Datensatz liefert 403 statt 404 (Existenz-Leak).
- Migration nicht idempotent erneut ausgeführt (siehe `004_ai_usage_log.sql`,
  `006_work_orders.sql` — bekannte Ausnahmen, nur einmal ausführen).

## 3. Übergabeformat

Am Ende jeder Abnahme, unabhängig vom Ergebnis:

```
Commit-ID:        <git rev-parse HEAD>
Testergebnisse:   scripts/check.ps1 → <PASS/FAIL, Exit-Code>
                  test_jarvis_quality.py → <N passed, M skipped, Grund>
Browserdurchlauf: <Kernflow, Ergebnis, ggf. Screenshot/GIF>
Bekannte Einschränkungen: <z. B. "VAULT_PATH lokal nicht konfiguriert,
                  Fälle 1–8 geskippt" oder "kein E2E-Framework, nur manuell
                  geprüft">
```

Nichts faken: fehlende lokale Konfiguration (z. B. `VAULT_PATH`) wird als
Skip mit Grund dokumentiert, nicht stillschweigend übergangen oder als PASS
ausgegeben.
