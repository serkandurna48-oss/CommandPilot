---
paths:
  - "supabase/**"
---

# Datenbank-/Migrations-Regeln (CommandPilot)

Ergänzt `CLAUDE.md` — hier stehen nur DB-spezifische, aktionable Details.

- **Nummerierung**: neue Migrationen als `supabase/migrations/NNN_beschreibung.sql`,
  nächste fortlaufende Nummer.
- **Idempotenz-Default**: `IF NOT EXISTS`/`DO $$ ... $$`-Guards, außer es gibt einen
  konkreten Grund dagegen — dann die Ausnahme **im Datei-Header selbst** UND in der
  README-Migrationstabelle ("What it does"-Spalte) explizit benennen, so wie bei
  `004_ai_usage_log.sql` (CREATE POLICY ohne Guard) gehandhabt.
- **RLS ist Defense-in-Depth, nicht der einzige Schutz**: das FastAPI-Backend nutzt
  den Service-Role-Key und umgeht RLS vollständig. Der eigentliche Schutz sind die
  Ownership-Checks in `backend/app/auth.py`/den Routern (`.eq("user_id", ...)`).
  Eine neue RLS-Policy allein reicht nie aus.
- **README-Sync-Pflicht**: jede neue Migrationsdatei muss im selben Change in
  README.md's Tabelle "1b. Running Migrations" eingetragen werden. Genau diese
  Synchronisation ist einmal gerissen (003–005 fehlten trotz aktiver Nutzung im
  Code) — nicht wiederholen. Der Subagent `architecture-consistency-check` prüft
  das automatisiert.
- **Nicht-idempotente Migrationen (CREATE POLICY ohne Guard), alle auf `main`,
  jeweils nur einmal ausführen**: `004_ai_usage_log.sql`, `006_work_orders.sql`,
  `007_work_order_steps.sql`, `013_suggested_action_decisions.sql`.
