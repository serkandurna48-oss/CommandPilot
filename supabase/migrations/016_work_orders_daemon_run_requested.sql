-- Migration: work_orders.daemon_run_requested_at — the trigger signal for
-- scripts/run_work_order_daemon.py
--
-- Purely additive, nullable column — a work order that never uses the
-- autonomous-start feature behaves exactly as before. NULL = no auto-start
-- requested. Set (by the "Autonom starten" button in
-- frontend/components/operator/LifecycleControls.tsx, at status='queued')
-- = "run me the moment a local daemon notices." The daemon polls
-- GET /api/work-orders/me, picks up rows where status='queued' and this
-- field is not null (oldest first), clears it back to NULL as its claim
-- (before starting anything, so a crash mid-claim or a second poll cycle
-- can never double-start the same work order), then invokes
-- scripts/run_work_order.py --mode execute exactly as a human would type
-- it — no new execution/safety logic, this column is the only new state.

alter table work_orders
  add column if not exists daemon_run_requested_at timestamptz;
