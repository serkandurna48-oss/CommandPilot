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
- **Falls `supabase/migrations/006_work_orders.sql` (oder höher) existiert**
  [nur auf `feat/operator-control-plane`]: 006 hat dieselbe
  Nicht-idempotenz-Einschränkung wie 004 (CREATE POLICY ohne Guard) — nur einmal
  ausführen.
