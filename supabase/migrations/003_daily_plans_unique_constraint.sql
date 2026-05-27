-- Migration: add UNIQUE constraint (user_id, plan_date) to daily_plans
-- Prevents duplicate plans per user per day at the database level (CP-202).
--
-- Pre-condition: all duplicate (user_id, plan_date) pairs must be resolved
-- before running this migration. Run the following check first — it must
-- return 0 rows:
--
--   SELECT user_id, plan_date, COUNT(*)
--   FROM daily_plans
--   GROUP BY user_id, plan_date
--   HAVING COUNT(*) > 1;
--
-- Idempotent: no-op if the constraint already exists.

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'daily_plans_user_id_plan_date_key'
  ) then
    alter table public.daily_plans
      add constraint daily_plans_user_id_plan_date_key
      unique (user_id, plan_date);
  end if;
end $$;
