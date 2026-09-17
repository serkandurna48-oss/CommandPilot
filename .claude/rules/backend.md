---
paths:
  - "backend/**"
---

# Backend-Regeln (CommandPilot)

Ergänzt `CLAUDE.md` — hier stehen nur backend-spezifische, aktionable Details.

- **Schichtung nicht umgehen**: `routers/` (nur HTTP-Boundary, Request-/Response-
  Modelle) → `services/` (Business-Logik) → `db/client.py` (Supabase-Zugriff).
  Keine Supabase-Queries direkt in Routern, kein Pydantic-Parsing in Services.
- **Ownership-Pattern konkret** (siehe `CLAUDE.md` § Auth-/Security-Grundregeln für
  die Kurzfassung): jeder neue Endpoint auf einer nutzereigenen Tabelle hängt von
  `get_current_user()` ab und filtert mit `.eq("user_id", user.id)` bzw. nutzt
  `require_owned_record()` — 404 statt 403 bei fremdem Datensatz.
- **AI-Prompt-Logik** bleibt isoliert in `app/prompts/`, nicht inline in
  `services/ai_service.py`.
- **Fehlerbehandlung**: `json.JSONDecodeError` und `pydantic.ValidationError`
  getrennt fangen und als beschreibende `ValueError`s re-raisen (bestehende
  Konvention in `ai_service.py`).
- **Kein Lint-/Test-Tool konfiguriert** (kein ruff/black/pytest) — keins erfinden;
  falls eines sinnvoll wäre, explizit vorschlagen statt stillschweigend anzunehmen.
- **Falls `core/safety_rules.py` in deinem Checkout existiert**
  [nur auf `feat/operator-control-plane`]: das ist die **echte
  Enforcement-Schicht** für Work-Order-Approval-Scopes.
  `frontend/lib/safetyRules.ts` ist nur Anzeige — Änderungen an erlaubten/
  genehmigungspflichtigen Aktionen zuerst in `safety_rules.py` vornehmen, dann mit
  Frontend und Runner-Prompt-Text synchronisieren.
