-- Migration: idempotent result-import keys (CP-OP03)
--
-- scripts/import_work_order_result.py's activity-log and artifact writes
-- were plain INSERTs with no natural conflict target — re-running
-- --mode import-result against the same result.json (or recovering from a
-- partial prior import) duplicated every activityLogs/artifacts entry.
--
-- dedup_key is a POSITION-based key computed by the import script:
--   sha256(f"{agent_run_id}|activity_log|{index}")
--   sha256(f"{agent_run_id}|artifact|{index}")
-- Deliberately NOT content-based (e.g. hash(agent_run_id + the full item's
-- JSON)) — two genuinely identical log/artifact entries at different
-- positions in the same result must stay distinct rows, not collapse into
-- one. Keying on (agent_run_id, kind, index) instead means: importing the
-- exact same result.json twice reproduces the same keys (safe no-op
-- upsert); a corrected re-import of the SAME agent_run's result updates the
-- same positional slots rather than duplicating; two different agent_runs
-- (e.g. CP-OP02 retry attempts, each with their own agent_run_id) never
-- collide. The full, untruncated SHA-256 hex digest is stored (64 chars).
--
-- Non-import callers (e.g. the harness's own "runner_started" activity log
-- entry, or any future manual UI-authored entry) never set dedup_key — it
-- stays NULL for them, and behaves exactly like a plain insert (see below).
--
-- Plain (non-partial) UNIQUE index on (work_order_id, dedup_key): PostgreSQL
-- never considers two NULLs equal for uniqueness purposes, so rows with
-- dedup_key IS NULL are never constrained against each other or against a
-- real key — a normal index is correct for both the deduped (non-null) and
-- undeduped (null) cases, and PostgREST can target it directly as an
-- on_conflict key with no partial-index workaround needed.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS are
-- safe to re-run.

alter table activity_logs add column if not exists dedup_key text;
alter table artifacts     add column if not exists dedup_key text;

create unique index if not exists idx_activity_logs_dedup_key
  on activity_logs (work_order_id, dedup_key);

create unique index if not exists idx_artifacts_dedup_key
  on artifacts (work_order_id, dedup_key);
