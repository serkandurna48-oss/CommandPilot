-- Migration: OP-Runner-001 — work_order_steps (the visible execution/ticket plan)
-- A work order's steps are its ordered, human-readable plan. Unlike agent_runs
-- (one row per agent-role execution, useful for audit) steps are what Serkan
-- actually looks at to answer "what is my background team doing right now,
-- what's done, what's blocked." A step and an agent_run can both exist for the
-- same unit of work — a step is the plan-level unit, a run is the
-- execution-level unit; they are not the same table on purpose.
--
-- Ownership: same join-based pattern as the other work_orders children
-- (006_work_orders.sql) — no user_id column here, enforced via work_order_id
-- join in both RLS and the FastAPI service layer.

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

create index if not exists idx_work_order_steps_work_order
  on work_order_steps(work_order_id, order_index);

alter table work_order_steps enable row level security;

create policy "Users own work_order_steps via work order"
  on work_order_steps for all using (
    exists (
      select 1 from work_orders wo
      where wo.id = work_order_steps.work_order_id
        and wo.user_id = auth.uid()
    )
  );
