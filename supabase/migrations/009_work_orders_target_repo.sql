-- Migration: OP-Runner-RepoPath-001 — work_orders.target_repo_name / target_repo_path
--
-- Lets a work order optionally point at an external "target repo" distinct
-- from CommandPilot itself (the Control Plane repo) — e.g. a work order
-- that edits Sommercamps/CampsPilot rather than CommandPilot's own code.
-- Both columns are purely descriptive context surfaced in the generated
-- runner prompt and the Local Runner panel; CommandPilot never reads from,
-- cd's into, or executes anything at target_repo_path itself — it is a
-- path hint for the human/agent working in that other repo, not a trigger
-- for automatic shell commands. See
-- docs/background-dev-team-runbook.md and
-- scripts/runner_adapters/base.py's build_runner_prompt().
--
-- externalRepoMode is deliberately NOT a stored column — it's derived
-- (bool(targetRepoPath)) in frontend/lib/workOrderMapper.ts, avoiding a
-- second source of truth that could drift from target_repo_path itself.
--
-- Safe for existing rows: both columns are nullable, no default needed —
-- an absent target_repo_path means "this work order targets the Control
-- Plane repo itself" (`repo` field), the same as every work order before
-- this migration. Idempotent: IF NOT EXISTS guards both column adds.

alter table work_orders
  add column if not exists target_repo_name text,
  add column if not exists target_repo_path text;
