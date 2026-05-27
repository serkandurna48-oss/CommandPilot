-- Migration: CP-203 — ai_usage_log table
-- Tracks every OpenAI API call with token counts and USD cost.
-- Used for per-user daily spending cap enforcement ($0.50/user/UTC-day).
--
-- request_date is set server-side to datetime.now(UTC).date() at insert time —
-- NOT derived from plan_date. This prevents cap bypass via back-dated plans.
--
-- FK pattern: user_id → profiles(id), consistent with daily_plans / evening_reviews.
-- plan_id is nullable (ON DELETE SET NULL) because the plan INSERT may fail after
-- the AI call — the usage still happened and must be logged.
--
-- NOT fully idempotent: CREATE POLICY has no IF NOT EXISTS guard (pre-PG15).
-- Run once during initial deploy. Re-running will error on the policy statement.

create table if not exists ai_usage_log (
  id            uuid          primary key default uuid_generate_v4(),
  user_id       uuid          not null references profiles(id) on delete cascade,
  workspace_id  uuid          references workspaces(id),
  plan_id       uuid          references daily_plans(id) on delete set null,
  request_date  date          not null,
  model         text          not null,
  input_tokens  int           not null,
  output_tokens int           not null,
  cost_usd      numeric(10,6) not null,
  created_at    timestamptz   not null default now()
);

create index if not exists idx_ai_usage_log_user_date
  on ai_usage_log(user_id, request_date desc);

alter table ai_usage_log enable row level security;

-- Users may read their own usage (e.g. future spending dashboard).
-- No insert/update/delete policy — writes go through service role only.
create policy "Users view own usage"
  on ai_usage_log for select using (auth.uid() = user_id);
