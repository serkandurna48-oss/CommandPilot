-- Migration: OP-Backend-001 — Background Dev Team work orders foundation
-- Adds 6 tables: work_orders, approval_scopes, agent_runs, activity_logs,
-- artifacts, review_packages. Fresh installs get these from supabase/schema.sql
-- directly; this migration brings an already-provisioned project up to date.
--
-- Design notes:
-- - work_orders carries user_id/workspace_id (the ownership root), mirroring
--   the projects table. The other 5 tables are children scoped by
--   work_order_id and own no user_id column — ownership is enforced via a
--   join back to work_orders in both RLS policies and the FastAPI service
--   layer (require_owned_record on work_orders first, every child query is
--   then scoped to that verified work_order_id).
-- - approval_scopes.work_order_id and review_packages.work_order_id are
--   UNIQUE (1:1 with their work order). work_orders does NOT store an
--   approval_scope_id column — the API layer looks it up via the reverse FK
--   to avoid a circular "which row do I insert first" dependency.
-- - NOT fully idempotent (CREATE POLICY has no IF NOT EXISTS guard, matching
--   004_ai_usage_log.sql's precedent). Run once during initial deploy.

create table if not exists work_orders (
  id                    uuid primary key default uuid_generate_v4(),
  workspace_id          uuid references workspaces(id) on delete cascade,
  user_id               uuid not null references profiles(id) on delete cascade,
  title                 text not null,
  goal                  text not null,
  repo                  text not null default 'commandpilot',
  status                text not null default 'draft'
                          check (status in (
                            'draft', 'approved', 'queued', 'running',
                            'needs_approval', 'blocked', 'failed',
                            'review_ready', 'accepted', 'rework_requested',
                            'cancelled'
                          )),
  created_by            text not null,
  time_limit_minutes     integer not null default 90,
  acceptance_criteria    jsonb not null default '[]',
  missing_context        jsonb not null default '[]',
  recommended_next_step  text,
  started_at            timestamptz,
  completed_at          timestamptz,
  created_at            timestamptz not null default now()
);

create table if not exists approval_scopes (
  id                    uuid primary key default uuid_generate_v4(),
  work_order_id         uuid not null unique references work_orders(id) on delete cascade,
  allowed_actions       jsonb not null default '[]',
  requires_approval     jsonb not null default '[]',
  blocked_actions       jsonb not null default '[]',
  allowed_paths         jsonb,
  blocked_paths         jsonb,
  max_runtime_minutes   integer not null,
  max_cost_usd          numeric(10,2),
  created_at            timestamptz not null default now()
);

create table if not exists agent_runs (
  id                uuid primary key default uuid_generate_v4(),
  work_order_id     uuid not null references work_orders(id) on delete cascade,
  role              text not null
                      check (role in ('product', 'architect', 'coder', 'qa', 'reviewer', 'reporter')),
  status            text not null default 'queued'
                      check (status in ('queued', 'running', 'blocked', 'failed', 'completed')),
  input_summary     text not null,
  output_summary    text,
  model             text,
  started_at        timestamptz,
  completed_at      timestamptz,
  created_at        timestamptz not null default now()
);

create table if not exists activity_logs (
  id              uuid primary key default uuid_generate_v4(),
  work_order_id   uuid not null references work_orders(id) on delete cascade,
  agent_run_id    uuid references agent_runs(id) on delete set null,
  level           text not null
                    check (level in ('info', 'warning', 'error', 'approval_required')),
  event_type      text not null,
  message         text not null,
  metadata        jsonb,
  created_at      timestamptz not null default now()
);

create table if not exists artifacts (
  id              uuid primary key default uuid_generate_v4(),
  work_order_id   uuid not null references work_orders(id) on delete cascade,
  type            text not null
                    check (type in ('plan', 'diff', 'test_output', 'review', 'summary', 'screenshot', 'prompt')),
  title           text not null,
  content         text,
  file_path       text,
  created_at      timestamptz not null default now()
);

create table if not exists review_packages (
  id                    uuid primary key default uuid_generate_v4(),
  work_order_id         uuid not null unique references work_orders(id) on delete cascade,
  summary               text not null,
  files_changed         jsonb not null default '[]',
  tests_run             jsonb not null default '[]',
  risks                 jsonb not null default '[]',
  open_questions        jsonb not null default '[]',
  needs_human_review    boolean not null default true,
  recommended_next_step text,
  verdict               text not null
                          check (verdict in ('ready_for_review', 'needs_fix', 'blocked', 'unsafe')),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
create index if not exists idx_work_orders_user
  on work_orders(user_id, status);

create index if not exists idx_agent_runs_work_order
  on agent_runs(work_order_id, created_at);

create index if not exists idx_activity_logs_work_order
  on activity_logs(work_order_id, created_at);

create index if not exists idx_artifacts_work_order
  on artifacts(work_order_id, created_at);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table work_orders      enable row level security;
alter table approval_scopes  enable row level security;
alter table agent_runs       enable row level security;
alter table activity_logs    enable row level security;
alter table artifacts        enable row level security;
alter table review_packages  enable row level security;

create policy "Users own work_orders"
  on work_orders for all using (auth.uid() = user_id);

create policy "Users own approval_scopes via work order"
  on approval_scopes for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = approval_scopes.work_order_id
        and wo.user_id = auth.uid()
    )
  );

create policy "Users own agent_runs via work order"
  on agent_runs for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = agent_runs.work_order_id
        and wo.user_id = auth.uid()
    )
  );

create policy "Users own activity_logs via work order"
  on activity_logs for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = activity_logs.work_order_id
        and wo.user_id = auth.uid()
    )
  );

create policy "Users own artifacts via work order"
  on artifacts for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = artifacts.work_order_id
        and wo.user_id = auth.uid()
    )
  );

create policy "Users own review_packages via work order"
  on review_packages for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = review_packages.work_order_id
        and wo.user_id = auth.uid()
    )
  );
