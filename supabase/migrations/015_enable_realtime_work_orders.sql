-- Migration: enable Supabase Realtime on the Operator Control Plane tables
--
-- Background: work orders were a static, fetch-once snapshot in the
-- frontend (frontend/app/(app)/operator/[id]/page.tsx loaded once via
-- load(), never again). This migration is the DB-side half of making a
-- *running* work order feel live: a postgres_changes subscription on these
-- three tables (frontend/lib/supabase.ts's standard client — no config
-- change needed, Realtime is already available on it) lets the operator
-- detail page react to backend PATCHes/POSTs without polling or reload.
--
-- Realtime respects each table's existing RLS policies automatically — no
-- new policy needed here. Owner-scoped SELECT policies already exist:
--   work_orders       -- "Users own work_orders" (006_work_orders.sql)
--   work_order_steps  -- owner via join back to work_orders (schema.sql:530)
--   activity_logs     -- owner via join back to work_orders (schema.sql:557)
--
-- Idempotent: `alter publication ... add table` errors if the table is
-- already a publication member, so each ADD is guarded by a check against
-- pg_publication_tables rather than relying on IF NOT EXISTS (which that
-- statement doesn't support).

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'work_orders'
  ) then
    alter publication supabase_realtime add table work_orders;
  end if;

  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'work_order_steps'
  ) then
    alter publication supabase_realtime add table work_order_steps;
  end if;

  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'activity_logs'
  ) then
    alter publication supabase_realtime add table activity_logs;
  end if;
end $$;
