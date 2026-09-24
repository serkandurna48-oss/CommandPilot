-- Migration: runner_connections + runner_pairing_requests — guided,
-- revocable pairing for a local runner (scripts/run_work_order_daemon.py),
-- replacing the "copy a Supabase session token out of browser DevTools"
-- workflow (23.09.2026 product decision: a customer-facing product cannot
-- ask a user to do that).
--
-- Device-flow-shaped, using only stdlib-grade primitives (secrets.token_urlsafe
-- + sha256 in the backend, no custom cryptography):
--   1. The runner calls POST /api/runner-pairing/request (unauthenticated) —
--      backend generates the actual long-lived runner_token right away and
--      stores only its SHA-256 hash here, plus a short human-typeable
--      user_code. The row starts with user_id/workspace_id NULL — a token
--      exists but authorizes nothing yet.
--   2. A human, already logged into the web app, types the user_code into
--      the "Runner verbinden" UI. POST /api/runner-pairing/approve (real
--      Supabase-authenticated request) fills in user_id/workspace_id on the
--      matching runner_connections row — this is the ONLY step that binds
--      the token to an actual account, and it happens inside an
--      authenticated browser session, never via a copied credential.
--   3. The runner, still polling runner_pairing_requests.status, sees
--      'approved' and starts using the token it already had from step 1.
--
-- app.auth.get_current_user() accepts a runner token transparently
-- alongside a real Supabase JWT (distinguished by a fixed, non-secret
-- prefix on the token string, checked before ever touching the DB) — every
-- existing ownership check (require_owned_record, .eq("user_id", ...))
-- keeps working unchanged, because a resolved runner connection produces
-- the exact same CurrentUser shape a real session would.

create table if not exists runner_connections (
  id            uuid primary key default uuid_generate_v4(),
  -- NULL until approved (step 2 above) — an unapproved connection has a
  -- valid-looking token that authorizes nothing, by construction (every
  -- lookup requires user_id IS NOT NULL).
  user_id       uuid references profiles(id) on delete cascade,
  workspace_id  uuid references workspaces(id),
  label         text not null default 'Lokaler Runner',
  -- SHA-256 hex of the actual bearer token. The raw token is generated
  -- once, returned once (to the runner, in the /request response), and
  -- never persisted anywhere in plaintext — same principle as a password
  -- hash, even though this isn't a password.
  token_hash    text not null,
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz,
  revoked_at    timestamptz
);

create unique index if not exists idx_runner_connections_token_hash
  on runner_connections(token_hash);
create index if not exists idx_runner_connections_active_by_user
  on runner_connections(user_id) where revoked_at is null;

create table if not exists runner_pairing_requests (
  id            uuid primary key default uuid_generate_v4(),
  connection_id uuid not null references runner_connections(id) on delete cascade,
  -- Short, human-typeable (e.g. "ABCD-1234") — shown by the runner in its
  -- terminal output, typed by the human into the browser. Not the secret;
  -- the secret is runner_connections.token_hash's plaintext counterpart,
  -- which never touches this table at all.
  user_code     text not null,
  status        text not null default 'pending'
                  check (status in ('pending', 'approved', 'denied', 'expired')),
  created_at    timestamptz not null default now(),
  expires_at    timestamptz not null
);

create unique index if not exists idx_runner_pairing_user_code
  on runner_pairing_requests(user_code) where status = 'pending';

alter table runner_connections enable row level security;
alter table runner_pairing_requests enable row level security;

-- Both tables are backend-only (service-role key, bypasses RLS) by design —
-- pairing must work before a user_id even exists on the row, so there is no
-- meaningful auth.uid() to write a policy against for runner_pairing_requests.
-- RLS is enabled with zero policies on both (the project's existing
-- "defense in depth, not the only protection" stance, CLAUDE.md) except one
-- explicit owner-read policy on runner_connections, in case a future direct
-- client read is ever added.
--
-- NOT idempotent: CREATE POLICY has no IF NOT EXISTS guard, matching
-- 004_ai_usage_log.sql / 006_work_orders.sql / 007_work_order_steps.sql /
-- 013_suggested_action_decisions.sql. Run once.
create policy "Users own runner_connections"
  on runner_connections for select using (auth.uid() = user_id);
