# Background Dev Team — System Design

Status: **persisted control plane (OP-Backend-001)**. A real backend now
exists — `work_orders` + 5 related tables, Pydantic models, and 9 FastAPI
endpoints — but no autonomous worker executes anything yet, and the SQL
migration has not been run against any live Supabase project (that's a
manual step for Serkan; see §8). The frontend still works with zero backend
deployed, falling back to seed data automatically.

## 0. Strategic Framing

CommandPilot is not primarily a daily planner. The daily-plan / morning
check-in / evening review loop is one module — the "Daily Interface." The
actual product is a **personal Business & Execution OS**, and the Work Order
system is a **general-purpose primitive** of that OS, not a dev-tool bolt-on.

A Work Order can eventually represent a code task, a sales follow-up, a
customer-onboarding step, a content draft, a study session, or an internal
process optimization — anything with a goal, a bounded scope of allowed
action, and a reviewable outcome. **The MVP scope stays narrow on purpose**:
the Background Dev Team (code work orders against this repo and, later,
other repos) is the first concrete, highest-leverage use case, because it's
the one CommandPilot can validate against its own codebase without needing
any external integration. Nothing in the data model (§2) is dev-specific —
`repo` is just a string, `goal`/`acceptanceCriteria`/`ApprovalScope` are
domain-agnostic — so a "Follow up with lead X" or "Draft onboarding email
for client Y" work order fits the same six tables without a schema change.
What *would* need new work before other domains are usable: domain-specific
`ArtifactType`s (a "sales_call_summary" artifact, say) and a different set of
default safety rules per domain (§4's rules are dev-specific — "keine
destructive Git-Kommandos" doesn't mean anything for a sales work order).
That generalization is explicitly not attempted in this pass.

CommandPilot's role throughout is the **hull around Claude/Codex/OpenAI**:
it holds the context, the goal, the rules, the approval scope, the activity
log, the artifacts, the review package, and (later) the optimization loop
that feeds a completed work order's lessons back into the next one. It does
not (yet) hold the model call itself — see §5/§7.

## 1. System Design

**Judge / Executor split.** A Work Order is created (by Serkan, or later by
another CommandPilot flow) with a goal and a time limit. A **Judge** role
plans the work, defines/refines acceptance criteria, and decides on anything
ambiguous *within the Approval Scope* — it does not stop to ask about small
things. An **Executor** (in this MVP: a sequence of specialized agent roles
— see §2) carries out clearly bounded sub-tasks. The moment an action falls
outside the Approval Scope, execution pauses (`needs_approval`) rather than
the Judge deciding to widen its own mandate.

**One-time Approval Scope.** Every Work Order has exactly one `ApprovalScope`,
fixed at creation time (`POST /api/work-orders` requires it in the same
request body — there is no way to create a work order without one). It is
the single source of truth for "what is this order allowed to do" — allowed
actions, actions that need a human nod, actions that are blocked outright,
path restrictions, and a runtime/cost ceiling. Widening it mid-run is itself
a "needs approval" action (§4), never a silent Judge decision, and there is
currently no endpoint that mutates an existing `approval_scopes` row at all
— by omission, not oversight: scope changes deserve their own reviewed
work order, not a quiet `PATCH`.

**Everything is logged.** Every state transition and every non-trivial step
produces an `ActivityLogEntry` (`POST /api/work-orders/{id}/activity-log`).
This is what makes "no rückfrage bei Kleinkram" safe: the human doesn't need
to be asked in real time because they can always reconstruct what happened
and why from the log after the fact.

**Review Package at the end.** Regardless of outcome — done, blocked, or
failed — the last thing produced is a `ReviewPackage`
(`PUT /api/work-orders/{id}/review-package`, an upsert): what happened, what
changed, what's risky, what's still open, and an explicit verdict. This is
the only artifact a human is expected to read end-to-end before accepting.

```
Work Order + ApprovalScope created (one POST, one transaction-like insert pair)
      │
      ▼
  Judge (Product → Architect) plans, refines acceptance criteria
      │
      ▼
  Executor (Coder → QA → Reviewer) works within scope
      │  (hits a "needs approval" action) ──► needs_approval ──► human decides
      │  (hits missing context / external dependency) ──► blocked
      ▼
  Reporter produces ReviewPackage
      │
      ▼
  review_ready ──► human reviews ──► accepted | rework_requested
```

## 2. Data Models

Six entities, now backed by real Postgres tables (`supabase/schema.sql` +
`supabase/migrations/006_work_orders.sql`) and Pydantic models
(`backend/app/models/work_order.py`):

| Entity | DB table | Purpose |
| --- | --- | --- |
| `WorkOrder` | `work_orders` | The unit of work: goal, repo, status, time limit, acceptance criteria. Ownership root (`user_id`, `workspace_id`). |
| `ApprovalScope` | `approval_scopes` | 1:1 with a work order (`work_order_id unique`). The one-time-defined permission envelope. |
| `AgentRun` | `agent_runs` | One execution of one agent role against a work order. |
| `ActivityLogEntry` | `activity_logs` | Append-only, timestamped event, optionally tied to a specific agent run. |
| `Artifact` | `artifacts` | Anything produced along the way — a plan, a diff, test output, the generated runner prompt itself. |
| `ReviewPackage` | `review_packages` | 1:1 with a work order. The final human-facing summary + verdict. |

`work_orders` is the only one of the six with `user_id`/`workspace_id`. The
other five are children scoped by `work_order_id` and own no ownership
column of their own — enforced two ways simultaneously:
- **RLS** (defense in depth, bypassed by the backend's service-role key but
  still the correct posture for any future direct-from-client access): each
  child table's policy is `exists (select 1 from work_orders wo where
  wo.id = <child>.work_order_id and wo.user_id = auth.uid())`.
- **Service layer** (what actually protects the FastAPI endpoints today):
  every child-table route calls `require_owned_record("work_orders",
  work_order_id, user)` first — the same helper `projects.py`/`plans.py` use
  — and only then touches the child table, scoped to that verified
  `work_order_id`. `update_agent_run` additionally filters by
  `work_order_id` (not just `run_id`) so one work order's run IDs can never
  be used to reach into another work order's data.

`approval_scopes.work_order_id` and `review_packages.work_order_id` are
`unique`. `work_orders` does **not** store an `approval_scope_id` column —
that would create a circular "which row do I insert first" dependency at
creation time. Instead the API looks the scope up via the reverse FK and
attaches `approval_scope_id` to the response (see §3).

`MissingContextItem` (a required/optional gap like "ticket descriptions")
lives as a `jsonb` column on `work_orders` rather than its own table — it's
small, always read/written as a whole list, and never queried by its
contents, so a join-table would be pure overhead.

## 3. camelCase ↔ snake_case: the Mapper Convention

The frontend `WorkOrder`/`ApprovalScope`/etc. types
(`frontend/types/index.ts`) are **camelCase** — they were designed in the
mock-only pass before any backend existed. The backend
(`backend/app/models/work_order.py`, `supabase/schema.sql`) is **snake_case**,
matching every other resource in this codebase (`Project`, `DailyPlan`, ...).
Neither convention was changed to match the other:
- Rewriting the frontend types to snake_case would have meant re-touching
  every component built against them (`OperatorManager`, `WorkOrderDetail`,
  `RunnerPromptPanel`, `StatusFlowStrip`) for a purely cosmetic reason.
- Rewriting the backend to camelCase would break the one convention every
  other resource in this repo relies on.

Instead, **`frontend/lib/workOrderMapper.ts` is the single seam** where the
two conventions meet:
- `Api*` interfaces (`ApiWorkOrder`, `ApiApprovalScope`, ...) describe the
  raw snake_case wire format exactly as the backend returns it.
- `mapXFromApi()` functions convert each `Api*` shape into its camelCase
  domain type.
- `mapWorkOrderCreateToApi()` converts a camelCase creation input back into
  the snake_case payload `POST /api/work-orders` expects.

`frontend/lib/api.ts`'s `api.workOrders.*` functions return raw `Api*`
shapes and never do the conversion themselves — they're a pure transport
client, consistent with every other resource in that file. Callers (the
operator pages) always route through the mapper before touching the data.
**Nothing outside `workOrderMapper.ts` should reference a snake_case field
name for this feature** — if a new component needs one, that's a sign the
mapper is missing a field, not a reason to reach past it.

## 4. Status Flow

`WorkOrderStatus` (11 states, rendered end-to-end in the UI via
`StatusFlowStrip`, mirrored by a `check` constraint on `work_orders.status`):

| Status | Meaning |
| --- | --- |
| `draft` | Defined, not yet approved to run. |
| `approved` | Approval scope signed off; not yet queued. |
| `queued` | Waiting for an executor to pick it up. |
| `running` | An agent run is actively executing. |
| `needs_approval` | Paused — hit an action outside `allowedActions`. |
| `blocked` | Paused — missing context or an external dependency. |
| `failed` | An agent run failed; not reviewed as done. |
| `review_ready` | Review package produced, waiting on human review. |
| `accepted` | Human reviewed and accepted the outcome. |
| `rework_requested` | Human reviewed and asked for changes. |
| `cancelled` | Withdrawn before or during execution. |

`started_at`/`completed_at` are **never client-settable** — `PATCH
/api/work-orders/{id}` only accepts `status`, `recommended_next_step`, and
`missing_context`. `work_order_service.update_work_order()` derives the
timestamps from the status transition itself (first time the status enters
`{running, needs_approval, blocked, review_ready, accepted,
rework_requested}` → set `started_at` if unset; entering `{accepted, failed,
cancelled}` → set `completed_at`), the same "derive timestamps server-side,
never trust the client" rule `usage_service.py` already follows for
`request_date`.

`AgentRunStatus` (`queued → running → completed`, with `blocked`/`failed` as
off-ramps) is deliberately a separate, smaller enum — a work order's overall
status is a function of its runs, not identical to any single run's status.

## 5. Safety Rules

Rendered on every operator page (`SafetyRulesPanel`) and baked into every
generated runner prompt (`generateRunnerPrompt`, both read from the single
source of truth `frontend/lib/safetyRules.ts`):

**Autonom erlaubt (kein Approval nötig):** Repo lesen · Plan erstellen ·
Code ändern innerhalb Scope · Tests / Lint / Typecheck ausführen · Lokale
Artifacts erzeugen · Review Package schreiben

**Braucht Approval:** Dependencies installieren · Externe Services anbinden ·
Migrationen ausführen · Push / PR erstellen · Laufzeit- oder Kostenlimit
erhöhen · Große Architekturänderungen

**Blockiert — immer, unabhängig vom Approval Scope:** Deployments ·
Production-Daten ändern · Secrets anzeigen oder loggen · E-Mails senden ·
Zahlungen auslösen · Destructive Git-Kommandos · Direkte Änderungen auf main
· Userdaten exportieren

A work order's `ApprovalScope` can only **narrow** these defaults further,
never widen them — nothing in this system (frontend or backend) can promote
a repo-wide-blocked action to allowed for a single work order. As of
OP-Runner-001 (§12) this is a **partial runtime check, not just
convention**: `backend/app/core/safety_rules.py` + a Pydantic validator on
`ApprovalScopeCreate` reject any scope whose `allowed_actions` or
`requires_approval` contains a keyword matching the blocked list (see §12
for what this does and does not cover).

## 6. Backend API

9 endpoints under `/api/work-orders`, all bearer-token-protected like every
other resource (`backend/app/routers/work_orders.py`,
`backend/app/services/work_order_service.py`):

| Method | Endpoint | Notes |
| --- | --- | --- |
| POST | `/api/work-orders` | Creates the work order **and** its approval scope in one call. If the scope insert fails, the work order row is deleted (compensating action — no real multi-statement transaction available via the Supabase REST client, same non-transactional style `ensure_user_workspace` already uses). |
| GET | `/api/work-orders/me` | Flat list, each row's `approval_scope_id` resolved via a second batched query (`in_(work_order_ids)`), not a per-row query. |
| GET | `/api/work-orders/{id}` | The full aggregate: order + approval_scope + agent_runs + activity_log + artifacts + review_package — exactly what the detail page needs in one call. |
| PATCH | `/api/work-orders/{id}` | `status` / `recommended_next_step` / `missing_context` only. |
| POST | `/api/work-orders/{id}/activity-log` | Append-only. |
| POST | `/api/work-orders/{id}/agent-runs` | |
| PATCH | `/api/work-orders/{id}/agent-runs/{run_id}` | Scoped by **both** `run_id` and `work_order_id`. |
| POST | `/api/work-orders/{id}/artifacts` | |
| PUT | `/api/work-orders/{id}/review-package` | Upsert on `work_order_id` (unique constraint). |

No embedding/joins via PostgREST (`select=*,child(*)`) are used anywhere —
every related-table fetch is a separate, explicit query in Python. This was
a deliberate choice over relying on PostgREST's relationship-embedding
syntax, which behaves differently across versions for a 1:1-via-unique-
constraint relationship (array vs. single object) and isn't used anywhere
else in this codebase; explicit queries are slightly more verbose but
version-independent and consistent with `project_service.py`.

## 7. Frontend: API-Ready, Mocks as Fallback

`frontend/components/operator/OperatorManager.tsx` and
`frontend/app/operator/[id]/page.tsx` both now **try the real API first**
(`api.workOrders.listMine()` / `api.workOrders.get(id)`, mapped via
`workOrderMapper.ts`) and **fall back to `mockWorkOrders.ts` only if that
call throws** — which it will today, since `006_work_orders.sql` hasn't been
run against any real Supabase project yet, so the tables don't exist. This
satisfies "Mocks nur noch Fallback/Seed-Daten, nicht Kernarchitektur"
literally: the mock data is no longer what the components are built around,
it's what they degrade to.

`WorkOrderDetail.tsx` was refactored to take a fully-formed
`WorkOrderDetailBundle` (order + approvalScope + agentRuns + activityLog +
artifacts + reviewPackage) as props instead of reaching into
`mockWorkOrders.ts`'s lookup helpers itself — so it's identical whether the
bundle came from the API or the mock fallback. The page component is the
only place that knows which source it's using.

**What "API-ready" does not yet mean:** there is no "Create Work Order" form
in the UI. `mapWorkOrderCreateToApi()` and `api.workOrders.create()` exist
and are ready to be called — the missing piece is a form component, not
plumbing. This was deliberately deferred (see §9, next step #1) to keep this
pass's diff centered on persistence, not UI.

## 8. Route Naming: `/operator` vs. alternatives

**Recommendation: keep `/operator` for now; revisit at v1 (§10), don't
rename today.**

Considered alternatives:
- **`/work-orders`** — accurate to the data model and the strategic framing
  in §0 (work orders aren't dev-specific), but reads as a queue/ticketing
  view, undersells the "a team of agents is doing this for you" framing that
  makes the feature legible at a glance.
- **`/ai-team`** — captures the "background dev team" pitch well, but
  actively wrong once the system generalizes beyond code (§0) — an "AI team"
  handling a sales follow-up work order is a confusing frame.
- **`/operator` (current)** — vague enough to survive the domain
  generalization in §0 without renaming again, and already wired into
  `Sidebar.tsx`/`MobileNav.tsx`/`i18n.ts`. The cost of being slightly
  under-specific now is much lower than the cost of a second rename once
  real users/URLs/bookmarks exist.

Rename this once the product actually ships a second work-order domain
(e.g. the first non-code work order goes live) — at that point "Operator"
vs. "Work Orders" vs. something else should be decided against real usage,
not speculation.

## 9. Path to a Real Runner Prototype

1. **Manual round-trip — DONE (OP-Runner-001, §12).** Create a work order
   (with its ticket plan) via `POST /api/work-orders`, generate the runner
   prompt from the UI, run it by hand in Claude Code, and import the
   result with `scripts/import_work_order_result.py`. Full walkthrough:
   `docs/background-dev-team-runbook.md`.
2. **A thin "recorder" script — DONE (OP-Runner-001, §12).**
   `scripts/import_work_order_result.py` is that script. It's still invoked
   by a human after the runner session ends (not called by the runner
   itself mid-session), which is the honest boundary of "done" here — see
   §11 for what that does and doesn't cover.
3a. **A local, human-invoked runner harness — DONE (OP-Runner-002, §13).**
   `scripts/run_work_order.py` fetches a work order, runs safety
   preconditions, sets it `running`, writes the prompt to a local session
   folder, and can optionally invoke a user-supplied runner command and
   auto-import its result. A human still types the command that starts
   this — CommandPilot does not initiate it itself. Execution stays fully
   on Serkan's own machine (the Execution Plane); CommandPilot never
   executes a shell command (the Control Plane boundary from §13).
3b. **A triggered (not autonomous) runner — not yet built.** Something (a
   button in the UI, a scheduled check) that picks up a `queued` work order
   and starts a Claude Code/Codex session with the generated prompt
   *without a human running a command* — the harness in 3a is the
   execution mechanics this would reuse, but the *trigger* would move from
   "Serkan runs a script" to "CommandPilot (or something it calls) decides
   to." This is the actual first point where "background" becomes literal,
   still stopping hard at `needs_approval`/`blocked` and still requiring a
   human to move `review_ready → accepted`. It's also the point where the
   safety-rules enforcement in §5/§12 needs to go further than keyword
   matching on free-text scope fields: a real runner-side execution
   sandbox/allowlist that can't be bypassed by phrasing an action
   differently — §13's local harness deliberately doesn't attempt this yet
   either (it validates the *scope declaration*, not what a runner
   actually *does*).

Multi-agent parallelism, cross-repo work orders, and any real external
integration (CampsPilot, Signalübertragung, email, calendar, Stripe) are all
later than step 3b and each needs its own approval-scope design — not
sketched further here.

## 10. Explicitly Out of Scope (this pass)

- No real autonomous worker/executor — nothing in this repo calls an agent
  or executes a work order on its own; §9 step 3 is the first point that
  would change. The import script (§12) is invoked by a human after a
  runner session ends, not by the runner mid-session.
- No deployment integration of any kind.
- No production data reads or writes. The migrations have been written but
  **not run** against any live Supabase project — running them is a manual
  step for Serkan, deliberately not automated here.
- No email/Gmail integration.
- No secrets are read, displayed, or logged anywhere in this feature — the
  backend `.env` was not opened or read while building this.
- No Stripe / payment integration.
- No calendar integration.
- No multi-agent parallel execution — the agent-role list in a runner prompt
  is sequential by design.
- No "Create Work Order" UI form yet (§7) — the API and the recorder script
  (§12) both work today via `curl`/the runbook; a form is still just a UI
  convenience layered on top of the same endpoint.
- No enforcement layer that mechanically stops a blocked action from
  happening at the runner/execution level — §12's validator catches bad
  scopes at creation time, not bad actions mid-run. See the risk below.

## 11. Open Risks

- **Safety rules are still convention at the execution layer.** §12's
  `validate_approval_scope` stops a scope from *declaring* a blocked action
  as allowed, but nothing stops a misbehaving or misconfigured runner from
  *doing* something blocked anyway mid-session (e.g. calling
  `git push --force` despite the prompt saying not to) — the prompt's hard-
  stop instructions are strong wording, not a technical barrier. Real
  enforcement requires a runner-side execution sandbox/allowlist, which is
  step 3b in §9, not this pass. §13's local harness adds a second,
  independent keyword check before a run starts (defense in depth on the
  *declaration*), but still nothing at the *execution* level.
- **The blocked-keyword validator is a best-effort net, not a grammar.** It
  does substring matching on free-text `allowed_actions`/`requires_approval`
  entries (`backend/app/core/safety_rules.py`). Phrasing a blocked action
  without hitting a keyword (e.g. "ship it" instead of "deploy") would slip
  through. It catches the obvious cases Serkan would actually type, not an
  adversarial input — this system has no adversarial user, so that's a
  reasonable line today, not a long-term one.
- **No transactional guarantee on work order creation.** The
  create-then-compensate approach in §6 (delete the work order if the
  approval scope insert fails) is best-effort, matching existing repo
  precedent (`ensure_user_workspace`), but a crash between the two inserts
  (rather than a clean exception) could leave an orphaned, scope-less work
  order row. Low likelihood, not zero.
- **Migrations not yet run anywhere.** Everything in §6/§7/§12 is inert
  until `006_work_orders.sql` and `007_work_order_steps.sql` are applied to
  a real Supabase project — this was intentional (no production data
  changes), but it means none of this has been exercised against a live
  database, only against the Pydantic layer
  and the mock-fallback frontend path.

## 12. OP-Runner-001 — Making the Dev Team Operational

This pass turned the persisted control plane (OP-Backend-001) into
something Serkan can actually run a background dev-team session with today.
Full walkthrough: `docs/background-dev-team-runbook.md`. What was added:

**`work_order_steps` — the visible ticket plan** (new table,
`supabase/migrations/007_work_order_steps.sql`). A step is the plan-level
unit ("what is my team doing right now") and is deliberately a separate
table from `agent_runs` (the execution-level audit record) — see §2's
distinction, now extended by one more table. Same join-based ownership
pattern as every other `work_orders` child. `WorkOrderCreate` accepts an
optional `steps` list so a work order's plan can be defined at creation
time; two endpoints (`POST`/`PATCH .../steps/{step_id}`) let it evolve or
be updated afterward.

**Execution Plan UI** (`components/operator/ExecutionPlan.tsx`), rendered
prominently near the top of the work order detail page, above Approval
Scope — ahead of it in priority because "what is happening right now" is
the more urgent question than "what's the scope," per this run's explicit
brief. Shows ordered steps, a progress bar, the currently-`running` step
highlighted, and blocked steps with their reason inline.

**Lifecycle Controls** (`components/operator/LifecycleControls.tsx`) — one
button per valid status transition (`draft→approved→queued→running`, and
`review_ready→{accepted, rework_requested}`), calling the existing
`PATCH /api/work-orders/{id}` (no new endpoint needed — it was already
there from OP-Backend-001). Disabled with an explanatory note when viewing
mock-fallback data, since mutating seed data isn't a real action.

**Runner prompt upgraded** (`lib/generateRunnerPrompt.ts`) to walk the
runner through the ticket plan step by step (each step's real id embedded,
so the runner's output can reference it exactly), add an explicit "HARTER
STOPP bei Scope-Verletzung" section, and end by demanding the machine-
readable result JSON (`workOrderId`, `finalStatus`, `steps[]`,
`activityLogs[]`, `artifacts[]`, `reviewPackage`) that the import script
consumes. One correction from the mission spec: `reviewPackage.
needsHumanReview` is a boolean in the actual schema (matching the
already-built `ReviewPackage` model), not the array shown in the original
example — the import script coerces it defensively either way.

**Recorder/import bridge** (`scripts/import_work_order_result.py`) — a
zero-dependency (stdlib `urllib` only) Python script that reads the
runner's result JSON (file or stdin) and writes it back through the
existing API: one `PATCH` per step, one `POST` per activity log entry and
artifact, one `PUT` for the review package, one final `PATCH` for the work
order's overall status. Authenticates with a bearer token the user already
has (own Supabase session, via `--token`/`COMMANDPILOT_API_TOKEN`) — no new
auth mechanism, no secret reading. Per-item error handling: one bad step id
doesn't abort the rest of the import. `--dry-run` prints every call it
would make without making it.

**Safety scope, technically enforced (partially)**
(`backend/app/core/safety_rules.py` + a `model_validator` on
`ApprovalScopeCreate`) — a work order can no longer be created with a
repo-wide-blocked action (keyword-matched: "deploy", "secret", "force
push", ...) sitting in `allowed_actions` or `requires_approval` instead of
`blocked_actions`; the API rejects it with a 422. `ApprovalScopeResponse`
is deliberately *not* a subclass of `ApprovalScopeCreate` anymore (it was,
in OP-Backend-001) specifically so this validator only runs on the write
path — a read should never 500 because of a scope that already exists in
the DB. The UI also now warns explicitly when a work order has no approval
scope at all, or an approval scope with an empty `blocked_actions` list.
This is a real, if partial, answer to §11's "convention, not enforcement"
risk — see the updated risk entries above for exactly what it does and
doesn't cover.

## 13. OP-Runner-002 — Local Triggered Runner Harness

**The Control Plane / Execution Plane boundary, made explicit.**
CommandPilot (the backend + frontend built so far) is the **Control
Plane**: it holds work orders, approval scopes, ticket plans, activity
logs, review packages, status — the record of what should happen and what
did. It has never executed a shell command and still doesn't. The
**Execution Plane** is wherever a runner (Claude Code, Codex, later
possibly something else) actually does the work — until OP-Runner-002 that
was "Serkan's own hands, copying text between two windows." This pass adds
`scripts/run_work_order.py`, a **local runner harness**: still entirely on
Serkan's machine, still explicitly invoked by a human, but it now does the
mechanical parts (fetch, validate, mark running, write the prompt, import
the result) so the human's job shrinks to "run one command, then run
Claude Code, then run one more command."

**`scripts/run_work_order.py`** — stdlib-only Python (same zero-dependency
posture as `import_work_order_result.py`, which it imports and reuses
rather than duplicating). Three modes:
- `--mode prompt-file`: fetch the work order, run safety preconditions
  (below), set it `running` (+ its first step), write `prompt.md` +
  `result.schema.json` + `result.example.json` to
  `tmp/work-order-runs/<id>/` (gitignored — local, throwaway session
  files), log an `activity_log` entry.
- `--mode import-result`: thin wrapper around `import_work_order_result.
  import_result()` — no logic duplicated, just defaults the result path to
  the session folder.
- `--mode execute` (opt-in only, no default command ever): runs a
  user-supplied `--runner-command`, captures its output, best-effort scans
  it for a valid result JSON (a backward brace-matching scan looking for
  a `{...}` block with `workOrderId`+`finalStatus` keys) and auto-imports
  it if found — falls back to "save the output and do it yourself" if not,
  never guesses wrong silently.

**The prompt generator now has two implementations, on purpose.**
`build_runner_prompt()` in the Python script is a deliberate line-by-line
port of `frontend/lib/generateRunnerPrompt.ts`, not a shared library. This
is the same duplication tradeoff as the safety-rules lists (§5/§12): the
script needs to run standalone on a bare Python 3 install without the
frontend's Node toolchain on the path, so importing the real TS function
isn't practical. Two independently-maintained copies of the same template,
clearly cross-referenced in comments, was judged safer than a fragile
cross-language import — keep both in sync by hand when either changes.

**Safety preconditions — a technical gate before any run, not just at
scope-creation time.** `validate_preconditions()` blocks a run (no state
mutated yet, so aborting is free) unless: an approval scope exists with a
non-empty `blocked_actions` list; no blocked-looking keyword appears in
`allowed_actions`/`requires_approval` (the same keyword check as the
backend validator, run a second time here — independent defense in depth,
not a replacement for it); at least one ticket-plan step exists; and the
work order's status is `approved` or `queued`. `--force` overrides *only*
the status check — never the three safety-critical ones above it. A
separate, non-blocking `check_warnings()` flags an empty `allowed_paths`
when `allowed_actions` implies code changes.

**No new API endpoints.** Every capability `run_work_order.py` needs
already existed from OP-Backend-001/OP-Runner-001 (`GET`/`PATCH` on a work
order, `PATCH` on a step, `POST` activity-log). A `POST .../runner-events`
endpoint was considered and deliberately not built — a runner-started
event is just an activity log entry with `event_type="runner_started"`;
adding a parallel endpoint for the same concept would be surface area
without a new capability.

**Frontend: `LocalRunnerPanel`** on the work order detail page, above the
manual `RunnerPromptPanel` (which stays, as the documented fallback/
explainer for what's happening underneath) — shows the exact two commands
to copy, a reminder that execution is local, and a pointer to the session
folder for troubleshooting. It never runs anything itself, matching the
Control-Plane-only rule.

**What this deliberately is not.** Not a triggered runner (§9 step 3b) —
a human still types the command. Not live step-by-step streaming — the
harness sets one step `running` at the start and waits for the final
result JSON, exactly like the fully-manual path; genuinely live updates
need the runner itself to call back into CommandPilot mid-session, which
is a different (harder) integration than wrapping an opaque CLI call.

**RunnerAdapter contract v0.** The interface a runner needs to satisfy is
now stable enough to name: read a prompt (`prompt.md` / the UI's copy-paste
prompt — same content), do the work within its stated approval scope, emit
a result JSON matching `result.schema.json`. Anything that can consume a
prompt and produce that JSON is a valid adapter — Claude Code and Codex
today, manually. **OpenClaw is noted here as a candidate future
RunnerAdapter** (an execution backend that could plug into this same
contract) — explicitly not evaluated or integrated in this pass. This
informal "v0" is formalized into an actual Python interface in §14
immediately below.

## 14. OP-Runner-003 — Runner Adapter Contract

**Strategic principle, restated and now load-bearing in code, not just
prose:** CommandPilot orchestrates existing coding agents (Claude Code,
Codex, later possibly OpenClaw); it does not become one. §13's "contract
v0" was a paragraph describing a shape. This pass makes that shape a real
Python interface — `scripts/runner_adapters/` — and refactors
`run_work_order.py` to be a thin orchestrator over it instead of a
monolith with the prompt-building and result-collecting logic baked in
directly. Full interface, safety requirements, and the "never do this"
list: **`docs/runner-adapter-contract.md`** (dedicated doc, not duplicated
here).

**What moved where.** `build_runner_prompt()`, `RESULT_JSON_SCHEMA`,
`build_result_example()`, and the `AGENT_ROLES`/`SAFETY_*` constants moved
from `run_work_order.py` into `scripts/runner_adapters/base.py` — content
that's about representing a work order as text for *any* adapter to
consume, not specific to the harness's own CLI orchestration.
`BLOCKED_ACTION_KEYWORDS`/`find_blocked_keyword` moved there too, which
incidentally *reduced* duplication versus OP-Runner-002: previously
`run_work_order.py` held its own copy; now every adapter and the harness
import the one copy in `base.py` (still a deliberate, separate copy from
the frontend/backend versions — see §5/§13 — but no longer duplicated a
second time *within* `scripts/`).

**Four adapters, one implemented.** `manual_prompt` (the only one that
actually works — identical behavior to OP-Runner-002's hardcoded logic,
now behind the `RunnerAdapter` interface), `claude_code`/`codex`
(architectural placeholders: `info` declared with real
capabilities/`command_template` guesses, `prepare()` works, `execute()`/
`collect_result()` raise `NotImplementedError` with a pointer to the
contract doc), and `openclaw` (a named slot only — capabilities
unresearched, every method raises immediately). `--adapter` defaults to
`manual_prompt`, so the existing Fast Path from OP-Runner-002 is
unchanged for anyone not passing the flag.

**Safety, now checked twice, independently.** `validate_preconditions()`
(harness-level, unchanged from §13) and the new
`RunnerAdapter.check_scope_errors()` (adapter-level: does *this adapter's*
own declared capabilities/`command_template` reference a blocked action?)
both run before `prepare()` is called, and both must pass. This is
deliberate redundancy, not an accident — a future adapter with a
mis-declared capability is caught even if the work order's own scope is
perfectly fine, and vice versa.

**The generic `--runner-command` escape hatch stays, deliberately outside
the contract.** `--mode execute --runner-command "..."` (OP-Runner-002)
still works exactly as before, with any adapter — a human supplies the
literal command, so it needs no adapter-specific knowledge. `RunnerAdapter.
execute()` is a different, narrower thing: *adapter-native* invocation,
where the adapter itself knows how to start its own runtime via its own
`command_template`, without a human typing anything. Today every adapter's
`execute()` raises `NotImplementedError` — that's correct, not a bug; it
becomes meaningful the day `claude_code` or `codex` is actually
implemented.

**Still not done, on purpose (out of scope for this pass):** real
OpenClaw integration, any backend-triggered execution, and anything beyond
declaration-time scope checking — see `docs/runner-adapter-contract.md`'s
closing section for exactly what a `check_scope_errors()` pass does and
does not guarantee.

## 15. OP-ClaudeAdapter-001 — Runner UX Hardening + Claude Code Adapter v0

Follows the first real end-to-end UI → Local Runner → Claude Code →
`result.json` → import → Review Package lifecycle test, which surfaced
concrete friction (documented and fixed here rather than left as folklore
in a chat transcript).

**`AdapterInfo.supports_auto_execute` became a tri-state**
(`"yes" | "no" | "semi_auto"`, `scripts/runner_adapters/base.py`), not the
plain bool it was in §14. A bool can't distinguish "fully unattended" from
"really does execute, but depends on something outside the adapter's
control" — and that distinction turned out to matter the moment a real
adapter (`claude_code`) had a genuine gap (workspace trust, below) instead
of just being an unimplemented placeholder. `manual_prompt`/`openclaw` are
`"no"`; `codex` (still unverified) and `claude_code` are `"semi_auto"`;
`"yes"` is reserved for an adapter with no known unattended gap — none
qualifies yet.

**`claude_code` went from placeholder to real, verified implementation**
(`scripts/runner_adapters/claude_code.py`). Verified against the installed
`claude` CLI (v2.1.199) via `claude --help` plus one minimal,
cost-capped live call (`--max-budget-usd 0.02`) — not guessed:
- `-p/--print --output-format json` is genuinely non-interactive; the
  prompt is piped via stdin (no positional argument needed); the wrapper's
  `result` field holds the model's final text, where the embedded
  work-order result JSON lives.
- `--max-budget-usd` is a real, CLI-enforced spend cap, independent of and
  in addition to the work order's own `approval_scope.max_cost_usd` — the
  adapter passes the scope's value through rather than inventing its own.
- **The one hard, verified gap:** an untrusted workspace makes Claude Code
  silently ignore this project's `permissions.allow` entries, even in
  `--print` mode — accepting the trust dialog interactively, once, per
  machine/directory, is a precondition this adapter cannot satisfy for
  itself. `execute()` detects the resulting message and raises a clear,
  actionable error rather than pretending the run succeeded. This is
  exactly why `supports_auto_execute="semi_auto"` and not `"yes"`.
- **Deliberately never passes `--dangerously-skip-permissions` /
  `--permission-mode bypassPermissions`.** That flag would let Claude Code
  run without any permission checking at all — the one thing this entire
  system's ApprovalScope model exists to provide. An adapter that reached
  for it to paper over the trust requirement would be solving its own
  inconvenience by deleting the safety property CommandPilot is built
  around. Not done, not considered acceptable later either without a much
  larger design conversation.
- `_map_allowed_tools()` best-effort maps the Background Dev Team default
  action slugs (`code_edit_within_scope`, `test_lint_typecheck`, ...) onto
  Claude Code's `--allowedTools` vocabulary; anything unrecognized falls
  back to Claude Code's own default permission handling rather than being
  silently granted. `_ALWAYS_DISALLOWED_TOOLS` hard-denies destructive git
  operations and outbound web tools regardless of scope — the
  execution-time counterpart to `check_scope_errors()`'s declaration-time
  check.
- Subprocess invocation uses an explicit argument list, never `shell=True`
  — prompt text (arbitrary, LLM-adjacent) is piped via `input=`, never
  interpolated into a command string. The child process's environment is
  the parent's minus `COMMANDPILOT_API_TOKEN` explicitly — the runner has
  no legitimate use for CommandPilot's own API credential and shouldn't be
  able to log it even by accident.

**Result JSON validation, centralized.** `parse_and_validate_result()`
(`scripts/runner_adapters/base.py`) checks JSON well-formedness (with
line/column on failure), that all six required top-level keys are present
(named individually if not), and that `finalStatus` is one of the three
valid values — before any API call is attempted. Both
`manual_prompt.collect_result()` and `claude_code.collect_result()` call
it, and `scripts/import_work_order_result.py`'s standalone `main()` now
does too (a one-directional dependency — `import_work_order_result.py` →
`runner_adapters.base`; nothing in `runner_adapters/` imports back) — so
the three ways a result JSON can enter this system all fail the same way,
with the same clarity, instead of each hand-rolling its own partial check.

**Execute-time path safety, now a hard gate, not just a warning.**
`run_work_order.py` had one check (`check_warnings()`, non-blocking) for
"code changes allowed but no `allowed_paths`" — correct for `--mode
prompt-file`, where a human reads the prompt before anything happens, but
not strict enough for `--mode execute`, where nothing stops an unattended
run from writing anywhere in the repo. `check_execute_path_safety()` is
the new, blocking sibling: it refuses to start an auto-execution (generic
`--runner-command` or an adapter's own `execute()`) under that condition
unless `--force` is passed explicitly. The Create Work Order form
(OP-Create-001) now also pre-fills safe default `allowed_paths` /
`blocked_paths` for `development` work orders specifically so this gate is
rarely the thing a user actually hits.

**PowerShell correctness, throughout.** The real test run surfaced
`$COMMANDPILOT_API_TOKEN` (silently empty — a different variable than
`$env:COMMANDPILOT_API_TOKEN`) and bare `<WORK_ORDER_ID>`-style angle-
bracket placeholders (parsed by PowerShell as input redirection, a hard
parse error) as genuine footguns, not hypothetical ones.
`LocalRunnerPanel.tsx` was rewritten around a 5-step flow (set token →
approve+queue in the UI, explicitly not clicking Mark Running → start the
runner → run Claude Code manually or via the `claude_code` adapter →
import) with every copyable command using correct `$env:` syntax and real
substituted values (never a bare placeholder). The runbook was aligned the
same way throughout, with a non-bracketed `YOUR_WORK_ORDER_ID` placeholder
convention for the few contexts where a literal command can't have a real
value substituted in the doc itself.

**Windows console encoding fix (OP-Runner-002/003 era, verified here)** —
both scripts reconfigure stdout/stderr to UTF-8 at import time; confirmed
still correct and side-effect-free (no change needed, called out in the
runbook's Known Issues so it doesn't read as folklore).

**Out of scope, per this work order's explicit instructions:** no backend
shell execution, no OpenClaw integration, no deployment, no production
data access — unchanged from every prior pass.

## 16. OP-ClaudeBudgetGate-001 — Usage/Budget Safety Gate

Follows directly from real usage during §15's own validation: a real
`claude_code` `execute()` run cost $1.40 with no cap enforced anywhere,
because the work order's own `approval_scope.max_cost_usd` simply wasn't
set. That gap — an adapter capable of spending real money, with nothing
external forcing an operator to acknowledge a limit before it runs — is
exactly what this pass closes.

**`AdapterInfo` gained `consumes_paid_credits: bool = False`**
(`scripts/runner_adapters/base.py`) — an adapter declares honestly whether
its `execute()` calls a paid LLM API on its own initiative.
`manual_prompt`/`openclaw` are `False`/`True` respectively for the reasons
already covered in §14/§15's `supports_auto_execute` distinction;
`claude_code` and `codex` are `True` — the latter conservatively, since a
real Codex CLI would presumably also cost money once implemented.

**`RunnerAdapter.execute()` gained a `max_budget_usd: float | None = None`
parameter**, threaded through from `run_work_order.py`'s new gate to
whichever adapter is running. `claude_code.py`'s `_build_cli_args()` now
takes this as `budget_override` and prefers it over the work order's own
`approval_scope.max_cost_usd` — the harness-level, invocation-time value
always wins, since it's the more immediate, explicit signal an operator
just typed or set.

**The gate itself, in `run_work_order.py`'s `cmd_execute()`:** before
`cmd_prompt_file()` is ever called (i.e. before anything is mutated —
status, steps, activity log), if the chosen adapter has
`consumes_paid_credits=True` and no `--runner-command` was given (see
below for why that path is exempt), the harness requires either
`--max-budget-usd <float>` or a parseable `COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`
env var. Missing both aborts with the exact required message: *"Claude
Code execution would consume usage credits. Set --max-budget-usd or use
--mode prompt-file."* No fallback default is ever invented here — that
would defeat the entire point. Verified via a mocked dry-run suite that
checks the stronger property than "exits non-zero": literally zero
mutating API calls happen before the gate fires (only the pre-existing,
read-only `GET` used for the path-safety check).

**Why the generic `--runner-command` escape hatch stays exempt:** that
path already requires a human to type the exact command themselves — a
fundamentally different consent signal than the adapter-native path,
where the harness itself decides to invoke `claude` on the operator's
behalf. Gating it too would mean string-sniffing an arbitrary
user-supplied command for "does this look like it calls a paid API,"
which is fragile and inconsistent with that path's whole "adapter-agnostic,
human already knows what they're running" design (OP-Runner-002).

**UI (`LocalRunnerPanel.tsx`):** each command block now carries an
explicit "no Claude credits used" / "uses Claude credits" badge, and the
`claude_code` execute command shown is no longer copy-paste-broken by the
new gate — it now includes `--max-budget-usd 0.20` as an edit-me starting
point, plus an inline hint explaining the requirement and the two ways to
satisfy it. `0.20` is UI copy, not a script default — the script itself
never assumes it.

**Docs:** `docs/background-dev-team-runbook.md` gained a "Working without
spending Claude credits" section (why `prompt-file`/`manual_prompt` cost
nothing, how to start `claude_code` with a small budget either way, why
manual is the safer default) plus a Known Issues entry and a
Troubleshooting row for the new refusal message.
`docs/runner-adapter-contract.md`'s `AdapterInfo` listing, `execute()`
description, and adapter status table were all updated to reflect
`consumes_paid_credits` and the new `max_budget_usd` parameter.

**Out of scope, per this work order's explicit instructions:**
`--dangerously-skip-permissions` remains never used; no auto-execute
without explicit cost approval; no silent default budget anywhere in the
codebase.
