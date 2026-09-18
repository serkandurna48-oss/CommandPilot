# Background Dev Team — First Real Run: QA / Validation Checklist

Purpose: validate the *whole* lifecycle once, for real, before deciding
whether to start OP-Runner-002 (triggered runner + live step updates +
stronger runner-safety). This is a validation pass, not a build task — if
something here fails, the fix is the next work order, not a bigger
architecture change made in a hurry.

Companion docs: `background-dev-team-runbook.md` (the how-to for each step),
`background-dev-team-system-design.md` (the why).

---

## 1. Migrations — what must be applied

> **Verified live 2026-09-18** (Operator Control Plane v1 stabilization
> pass) against the configured Supabase project: `transition_work_order()`
> present in the live PostgREST schema; `agent_runs.attempt_number` /
> `retry_reason` present; `activity_logs.dedup_key` / `artifacts.dedup_key`
> present. Behavior, not just schema, was exercised end-to-end via a
> throwaway work order (created, transitioned legally and illegally,
> review_ready-without-package rejected with the exact guard message,
> duplicate-`dedup_key` upsert confirmed to overwrite rather than
> duplicate) and fully deleted afterward — see git history for the
> verification script. All 9 checks passed.

Run in the Supabase SQL editor, in order, if not already applied:

- [x] `supabase/migrations/006_work_orders.sql`
- [x] `supabase/migrations/007_work_order_steps.sql`
- [x] `supabase/migrations/008_work_orders_team_type.sql`
- [x] `supabase/migrations/009_work_orders_target_repo.sql`
- [x] `supabase/migrations/010_transition_work_order_function.sql` (adds `transition_work_order()` — the authoritative state machine, see §7 below) — verified live 2026-09-18
- [x] `supabase/migrations/011_agent_run_attempts.sql` (adds `agent_runs.attempt_number`/`retry_reason`) — verified live 2026-09-18
- [x] `supabase/migrations/012_result_import_dedup_keys.sql` (adds `activity_logs.dedup_key`/`artifacts.dedup_key` + unique indexes) — verified live 2026-09-18, including that the unique index is actually enforced (not just the column present)

**Verify, don't assume.** Run this in the SQL editor after:

```sql
select table_name from information_schema.tables
where table_schema = 'public'
  and table_name in ('work_orders','approval_scopes','agent_runs','activity_logs','artifacts','review_packages','work_order_steps');
```

Expect exactly 7 rows back. Fewer than 7 → a migration didn't apply; do not
proceed until it does (everything below assumes all 7 tables exist).

Additionally, for 010–012 specifically (a table existing doesn't prove the
function/columns from a later migration were also applied):

```sql
select routine_name from information_schema.routines where routine_name = 'transition_work_order';
select column_name from information_schema.columns where table_name = 'agent_runs' and column_name in ('attempt_number','retry_reason');
select column_name from information_schema.columns where table_name in ('activity_logs','artifacts') and column_name = 'dedup_key';
```

Expect 1 row, 2 rows, 2 rows respectively.

---

## 2. API smoke test — proves Work Orders + Steps actually work

Run this sequence with `curl` (see runbook §1 for how to get
`$COMMANDPILOT_API_TOKEN`). Each step lists the exact thing to check — not
just "no error," but the specific field.

**2.1 Create** — `POST /api/work-orders` with 2-3 steps and a clean
approval scope (see runbook §2 for the full payload).
- [ ] Response is `200`, has a real `id`, and `approval_scope_id` is **not
  null** (proves the two-insert creation path in `work_order_service.
  create_work_order` completed both inserts).

**2.2 Negative test — safety validator.** Repeat 2.1 but put `"deploy to
staging"` inside `allowed_actions`.
- [ ] Response is `422`, message mentions the matched keyword. If this
  instead returns `200`, the blocked-action validator
  (`backend/app/core/safety_rules.py`) is not wired up — stop, this is a
  regression, not a "proceed anyway" situation.

**2.3 List** — `GET /api/work-orders/me`.
- [ ] The work order from 2.1 appears, with its `approval_scope_id` set.

**2.4 Detail (the one the UI actually calls)** — `GET /api/work-orders/{id}`.
- [ ] `approval_scope` object present and matches what you sent.
- [ ] `steps` array length matches how many steps you sent, in the right
  `order_index` order.
- [ ] `agent_runs`, `activity_log`, `artifacts` are empty arrays;
  `review_package` is `null` (nothing has happened yet — if any of these
  are non-empty on a brand-new work order, something is bleeding across
  work orders — check the `work_order_id` scoping in
  `work_order_service.get_work_order_children`).

**2.5 Step update** — `PATCH /api/work-orders/{id}/steps/{step_id}` with
`{"status": "running"}`, then again with `{"status": "completed",
"output_summary": "test"}`.
- [ ] First call: response has `started_at` set.
- [ ] Second call: response has `completed_at` set, `started_at` **unchanged**
  from the first call (proves timestamps aren't clobbered on every update).

**2.6 Work order status transition** — `PATCH /api/work-orders/{id}` through
`approved → queued → running`. As of CP-OP01, this now routes through the
`transition_work_order()` Postgres function (see §7 below) rather than an
unvalidated direct write — a nonsensical jump like `draft → accepted`
should now be rejected with `400`, not silently accepted.
- [ ] `started_at` appears once, on the first transition into `running`
  (or any status the function treats as "started"), and does not change on
  subsequent PATCHes.
- [ ] Each of the three PATCHes above produced exactly one new
  `activity_logs` row with `event_type: "status_transition"` (check via
  `GET /api/work-orders/{id}` — the `activity_log` array).
- [ ] `PATCH` with `{"status": "accepted"}` directly from `draft` (skipping
  every intermediate status) returns `400`, not `200`.

If 2.1–2.6 all pass: the persistence layer is sound. If any fails, fix that
specific endpoint/table before touching anything UI-side — a UI bug on top
of a broken API is much harder to diagnose than the API test alone.

---

## 3. Pick a minimal *real* first work order

Criteria for the first one — optimize for **fast, unambiguous
verification**, not for impressiveness:

- Small enough to finish in 15–20 minutes.
- Acceptance criteria a human can check by reading a diff, not by running
  the product.
- Touches `docs/` or `frontend/` only — keep `backend/` and `supabase/` out
  of the very first run, so a mistake has the smallest possible blast
  radius while you're still validating the *process*, not the *code*.
- Produces a real, visible diff you already know the correct answer to
  (so you can tell immediately if the result is right, without having to
  think hard about it).

**Recommended candidate:** *"Add a 'Known Issues' section to
`docs/background-dev-team-runbook.md` documenting that API tokens expire
and need refreshing (troubleshooting table already hints at this — make it
a proper section)."*

Why this one specifically: it's genuinely useful (not throwaway), it's
docs-only (zero risk to running code), the acceptance criteria are trivial
to eyeball ("does the new section exist, does it say the right thing"),
and you already know exactly what correct output looks like — so you're
validating the *lifecycle*, not evaluating whether the content is good.

Alternative if you'd rather touch code: *"Add a `data-testid` attribute to
the Execution Plan progress bar"* — one-line, frontend-only, `tsc --noEmit`
is a real, meaningful QA step for it (unlike a pure docs change, where
"tests run" is honestly just "read the file").

Approval scope for either: `allowed_actions: ["Repo lesen", "Datei
ändern innerhalb docs/"]` (or `frontend/components/operator/`),
`requires_approval: ["Push / PR erstellen"]`, `blocked_actions:` the full
standard list from the runbook. `max_runtime_minutes: 20`.

---

## 4. What the Result JSON must look like

Minimal valid shape for either candidate above (adjust step ids to the real
ones from your `POST` response):

```json
{
  "workOrderId": "<real id from step 3>",
  "finalStatus": "review_ready",
  "steps": [
    { "id": "<real step id>", "status": "completed", "outputSummary": "Added Known Issues section.", "blockedReason": null }
  ],
  "activityLogs": [
    { "level": "info", "eventType": "run_completed", "message": "Docs updated." }
  ],
  "artifacts": [
    { "type": "diff", "title": "runbook.md diff", "content": "+## Known Issues\n+..." }
  ],
  "reviewPackage": {
    "summary": "Added a Known Issues section documenting token expiry.",
    "filesChanged": ["docs/background-dev-team-runbook.md"],
    "testsRun": [],
    "risks": [],
    "openQuestions": [],
    "needsHumanReview": true,
    "recommendedNextStep": "Review and merge.",
    "verdict": "ready_for_review"
  }
}
```

Checklist for the JSON specifically, before you import it:
- [ ] `workOrderId` matches the real id exactly (copy-paste, don't retype).
- [ ] Every step `id` matches a real step id from `GET /{id}` — an invented
  id is the #1 way this goes wrong (see §6).
- [ ] `needsHumanReview` is `true`/`false`, **not** an array — the runner
  prompt's schema is explicit about this (a boolean), but it's worth
  double-checking the actual output; the import script coerces it
  defensively but a wrong type here is a signal the runner didn't read the
  schema carefully.
- [ ] `verdict` is one of the 4 literal values, spelled exactly.
- [ ] `finalStatus` is one of `review_ready | blocked | failed` — not
  `"done"` or `"accepted"` (those are human-only transitions via the
  Lifecycle Controls, never something a runner sets itself).

---

## 5. UI checkpoints after import

Run `python scripts/import_work_order_result.py result.json --token
"$COMMANDPILOT_API_TOKEN"`, then check, in order:

- [ ] **`/operator` list page** — the work order's status badge shows
  `Review Ready`; no console errors.
- [ ] **Status flow strip** on the detail page — `review_ready` is
  highlighted, nothing else.
- [ ] **Execution Plan** — the step you completed shows `Completed`,
  100% progress (if it was the only step), and its `outputSummary` text.
- [ ] **Approval Scope** — no "no scope" / "no blocked actions" warning
  banners (if you see one, your scope from step 3 was incomplete).
- [ ] **Activity Log** — your `activityLogs` entries appear, in
  chronological order, with the right level badge.
- [ ] **Artifacts** — the diff/summary content renders (check for broken
  whitespace/escaping — a common failure if the runner's JSON had literal
  unescaped newlines instead of `\n`).
- [ ] **Review Package** — verdict badge shows `Ready for Review`,
  `Needs human review` badge present, summary/files-changed/etc. all show
  the real content, not placeholders.
- [ ] **Lifecycle Controls** — **Accept** and **Request Rework** buttons
  are present and enabled (not greyed out — if they are, `isLive` is
  `false`, meaning the detail page fell back to mock data, meaning the
  live `GET /{id}` call failed — check the browser console/network tab).
- [ ] Click **Accept** → status flips to `accepted`, Lifecycle Controls
  section disappears (no further transitions defined from `accepted`).

If every box above is checked: the full lifecycle works end-to-end against
a real backend, with a real (if tiny) task. That's the actual milestone —
not the size of the task, the fact that every stage of the pipe is proven.

---

## 6. Red flags — signals that OP-Runner-002 is not ready yet

These are specifically about *readiness for a triggered/unsupervised
runner*, not about this validation pass itself. A human is watching this
first run; OP-Runner-002 means nobody is. Anything below means the gap
between "worked when supervised" and "safe when triggered automatically"
is still open.

| Symptom | What it means |
| --- | --- |
| Runner's result JSON references a step `id` that isn't one of the real ids from the prompt | The runner invented/guessed an id instead of copying it exactly. If an LLM won't reliably echo a literal id back, it can't be trusted to self-report against a fixed plan without supervision — the contract needs to be more machine-checkable (e.g. schema validation *before* import, not just the import script's best-effort matching) before any unsupervised run. |
| Runner proceeds past a "braucht Approval" or "blockiert" action despite the prompt's explicit hard-stop instructions | **The single most important red flag.** Prompt wording is not enforcement (system design doc §11). If this happens even once under supervision, do not build a triggered runner until there's an actual execution-layer sandbox/allowlist — a triggered runner hits this same failure with nobody there to notice. |
| `finalStatus: "review_ready"` but the Review Package's `risks`/`openQuestions` are empty despite an obvious deviation from acceptance criteria | The verdict is optimistic rather than honest. An autonomous system that always reports "ready" regardless of actual quality is worse than no automation — it erodes the one signal (the verdict) a human is meant to rely on without re-checking everything. |
| A step you expected in the result JSON is silently missing (not marked `failed`/`blocked`, just absent) | The runner skipped a planned step without saying so. Under supervision you'll notice a step still `pending` — under a triggered runner, "silently incomplete" and "actually done" look identical unless something enforces that every planned step must appear in the result. |
| Import script reports `404` on a step/agent-run update | Either the runner invented an id (see row 1), or the work order id in the JSON doesn't match — either way, a broken link between plan and result that must be air-tight before removing the human from the loop. |
| An obviously-blocked action gets past the `ApprovalScopeCreate` keyword validator by rephrasing (e.g. "ship it" instead of "deploy") | Known, documented limitation (system design doc §11) — not a new problem, but a live reminder that scope *creation* safety and runner *execution* safety are two different, both-still-partial layers. |
| Token expires mid-import, some calls succeed and some 401 | Operational rough edge, not a blocker — as of CP-OP03, every import-script call is genuinely safe to re-run: steps/review-package were already idempotent (PATCH/PUT), and activity-logs/artifacts now upsert on a stable `dedup_key` too (previously a plain `POST`, which *would* have duplicated on re-import — see §7). Re-running the same `result.json` after a token refresh is now a real no-op for already-landed items, not just "probably fine." Still confirms the recorder bridge needs a human refreshing a token by hand — another manual step a triggered runner can't yet do for itself. |

**Decision rule:** if §5's checklist is fully green *and* none of §6's red
flags occurred during this run, OP-Runner-002 is a reasonable next step to
scope out. If any red-flag row fired, the next work order should close
that specific gap — not "build the triggered runner and hope it doesn't
come up."

---

## 7. CP-OP01–04 — verifying the automation loop itself

The checklist above validates the *lifecycle*; this section validates the
*automation* added on top of it (state machine, bounded retry, idempotent
import). See `docs/background-dev-team-system-design.md` §17 for the full
design writeup, and `docs/manual-e2e-checklist.md` AC13–AC23 for the
step-by-step browser walkthrough of every item below.

> **Status as of 2026-09-18** (Operator Control Plane v1 stabilization
> pass): every item below has been verified either live (real UI + real
> backend + real Supabase project, via two throwaway `[VERIFICATION]`-
> prefixed work orders, deleted/left in a terminal state afterward — see
> `docs/manual-e2e-checklist.md`'s verification table for exactly which)
> or via the automated test suites (`scripts/test_bounded_retry.py`,
> `scripts/test_import_result_integrity.py`), which were re-run and pass.
> The one item explicitly **not** covered by this pass: a live run of
> `scripts/run_work_order.py --mode execute --adapter claude_code`
> actually spawning the `claude` CLI (budget enforcement, real subprocess
> retry) — that needs a real user bearer token, which per this session's
> credential-handling guardrails could not be extracted from the browser
> session automatically. `_run_adapter_with_bounded_retry()`'s logic
> itself is fully covered by `test_bounded_retry.py` with a faked adapter.

**State machine (CP-OP01):**
- [x] An illegal transition (e.g. `draft → accepted`) is rejected with
  `400`, and — critically — produces **zero** new `activity_logs` rows
  (a rejected transition must not leave a partial audit trail). — verified live
- [x] A legal transition produces **exactly one** new `activity_logs` row
  with `event_type: "status_transition"` and `metadata` containing
  `from_status`, `to_status`, `actor`, `source`, `reason` — never zero,
  never more than one. — verified live
- [x] Re-PATCHing the status a work order is already in returns success
  with no new audit row (documented no-op — this is what makes a repeated
  result import safe, see below). — verified live (RPC-level)
- [x] Each of `needs_approval → queued`, `blocked → queued`, `failed →
  queued`, `rework_requested → queued`, and `<non-terminal> → cancelled`
  (including `review_ready → cancelled`) succeeds via the UI's Requeue/
  Cancel buttons. — verified live via real browser clicks (AC13–AC17)

**Bounded retry (CP-OP02):**
- [x] A harness-detected technical failure (adapter exception, or no
  parseable result) with an **unchanged** working tree triggers a retry —
  up to 3 attempts total, each with its own `agent_runs` row
  (`attempt_number`, `retry_reason`). — verified via `test_bounded_retry.py`
- [x] A runner-*reported* `blocked`/`failed` result (a real, parsed result
  JSON) is **never** retried, regardless of `finalStatus`. — verified via `test_bounded_retry.py`
- [x] A technical failure with a **changed** working tree (or an
  undeterminable git state) skips retry entirely and fails the work order
  immediately with reason `technical_failure_with_worktree_changes`. — verified via `test_bounded_retry.py`
- [ ] `work_orders.status` stays `running` throughout a retry sequence —
  it never visits an intermediate status for the retry itself. — not independently re-verified this pass (implied by the retry loop never calling `transition_work_order`, but not directly observed against a live 2nd+ attempt)
- [x] Cancelling mid-sequence (before an attempt, or after a valid result
  but before import) stops the loop and leaves no `agent_runs` row stuck
  on `running` (closed as `failed` — see system design doc §17 for why not
  `blocked`/`completed`). — verified via `test_bounded_retry.py`
- [x] For a credit-consuming adapter, the total budget is enforced
  cumulatively — verify by giving a small `--max-budget-usd` and
  confirming attempt 2 is refused once attempt 1's (unreported or
  reported) cost already consumes it. — verified via `test_bounded_retry.py`
  (`test_reported_cost_correctly_decrements_cumulative_budget`,
  `test_unreported_cost_conservatively_assumes_full_remaining_budget_spent`);
  not exercised against a real `claude` subprocess this pass (see status note above)

**Idempotent import (CP-OP03):**
- [x] Re-importing the identical `result.json` twice produces no duplicate
  `activity_logs`/`artifacts` rows (see AC22). — verified live (direct upsert test) and via `test_import_result_integrity.py`
- [x] A partial import (some items fail to write) followed by a corrected
  re-import of the **same** `agent_run`'s result fills in only the missing
  slots — already-landed items are not duplicated (see AC23). — verified via `test_import_result_integrity.py`
- [ ] Confirm the known v1 limit: reordering items between re-imports of
  the *same* `agent_run_id` is not supported (position is canonical) — not
  a bug to file if encountered, a documented constraint. — not exercised this pass

**Visibility (CP-OP04):**
- [x] `WorkOrderDetail`'s Agent Runs section shows `attemptNumber` for
  every run and a translated retry reason for attempt 2+. — Attempt 1 confirmed live; attempt 2+ label confirmed by code read only (LocalRunnerPanel.tsx), not by a live 2nd attempt
- [x] A work order in `failed` status shows the dedicated failure banner
  with a human-readable (not raw machine-code) explanation. — verified live (AC15)
- [x] Clicking **Cancel** always shows the inline confirm step first —
  never fires on the first click. — verified live (AC17), including the "No, keep it" path

**Explicit v1 limits — confirm these are true, not regressions:**
- [ ] Cancelling a work order while a `claude` subprocess is genuinely
  mid-execution does **not** kill that process — it keeps running to
  completion or its own timeout; only the *next* harness status check
  reacts to the cancellation.
- [ ] There is no cryptographic distinction between a human's UI click and
  a script claiming `source: "ui"` — `actor`/`source` are self-reported.
- [ ] The Approval Scope still has no runtime enforcement beyond
  `claude_code`'s wall-clock timeout — a scope violation mid-execution is
  not mechanically blocked.
