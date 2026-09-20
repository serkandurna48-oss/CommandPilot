-- Migration: JARVIS-C1 — suggested_action_decisions (Command Layer audit + idempotency)
--
-- Jarvis can propose suggested_actions in a chat reply (see
-- backend/app/models/jarvis.py SuggestedAction) — nothing is written to the
-- database at proposal time (POST /api/jarvis/chat never touches this or any
-- other table beyond ai_usage_log). A human then confirms or rejects each
-- proposal individually. This table is the single record of that decision:
--   - confirmed -> work_order_id is set: a real work order (+ approval scope
--                  + activity_logs entry) was created via work_order_service
--   - rejected  -> work_order_id stays NULL, nothing else was created — this
--                  row IS the entire audit trail for a rejected proposal
-- activity_logs cannot represent a rejected proposal: its work_order_id
-- column is NOT NULL (006_work_orders.sql) because every existing row there
-- is scoped to a real work order. A decision with no work order has nowhere
-- else to go, hence this separate table rather than reusing activity_logs.
--
-- Idempotency (JARVIS-C1, Phase 6): request_id is a client-generated token,
-- one per suggested-action card, reused across retries of the same click —
-- never a server-assigned id, since suggested_actions themselves are never
-- persisted at chat time. The UNIQUE index on (user_id, request_id) is what
-- actually prevents a double-click/retry from creating two work orders for
-- the same proposal (see backend/app/services/suggested_action_service.py's
-- insert-first-then-act ordering) — not application-level logic alone, which
-- has a race window a UNIQUE constraint closes. A decision, once recorded,
-- is immutable; a later request for the same request_id but a different
-- decision is rejected by the service layer (409), never silently applied.
--
-- Ownership: user_id is the root (same pattern as work_orders, projects) —
-- no join needed for RLS/ownership checks, unlike the work_orders children.
--
-- NOT idempotent: CREATE POLICY has no IF NOT EXISTS guard, matching
-- 004_ai_usage_log.sql / 006_work_orders.sql / 007_work_order_steps.sql. Run
-- once.

create table if not exists suggested_action_decisions (
  id                  uuid primary key default uuid_generate_v4(),
  user_id             uuid not null references profiles(id) on delete cascade,
  workspace_id        uuid references workspaces(id),
  request_id          text not null,
  decision            text not null
                        check (decision in ('confirmed', 'rejected')),
  -- Denormalized snapshot of the proposal at decision time — the audit trail
  -- must stand on its own even if the underlying work order is later edited
  -- or deleted, and a rejected proposal has no work order to look this up on.
  title               text not null,
  team_type           text,
  target_repo_name    text,
  risk                text,
  requires_approval   boolean,
  sources             jsonb not null default '[]',
  work_order_id       uuid references work_orders(id) on delete set null,
  created_at          timestamptz not null default now()
);

create unique index if not exists idx_suggested_action_decisions_request
  on suggested_action_decisions(user_id, request_id);

alter table suggested_action_decisions enable row level security;

create policy "Users own suggested_action_decisions"
  on suggested_action_decisions for all using (auth.uid() = user_id);
