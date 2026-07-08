# Background Operator / Second Brain — Technical Spike

Status: **spike / MVP skeleton**. No backend, database, or production behavior
changed. This document plus a mock-data-only frontend page are the entire
output of this pass.

## 1. Current Architecture Summary

**Stack:** Next.js 14 App Router + TypeScript frontend, FastAPI + Pydantic
backend, Supabase (Postgres + Auth) for persistence and identity.

**Backend (`backend/app`)**
- `routers/` — one file per resource (`checkins`, `plans`, `reviews`, `rules`,
  `projects`, `auth`, `health`). Thin: validate → call a service → return a
  Pydantic response model.
- `models/` — Pydantic request/response models per resource. Status/priority
  fields use `Literal[...]` types (e.g. `ProjectStatusLiteral` in
  `models/project.py`), mirrored by a SQL `check (...)` constraint in
  `supabase/schema.sql` and a TS union type in `frontend/types/index.ts`. This
  three-way mirroring (Pydantic Literal / SQL check / TS union) is the
  established pattern for any enum-like field in this codebase.
- `services/` — business logic and DB access (`ai_service.py`,
  `plan_service.py`, `project_service.py`, `usage_service.py`, ...).
  `ai_service.py` calls OpenAI in JSON mode; prompt construction is isolated in
  `backend/app/prompts/`.
- `auth.py` — `get_current_user` validates the Supabase bearer token and
  returns a `CurrentUser(id, email, workspace_id)`. `ensure_user_workspace`
  guarantees a profile/workspace/workspace_members row exists (idempotent,
  called at the top of write-heavy endpoints like `/plans/generate`).
  `require_owned_record(table, id, user)` is the standard ownership check —
  every fetch-by-id endpoint uses it and returns 404 (not 403) on mismatch.
- `usage_service.py` enforces a daily AI spend cap (`check_daily_cap`,
  `log_ai_usage`) before/after any OpenAI call — the only existing example of
  a "guardrail before a costly/external action" pattern in the repo.

**Frontend (`frontend/`)**
- `app/<feature>/page.tsx` — route shell: `AppShell` (sidebar + mobile nav +
  `ProtectedRoute`) + `Header` + a feature `Manager` component.
- `components/<feature>/<Feature>Manager.tsx` — the actual page logic: fetch
  via `lib/api.ts`, local state, forms, list rendering. `ProjectsManager.tsx`
  is the closest analog to what a work-orders manager needs (status badges,
  priority accent borders, inline edit, empty/error/loading states).
  `AppShell`.
- `components/ui/` — `Card`/`CardHeader`/`CardContent`, `Button`, `Input`/
  `Textarea`/`Select`, `Badge`, `Spinner`/`EmptyState`. All feature UIs compose
  from these; no new low-level primitives are introduced by this spike.
- `lib/api.ts` — one `request<T>()` wrapper that attaches the Supabase access
  token; `api.<resource>.<verb>()` namespaces per resource.
- `lib/i18n.ts` — flat key → `{en, de}` dictionary, `useT()` hook reads
  `AuthContext.language`. Missing keys fall back to `en`, then the raw key
  (non-fatal), but the convention is to add both languages together.
- `lib/auth.tsx` — `AuthProvider` + `useAuth()` + `ProtectedRoute`. Bootstraps
  the backend session on `SIGNED_IN`, exposes `language`, redirects
  unauthenticated users to `/login`.
- `types/index.ts` — one flat file, hand-written interfaces mirroring backend
  Pydantic models, grouped by feature with a comment banner per section.

**Existing daily-loop flows** (the current "operator" is entirely
foreground/synchronous):
1. Morning check-in (`/morning`, `checkins` router/service) — energy, sleep,
   fixed events, raw brain-dump text.
2. AI plan generation (`POST /api/plans/generate`) — pulls checkin + active
   rules + recent review + active projects as context, calls OpenAI
   synchronously in the request/response cycle, persists a `daily_plans` row.
3. Evening review (`/review`, `reviews` router/service) — completed/missed
   items, reflection text; feeds back into the next morning's plan as
   `recent_review` context.
4. Projects (`/projects`) — a lightweight backlog (`active/waiting/paused/
   backlog/done/archived`) that also feeds plan generation as context.

**Database** — `supabase/schema.sql` is the source of truth, applied by hand
in the Supabase SQL editor; numbered files in `supabase/migrations/` are
incremental, idempotent follow-ups (see README §1b). Every user-owned table
has a `user_id` FK, most also carry `workspace_id`, and RLS policies key off
`auth.uid() = user_id`. The backend additionally re-checks ownership with
`require_owned_record` because it connects with the service-role key (RLS is
bypassed server-side, so the app-layer check is load-bearing, not redundant).

**What CommandPilot does NOT currently have** (confirmed by reading the repo,
not assumed): any notion of a long-running/background job, a task queue, a
webhook/integration layer, external tool access (GitHub, ticket trackers,
file import), or any concept of "AI acts without a human in the loop." Every
AI call today happens inside a single HTTP request initiated by the user.

## 2. Where a Background Operator Fits

The operator is a **new, additive surface**, not a modification of the daily
loop. It should slot in the same way `projects` did: a new router/service/
model on the backend, a new `app/<feature>` + `components/<feature>` pair on
the frontend, a new table with the same `user_id`/`workspace_id`/RLS shape.

Two integration points into the *existing* flows, both optional and additive:
- Morning plan generation could surface "you have N work orders needing
  review/approval" as context, the same way `active_projects` is fetched
  today in `plans.py` (non-fatal, best-effort, matching the existing
  try/except-and-continue pattern used for `recent_review` and
  `active_projects`).
- Evening review could be a *source* for a work order ("turn tonight's
  review into tomorrow's plan") rather than a consumer.

Nothing about the operator should live inside `plans.py`, `ai_service.py`, or
the daily-loop tables — it needs its own lifecycle (a work order can outlive
many days), its own status machine, and its own approval gate, none of which
the current one-shot "generate and save" pattern models.

## 3. Proposed MVP Data Model: Work Orders

Mirroring the existing Pydantic-Literal / SQL-check / TS-union pattern:

```python
# backend/app/models/work_order.py (proposed, not implemented this pass)
WorkOrderStatusLiteral = Literal[
    "planned", "needs_context", "queued", "working",
    "needs_review", "approved", "done", "failed",
]

class MissingContextItem(BaseModel):
    label: str            # e.g. "ticket descriptions"
    description: str | None = None
    required: bool = True # False = "nice to have", order can still proceed

class ReviewPackage(BaseModel):
    summary: str
    assumptions: list[str] = []
    missing_context: list[str] = []
    proposed_next_steps: list[str] = []
    actions_requiring_approval: list[str] = []

class WorkOrder(BaseModel):
    id: str
    user_id: str
    workspace_id: str | None
    title: str
    status: WorkOrderStatusLiteral
    source: str                       # "manual" | "morning_checkin" | "evening_review" | ...
    missing_context: list[MissingContextItem] = []
    review_package: ReviewPackage | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
```

```sql
-- supabase/migrations (proposed, not implemented this pass)
create table if not exists work_orders (
  id             uuid primary key default uuid_generate_v4(),
  workspace_id   uuid references workspaces(id) on delete cascade,
  user_id        uuid not null references profiles(id),
  title          text not null,
  status         text not null default 'planned'
                   check (status in ('planned','needs_context','queued','working',
                                      'needs_review','approved','done','failed')),
  source         text not null default 'manual',
  missing_context jsonb not null default '[]',
  review_package  jsonb,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now(),
  started_at     timestamptz,
  completed_at   timestamptz
);
-- RLS: same "Users own work_orders" using (auth.uid() = user_id) policy as projects.
```

`missing_context` and `review_package` as `jsonb` (mirroring how `daily_plans`
already stores `top_priorities`/`time_blocks` as structured JSON) avoids a
join-heavy schema for an MVP and keeps the shape flexible while the concept is
still being validated.

## 4. Status Lifecycle

```
planned ──────► needs_context ──────► queued ──────► working
   │                  ▲                                 │
   │                  └─────────(context added)─────────┘
   │                                                     │
   │                                                     ▼
   │                                            needs_review ──► approved ──► done
   │                                                     │
   └───────────────────────────────────────────────────►│
                                                          ▼
                                                        failed
```

- **planned** — order exists, not yet checked for required context.
- **needs_context** — blocked; at least one `required: true` item in
  `missing_context` is unfilled. This is a terminal-looking state that is
  actually just "waiting on the user" — see §5.
- **queued** — all required context present; eligible to be picked up by
  background execution.
- **working** — actively being processed (background-safe steps only, §6).
- **needs_review** — background work produced a `ReviewPackage`; waiting on
  human judgment before anything external happens.
- **approved** — user has signed off on the review package; queued for the
  approval-gated action (§7), not yet executed.
- **done** — terminal success.
- **failed** — terminal failure; should carry an error reason, and a failed
  order should be re-openable back to `needs_context` or `queued`, not just
  discarded.

## 5. Representing Missing Context

Missing context is a **first-class, structured list**, never a free-text
excuse buried in a summary. Each `MissingContextItem` has a `label` (what's
missing, e.g. "ticket descriptions"), an optional `description` (why it's
needed / what it unblocks), and a `required` flag. A work order with any
unfilled `required` item is *by construction* in `needs_context` — the status
is a derived/enforced consequence of the list, not an independent field the
operator can lie about.

This is also the mechanism by which the operator stays honest about not
having CampsPilot/Signalübertragung/other external context: instead of
fabricating ticket contents or lecture notes, it declares
`missing_context: [{label: "ticket descriptions", required: true}, ...]` and
sits in `needs_context` until the user supplies them (pastes text, links a
doc, grants repo access — the import mechanism itself is out of scope for
this MVP and just a future "add context" action on the order).

## 6. What Can Run Safely in the Background

Only steps that are **read-only, reversible, and internal to CommandPilot's
own data** (or explicitly-provided user text) qualify:
- Checking whether required `missing_context` items have been filled and
  flipping `needs_context` → `queued`.
- Drafting a `ReviewPackage` (summary, assumptions, proposed next steps) from
  context already present on the order — this is generation, not action.
- Re-reading the user's own CommandPilot data (checkins, reviews, rules,
  projects) the same way `plans.py` already does for context assembly.

Nothing that calls an external API, writes to another system, sends a
message, or spends money beyond a bounded AI drafting call belongs here
without becoming an approval-gated action first (§7). This mirrors the
existing `usage_service.check_daily_cap` guardrail: background work should be
cheap, capped, and non-destructive by default.

## 7. What Requires Explicit User Approval

Anything that is **external, hard to reverse, or costs real money/access**
must stop at `needs_review` and wait for an explicit approval action before
proceeding, regardless of how confident the draft is:
- Any call to an external system (ticket tracker, repo, calendar, email,
  Slack, etc.) — none of which CommandPilot currently has credentials for.
- Any write that leaves CommandPilot's own database.
- Committing to assumptions the operator made about missing context (e.g. "I
  assumed CS-302 means X" must be shown and confirmed, not silently acted on).
- Anything with a real-world cost beyond a bounded, capped AI draft call.

The `approved` status exists specifically so "user reviewed and said yes" is
recorded as a distinct, auditable event from "background process decided to
proceed" — the two must never be the same action.

## 8. Review Package

The `ReviewPackage` is what the user sees before anything crosses the
approval gate. It always shows, in this order:
1. **Task summary** — one or two sentences, what the order is trying to do.
2. **Assumptions** — anything the operator inferred rather than was told.
3. **Missing context** — explicitly repeated here even though it's also on
   the order, so review is self-contained.
4. **Proposed next steps** — the concrete plan, in plain language.
5. **Actions requiring approval** — the specific external/irreversible steps
   that will fire *only* after the user clicks approve.

If a work order has no `missing_context` and its action is fully internal
(e.g. "turn evening review into tomorrow's plan draft" using only the user's
own text), the review package can still be shown for transparency, but the
gate is lighter — this is why that example is modeled as `queued` /
`needs_review` rather than `needs_context` in the mock data.

## 9. Non-Goals of This Spike

- No backend router/service/model was added — the model above is a proposal,
  written but not implemented, to keep this pass reviewable and DB-free.
- No database migration was written or run.
- No real execution engine, queue, or scheduler.
- No integration with CampsPilot, Signalübertragung, or any external system —
  CommandPilot has no access to those today, and the mock work orders exist
  specifically to demonstrate *detecting and declaring that gap*, not to
  simulate having the data.
