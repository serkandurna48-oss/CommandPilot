-- Migration: agent_runs attempt tracking (CP-OP02)
--
-- The bounded auto-retry loop in scripts/run_work_order.py (--mode execute)
-- creates one agent_runs row per attempt instead of reusing/overwriting a
-- single row, so the full retry history of a work order stays visible and
-- auditable. These two columns identify which attempt a row represents and,
-- for attempt 2+, why the previous attempt was retried.
--
-- attempt_number is NOT a work_orders-level concept and does not gate
-- anything server-side — work_orders.status stays 'running' for the whole
-- duration of a retry sequence (see CP-OP02 report); the retry cap (max 3
-- attempts total) is enforced entirely in the harness's in-process loop,
-- not in the database.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS is safe to re-run.

alter table agent_runs
  add column if not exists attempt_number integer not null default 1,
  add column if not exists retry_reason text;
