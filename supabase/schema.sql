-- CommandPilot Database Schema
-- Supabase / PostgreSQL
-- Run this in the Supabase SQL editor

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Workspaces  (multi-tenant foundation)
-- ---------------------------------------------------------------------------
create table if not exists workspaces (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null,
  slug        text unique not null,
  owner_id    uuid not null,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Profiles   (extends Supabase auth.users 1-to-1)
-- ---------------------------------------------------------------------------
create table if not exists profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  workspace_id  uuid references workspaces(id),
  display_name  text,
  timezone      text default 'Europe/Berlin',
  language      text default 'en' check (language in ('en', 'de')),
  avatar_url    text,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Workspace members
-- ---------------------------------------------------------------------------
create table if not exists workspace_members (
  id            uuid primary key default uuid_generate_v4(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  user_id       uuid not null references profiles(id) on delete cascade,
  role          text not null default 'member'
                  check (role in ('owner', 'admin', 'member')),
  joined_at     timestamptz default now(),
  unique(workspace_id, user_id)
);

-- ---------------------------------------------------------------------------
-- Life areas
-- ---------------------------------------------------------------------------
create table if not exists life_areas (
  id            uuid primary key default uuid_generate_v4(),
  workspace_id  uuid references workspaces(id),
  user_id       uuid references profiles(id),
  name          text not null,
  slug          text not null,
  color         text default '#6366f1',
  icon          text,
  is_system     boolean default false,
  created_at    timestamptz default now()
);

-- System-level life areas (no user_id / workspace_id)
insert into life_areas (name, slug, color, is_system) values
  ('Work',     'work',     '#3b82f6', true),
  ('Study',    'study',    '#8b5cf6', true),
  ('Business', 'business', '#10b981', true),
  ('Sport',    'sport',    '#f59e0b', true),
  ('Health',   'health',   '#ef4444', true),
  ('Admin',    'admin',    '#6b7280', true),
  ('Social',   'social',   '#ec4899', true),
  ('Content',  'content',  '#f97316', true),
  ('Finance',  'finance',  '#14b8a6', true),
  ('Personal', 'personal', '#a78bfa', true)
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- Projects
-- ---------------------------------------------------------------------------
create table if not exists projects (
  id            uuid primary key default uuid_generate_v4(),
  workspace_id  uuid references workspaces(id) on delete cascade,
  user_id       uuid not null references profiles(id),
  life_area_id  uuid references life_areas(id),
  name          text not null,
  description   text,
  status        text default 'active'
                  check (status in ('active', 'waiting', 'paused', 'backlog', 'done', 'archived')),
  priority      text not null default 'medium'
                  check (priority in ('high', 'medium', 'low')),
  next_action   text,
  risk          text,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- User rules / Personal Operating System
-- ---------------------------------------------------------------------------
create table if not exists user_rules (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid not null references profiles(id) on delete cascade,
  workspace_id  uuid references workspaces(id),
  title         text not null,
  rule_text     text not null,
  category      text,
  life_area_id  uuid references life_areas(id),
  is_active     boolean default true,
  priority      integer default 5,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Daily check-ins
-- ---------------------------------------------------------------------------
create table if not exists daily_checkins (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid not null references profiles(id) on delete cascade,
  workspace_id    uuid references workspaces(id),
  checkin_date    date not null default current_date,
  wake_time       text,
  sleep_quality   integer check (sleep_quality between 1 and 10),
  energy_level    integer check (energy_level between 1 and 10),
  body_status     text,
  mood            text,
  fixed_events    jsonb default '[]',
  important_tasks jsonb default '[]',
  raw_input       text,
  available_hours numeric(4,2),
  day_constraints text,
  created_at      timestamptz default now(),
  unique(user_id, checkin_date)
);

-- ---------------------------------------------------------------------------
-- Daily plans  (AI-generated)
-- ---------------------------------------------------------------------------
create table if not exists daily_plans (
  id                       uuid primary key default uuid_generate_v4(),
  user_id                  uuid not null references profiles(id) on delete cascade,
  workspace_id             uuid references workspaces(id),
  checkin_id               uuid references daily_checkins(id),
  plan_date                date not null default current_date,
  status_summary           text,
  day_mode                 text,
  main_win                 text,
  top_priorities           jsonb default '[]',
  time_blocks              jsonb default '[]',
  energy_strategy          text,
  not_today_list           jsonb default '[]',
  evening_review_questions jsonb default '[]',
  motivational_closing     text,
  raw_ai_response          jsonb,
  model_used               text,
  review_context_used      boolean default false,
  generated_at             timestamptz default now(),
  created_at               timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Evening reviews
-- ---------------------------------------------------------------------------
create table if not exists evening_reviews (
  id                    uuid primary key default uuid_generate_v4(),
  user_id               uuid not null references profiles(id) on delete cascade,
  workspace_id          uuid references workspaces(id),
  plan_id               uuid references daily_plans(id),
  review_date           date not null default current_date,
  completed_items       jsonb default '[]',
  missed_items          jsonb default '[]',
  energy_end            integer check (energy_end between 1 and 10),
  biggest_win           text,
  lessons               text,
  carry_over_to_tomorrow jsonb default '[]',
  raw_reflection        text,
  overall_day_rating    integer check (overall_day_rating between 1 and 10),
  created_at            timestamptz default now(),
  unique(user_id, review_date)
);

-- ---------------------------------------------------------------------------
-- AI usage log  (CP-203 — daily spending cap)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Background Dev Team — work orders (OP-Backend-001)
--
-- work_orders is the ownership root (user_id/workspace_id). The 5 tables
-- below it are children scoped by work_order_id and carry no user_id of
-- their own — ownership is enforced via a join back to work_orders, both in
-- RLS (see policies below) and in the FastAPI service layer. See
-- docs/background-dev-team-system-design.md for the full design.
--
-- approval_scopes/review_packages are 1:1 with a work order (unique
-- work_order_id); work_orders itself does not store an approval_scope_id
-- column, to avoid a circular insert-ordering dependency — the API looks
-- it up via the reverse FK instead.
-- ---------------------------------------------------------------------------
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
  team_type             text not null default 'development',
  time_limit_minutes     integer not null default 90,
  acceptance_criteria    jsonb not null default '[]',
  missing_context        jsonb not null default '[]',
  recommended_next_step  text,
  started_at            timestamptz,
  completed_at          timestamptz,
  -- Optional Control-Plane/Target-Repo split (OP-Runner-RepoPath-001) — see
  -- supabase/migrations/009_work_orders_target_repo.sql for the full
  -- rationale. Both nullable: absent means "this work order targets
  -- CommandPilot itself," same as every work order before this existed.
  target_repo_name      text,
  target_repo_path      text,
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
-- Work order steps (OP-Runner-001) — the visible execution/ticket plan.
-- A step is the plan-level unit Serkan looks at ("what's my team doing right
-- now"); an agent_run is the execution-level audit record. Same join-based
-- ownership pattern as the other work_orders children above.
-- ---------------------------------------------------------------------------
create table if not exists work_order_steps (
  id                    uuid primary key default uuid_generate_v4(),
  work_order_id         uuid not null references work_orders(id) on delete cascade,
  title                 text not null,
  description           text,
  status                text not null default 'pending'
                          check (status in (
                            'pending', 'queued', 'running', 'blocked',
                            'completed', 'failed', 'skipped'
                          )),
  assigned_role         text not null
                          check (assigned_role in ('product', 'architect', 'coder', 'qa', 'reviewer', 'reporter')),
  order_index           integer not null default 0,
  acceptance_criteria   jsonb not null default '[]',
  started_at            timestamptz,
  completed_at          timestamptz,
  output_summary        text,
  blocked_reason        text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Referential integrity: workspaces.owner_id → profiles(id)
-- Added after profiles table creation to avoid circular dependency
-- ---------------------------------------------------------------------------
alter table workspaces
  add constraint fk_workspaces_owner
  foreign key (owner_id) references profiles(id) on delete cascade;

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
create index if not exists idx_daily_checkins_user_date
  on daily_checkins(user_id, checkin_date desc);

create index if not exists idx_daily_plans_user_date
  on daily_plans(user_id, plan_date desc);

create index if not exists idx_evening_reviews_user_date
  on evening_reviews(user_id, review_date desc);

create index if not exists idx_user_rules_user_active
  on user_rules(user_id, is_active);

create index if not exists idx_projects_user
  on projects(user_id, status);

create index if not exists idx_ai_usage_log_user_date
  on ai_usage_log(user_id, request_date desc);

create index if not exists idx_work_orders_user
  on work_orders(user_id, status);

create index if not exists idx_agent_runs_work_order
  on agent_runs(work_order_id, created_at);

create index if not exists idx_activity_logs_work_order
  on activity_logs(work_order_id, created_at);

create index if not exists idx_artifacts_work_order
  on artifacts(work_order_id, created_at);

create index if not exists idx_work_order_steps_work_order
  on work_order_steps(work_order_id, order_index);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table workspaces      enable row level security;
alter table profiles        enable row level security;
alter table workspace_members enable row level security;
alter table life_areas      enable row level security;
alter table projects        enable row level security;
alter table user_rules      enable row level security;
alter table daily_checkins  enable row level security;
alter table ai_usage_log    enable row level security;
alter table daily_plans     enable row level security;
alter table evening_reviews enable row level security;
alter table work_orders      enable row level security;
alter table approval_scopes  enable row level security;
alter table agent_runs       enable row level security;
alter table activity_logs    enable row level security;
alter table artifacts        enable row level security;
alter table review_packages  enable row level security;
alter table work_order_steps enable row level security;

-- profiles
create policy "Users can view own profile"
  on profiles for select using (auth.uid() = id);
create policy "Users can update own profile"
  on profiles for update using (auth.uid() = id);
create policy "Users can insert own profile"
  on profiles for insert with check (auth.uid() = id);

-- workspaces
create policy "Workspace members can view workspaces"
  on workspaces for select using (
    exists (
      select 1 from workspace_members wm
      where wm.workspace_id = workspaces.id
        and wm.user_id = auth.uid()
    )
  );

-- workspace_members
create policy "Workspace members can view memberships"
  on workspace_members for select using (user_id = auth.uid());

-- daily_checkins
create policy "Users own checkins"
  on daily_checkins for all using (auth.uid() = user_id);

-- daily_plans
create policy "Users own plans"
  on daily_plans for all using (auth.uid() = user_id);

-- evening_reviews
create policy "Users own reviews"
  on evening_reviews for all using (auth.uid() = user_id);

-- ai_usage_log: read-only for users (writes via service role only)
create policy "Users view own usage"
  on ai_usage_log for select using (auth.uid() = user_id);

-- user_rules
create policy "Users own rules"
  on user_rules for all using (auth.uid() = user_id);

-- life_areas: system areas visible to all, personal areas only to owner
create policy "Life areas visible"
  on life_areas for select using (is_system = true or auth.uid() = user_id);
create policy "Users manage own life areas"
  on life_areas for insert with check (auth.uid() = user_id);
create policy "Users update own life areas"
  on life_areas for update using (auth.uid() = user_id);
create policy "Users delete own life areas"
  on life_areas for delete using (auth.uid() = user_id);

-- projects
create policy "Users own projects"
  on projects for all using (auth.uid() = user_id);

-- work_orders (Background Dev Team) — see docs/background-dev-team-system-design.md
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

create policy "Users own work_order_steps via work order"
  on work_order_steps for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = work_order_steps.work_order_id
        and wo.user_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- Trigger: auto-create profile on new user signup
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger as $$
declare
  personal_workspace_id uuid;
begin
  insert into public.profiles (id, display_name)
  values (new.id, new.raw_user_meta_data->>'display_name')
  on conflict (id) do nothing;

  insert into public.workspaces (name, slug, owner_id)
  values (
    'Personal Workspace',
    'personal-' || replace(new.id::text, '-', ''),
    new.id
  )
  on conflict (slug) do nothing
  returning id into personal_workspace_id;

  -- If the workspace already existed (conflict), look it up by slug
  if personal_workspace_id is null then
    select id into personal_workspace_id
    from public.workspaces
    where slug = 'personal-' || replace(new.id::text, '-', '');
  end if;

  update public.profiles
  set workspace_id = personal_workspace_id
  where id = new.id and workspace_id is null;

  insert into public.workspace_members (workspace_id, user_id, role)
  values (personal_workspace_id, new.id, 'owner')
  on conflict (workspace_id, user_id) do nothing;

  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
