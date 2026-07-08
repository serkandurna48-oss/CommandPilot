-- Migration: OP-Create-001 — work_orders.team_type
--
-- Adds a `team_type` column so a work order can eventually represent
-- something other than a coding task (sales, onboarding, content, study,
-- process optimization, ...) without a schema change every time a new kind
-- shows up. Deliberately NOT a `check (team_type in (...))` constraint —
-- unlike status/assigned_role/etc., this field is meant to stay open-ended;
-- "development" is just the first value, not the only one ever allowed.
-- See docs/background-dev-team-system-design.md §0 (strategic framing).
--
-- Safe for existing rows: ADD COLUMN with a default backfills every
-- existing work order as 'development' (today's only real team type).
-- Idempotent: IF NOT EXISTS guards the column add.

alter table work_orders
  add column if not exists team_type text not null default 'development';
