-- CP-206: Extend projects table for full CRUD + morning plan integration
-- Adds priority, next_action, risk columns; expands status to include waiting/backlog/done

-- Safety: migrate any existing 'completed' rows before constraint change
update projects set status = 'done' where status = 'completed';

-- Replace status constraint with expanded set of values
alter table projects drop constraint if exists projects_status_check;
alter table projects
  add constraint projects_status_check
  check (status in ('active', 'waiting', 'paused', 'backlog', 'done', 'archived'));

-- New columns (all additive — no data loss)
alter table projects
  add column if not exists priority    text not null default 'medium'
    check (priority in ('high', 'medium', 'low')),
  add column if not exists next_action text,
  add column if not exists risk        text;
