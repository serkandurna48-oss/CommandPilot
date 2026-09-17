-- Migration: transition_work_order() DB function (CP-OP01)
--
-- Problem this closes: work_orders.status changes and their activity_logs
-- audit entry used to be two separate application-layer calls (an UPDATE
-- then an INSERT, in backend/app/services/work_order_service.py). A crash,
-- timeout, or bug between those two calls could commit a status change with
-- no audit trail for it. Wrapping both writes inside a single plpgsql
-- function means they share one implicit transaction: if the activity_logs
-- insert fails for any reason, the status update is rolled back with it. A
-- successful transition without its audit entry cannot happen.
--
-- This function is also now the single authoritative state machine for
-- work_orders.status. Before this migration, any status could be PATCHed to
-- any other status with zero validation. The transition table below is the
-- full legal graph, including the human-only resume/cancel edges added in
-- this same ticket:
--   needs_approval | blocked | failed | rework_requested -> queued
--   <any non-terminal status>                             -> cancelled
-- "Human-only" is enforced by convention for now (nothing in scripts/ calls
-- these edges), not by a hard actor check — see CP-OP01 report.
--
-- Re-requesting the status a work order is already in (e.g. a repeated
-- result import after a network retry) is a safe no-op: no transition
-- happened, so no audit log entry is written for it either.
--
-- Idempotent: CREATE OR REPLACE FUNCTION is safe to re-run.

create or replace function transition_work_order(
  p_work_order_id uuid,
  p_to_status text,
  p_source text default 'ui',
  p_reason text default null
)
returns work_orders
language plpgsql
set search_path = public
as $$
declare
  v_current text;
  v_actor text;
  v_allowed text[];
  v_updated work_orders;
begin
  select status into v_current
  from work_orders
  where id = p_work_order_id
  for update;

  if not found then
    raise exception 'work_order_not_found';
  end if;

  if v_current = p_to_status then
    select * into v_updated from work_orders where id = p_work_order_id;
    return v_updated;
  end if;

  v_allowed := case v_current
    when 'draft'            then array['approved', 'cancelled']
    when 'approved'         then array['queued', 'cancelled']
    when 'queued'           then array['running', 'cancelled']
    when 'running'          then array['needs_approval', 'blocked', 'failed', 'review_ready', 'cancelled']
    when 'needs_approval'   then array['queued', 'cancelled']
    when 'blocked'          then array['queued', 'cancelled']
    when 'failed'           then array['queued', 'cancelled']
    when 'review_ready'     then array['accepted', 'rework_requested', 'cancelled']
    when 'rework_requested' then array['queued', 'cancelled']
    else array[]::text[]  -- accepted, cancelled: terminal, no outgoing edges
  end;

  if not (p_to_status = any(v_allowed)) then
    raise exception 'illegal_transition: % -> % is not allowed', v_current, p_to_status;
  end if;

  if p_to_status = 'review_ready' and not exists (
    select 1 from review_packages where work_order_id = p_work_order_id
  ) then
    raise exception 'Cannot set status to review_ready: no review package exists for this work order yet.';
  end if;

  v_actor := case when p_source = 'ui' then 'human' else 'system' end;

  update work_orders
  set status = p_to_status,
      started_at = case
        when started_at is null
         and p_to_status in ('running', 'needs_approval', 'blocked', 'review_ready', 'accepted', 'rework_requested')
        then now()
        else started_at
      end,
      completed_at = case
        when p_to_status in ('accepted', 'failed', 'cancelled') then now()
        else completed_at
      end
  where id = p_work_order_id
  returning * into v_updated;

  insert into activity_logs (work_order_id, level, event_type, message, metadata)
  values (
    p_work_order_id,
    case when p_to_status in ('blocked', 'failed', 'cancelled', 'needs_approval') then 'warning' else 'info' end,
    'status_transition',
    format('Status changed from %s to %s', v_current, p_to_status),
    jsonb_build_object(
      'from_status', v_current,
      'to_status', p_to_status,
      'actor', v_actor,
      'source', p_source,
      'reason', p_reason
    )
  );

  return v_updated;
end;
$$;

grant execute on function transition_work_order(uuid, text, text, text) to service_role;
