# Background Dev Team — Runbook

Practical, step-by-step. This is the golden path from "nothing deployed" to
"a real work order went through a runner and came back for review." Follows
directly from `docs/background-dev-team-system-design.md` — read that first
if you want the *why*, this doc is the *how*.

## 0. One-time setup

**0.1 Run the migrations.** In the Supabase SQL editor, run (in order, if
not already applied):
- `supabase/migrations/006_work_orders.sql`
- `supabase/migrations/007_work_order_steps.sql`
- `supabase/migrations/008_work_orders_team_type.sql`

(Fresh project instead? Just run `supabase/schema.sql` — it already
includes all three.)

**0.2 Start the backend and frontend** (see root `README.md` §2/§3 if you
haven't already), each in its own terminal window/tab — running both from
one window is the easiest way to accidentally type an API command into the
wrong process's prompt:

```powershell
# Terminal 1
cd backend
uvicorn app.main:app --reload --port 8000
```
```powershell
# Terminal 2
cd frontend
npm run dev
```

**0.3 Log in** at `http://localhost:3000/login` with your normal
CommandPilot account.

## 1. Get an API token for the import script

The import script authenticates as *you* — it's not a service account, it
uses your own already-logged-in session token, the same way the frontend
does. Nothing secret about your project is read to get it.

> **Token hygiene.** This token is a bearer credential for your own
> account. Never paste it into a chat window (including a Claude Code /
> agent session), a commit, an issue, or any report — treat it like a
> password. If one ever ends up somewhere it shouldn't, it's short-lived
> (see below), but don't rely on that; get a fresh one and let the old one
> expire on its own.

1. With the CommandPilot tab open and logged in, open browser DevTools →
   Application (Chrome) / Storage (Firefox) → Local Storage →
   `http://localhost:3000`.
2. Find the key starting with `sb-` and ending in `-auth-token` (Supabase's
   default storage key for the JS client's session).
3. Its value is JSON; copy the `access_token` field. That's your token.
4. Set it for your current terminal session (**PowerShell**, the commands
   in this doc target PowerShell throughout — Windows is this project's
   primary dev environment):
   ```powershell
   $env:COMMANDPILOT_API_TOKEN = "paste-your-token-here"
   ```
   Note the `$env:` prefix — **`$COMMANDPILOT_API_TOKEN` without `env:` is
   a different, unset PowerShell variable** and every command below will
   silently send an empty/wrong token if you drop it. This exact mistake
   happened during real testing of this flow; it's not a hypothetical.

   (bash/zsh equivalent, if you're not on PowerShell: `export COMMANDPILOT_API_TOKEN="paste-your-token-here"`.)

Tokens expire (Supabase default: 1 hour). If the import script starts
getting 401s, repeat this step.

## 2. Create a work order

**In the UI (recommended, OP-Create-001):** open `http://localhost:3000/operator`
and click **New Work Order** (top right, or the empty-state button if you
have none yet). Fill in:
- **Title**, **Goal / Description**, **Repository / Project**, **Time
  limit (minutes)** — all required.
- **Team type** — defaults to `development`; leave it unless this work
  order is for something else (see system design doc §0 — team types
  beyond development aren't built out yet, but the field is real and
  persisted either way).
- **Acceptance criteria** — one per line, at least one required.
- **Approval Scope** (allowed / requires-approval / blocked actions, plus
  optional allowed/blocked paths) — pre-filled with the standard
  Background Dev Team defaults (see below); edit freely, but
  **blocked actions can't be empty** — that's a hard safety rule, not a
  formality (system design doc §5/§11).

Submitting creates the work order, its approval scope, **and 6 ticket-plan
steps automatically** (Product → Architect → Coder → QA → Reviewer →
Reporter — the same roles `generate_runner_prompt` walks through), then
redirects you straight to the detail page. Copy the id from the URL — the
rest of this doc calls it `YOUR_WORK_ORDER_ID` (no angle brackets — in
PowerShell, a bare `<...>` is parsed as input redirection and errors out,
so every example below uses a plain placeholder you can find-and-replace
safely instead).

Default Background Dev Team approval scope (pre-filled, edit as needed):

| | |
| --- | --- |
| Allowed | `repo_read`, `plan_create`, `code_edit_within_scope`, `test_lint_typecheck`, `local_artifacts`, `review_package_write` |
| Requires approval | `dependency_install`, `external_service_change`, `migration_execute`, `push_or_pr_create`, `runtime_or_cost_increase`, `major_architecture_change` |
| Blocked | `deploy`, `production_data_write`, `secrets_read_or_log`, `email_send`, `payment_action`, `destructive_git`, `direct_main_change`, `user_data_export` |

**If the form shows a red error banner** mentioning "looks like a blocked
action": you moved something like `deploy` or `secrets_read_or_log` into
Allowed or Requires-approval instead of Blocked. That's the backend safety
validator working as intended (system design doc §5/§11) — move it to
Blocked and resubmit; nothing was saved.

**Via `curl` instead** (for scripting, or if you'd rather not use the UI).
PowerShell's `curl` is an alias for `Invoke-WebRequest` with different
flags — either use `curl.exe` explicitly, or use `Invoke-RestMethod`
directly:

```powershell
curl.exe -s -X POST http://localhost:8000/api/work-orders `
  -H "Authorization: Bearer $env:COMMANDPILOT_API_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{
    "title": "My first background dev-team run",
    "goal": "Describe in plain language what you want done.",
    "repo": "commandpilot",
    "team_type": "development",
    "time_limit_minutes": 60,
    "acceptance_criteria": ["Concrete, checkable criterion 1", "Criterion 2"],
    "approval_scope": {
      "allowed_actions": ["repo_read", "plan_create", "code_edit_within_scope", "test_lint_typecheck"],
      "requires_approval": ["push_or_pr_create", "dependency_install"],
      "blocked_actions": ["deploy", "production_data_write", "secrets_read_or_log", "destructive_git"],
      "max_runtime_minutes": 60
    },
    "steps": [
      { "title": "Product Agent", "assigned_role": "product" },
      { "title": "Architect Agent", "assigned_role": "architect" },
      { "title": "Coder Agent", "assigned_role": "coder" },
      { "title": "QA Agent", "assigned_role": "qa" },
      { "title": "Reviewer Agent", "assigned_role": "reviewer" },
      { "title": "Reporter Agent", "assigned_role": "reporter" }
    ]
  }' | python -m json.tool
```

Copy the `id` from the response — that's your `YOUR_WORK_ORDER_ID`.

### Cross-repo work orders (OP-Runner-RepoPath-001)

By default a work order's `repo` field is just a free-text label, and the
generated runner prompt assumes Control Plane (CommandPilot) and Execution
Context are the same repo — fine for a work order that edits CommandPilot
itself, confusing for one that edits an entirely different project (e.g.
Sommercamps/CampsPilot), because the prompt would still mention
CommandPilot import paths and `scripts/run_work_order.py`, neither of which
exist in that other repo.

Two **optional** fields fix this — leave both blank and nothing changes
from before:
- **Target repo name** — a display label, e.g. `Sommercamps`.
- **Target repo path** — a local filesystem path, purely informational
  context shown in the prompt and the Local Runner panel. **CommandPilot
  never reads from, cd's into, or executes anything at this path** — it is
  not a shell trigger, just a hint for whoever (human or agent) is about to
  work in that other repo.

When set, the generated runner prompt clearly separates:
- **Control Plane**: CommandPilot — where `scripts/run_work_order.py` runs
  and where the result gets imported back (step 5 below), regardless of
  which repo the work order targets.
- **Target Repo**: the external project — where the actual analysis/coding
  happens. The prompt tells the runner explicitly: it's working in the
  target repo, CommandPilot scripts won't exist there, don't write
  `result.json` inside the target repo unless told to, and to return a
  normal analysis/report (or write the result to the CommandPilot tmp path
  only if that path happens to be reachable from there).

The Local Runner panel on the work order's detail page shows the same
split for a cross-repo work order: which command runs in CommandPilot vs.
where Claude/Codex's actual working context is — see step-by-step below,
same flow either way (§3–§7 are unaffected by whether a work order is
cross-repo or not).

## Fast Path: Local Runner Harness (recommended, OP-Runner-002/003)

Sections 3–6 below (approve/queue/run in the UI, click "Generate Runner
Prompt", copy it by hand, import the result with a separate command)
still work and are documented in full because they're what's actually
happening underneath — read them once to understand the mechanics. Day to
day, `scripts/run_work_order.py` does the same thing in fewer steps. The
**Local Runner** panel on a work order's detail page shows these exact
commands pre-filled with the real id and correct PowerShell syntax — copy
from there instead of retyping anything below.

**The flow is: Draft → Approved → Queued → the runner sets Running itself.**
In the UI, click **Approve**, then **Mark Queued** — and stop there. **Do
not click Mark Running yourself.** The harness does that automatically in
the next step, and clicking it manually first just means you'll need
`--force` later for no benefit (this exact sequence — manual click, then
hitting a `--force`-required error — happened during real testing; it's
avoidable by simply not clicking Running).

**Step A — start the runner (generates the prompt, sets status to
running).**

```powershell
python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode prompt-file --token $env:COMMANDPILOT_API_TOKEN
```

This fetches the work order, runs hard safety checks (see below), sets its
status to `running` and its first step to `running`, writes an
`activity_log` entry, and creates a session folder:

```
tmp/work-order-runs/YOUR_WORK_ORDER_ID/
  prompt.md            — the exact runner prompt, ready to paste
  result.schema.json   — the result JSON's shape, for reference
  result.example.json  — a fill-in-the-blanks template with your real step ids
  run.log              — what the harness itself did, with timestamps
```

(`tmp/` is gitignored — these are local, throwaway session files, never
committed.)

**Step B — run it.** Two options:

**B1. Manual (`manual_prompt` adapter, the default — always works).** Paste
`prompt.md`'s contents into a fresh Claude Code or Codex session (same as
manual §5). Save its result JSON as
`tmp/work-order-runs/YOUR_WORK_ORDER_ID/result.json`.

**B2. `claude_code` adapter (OP-ClaudeAdapter-001, semi-automatic).**

```powershell
python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode execute --adapter claude_code --max-budget-usd 0.20 --token $env:COMMANDPILOT_API_TOKEN
```

This calls the local `claude` CLI directly (`claude --print
--output-format json`, argument list, no shell string interpolation),
piping in `prompt.md` and mapping the approval scope's `allowed_actions`
onto `--allowedTools`/`--disallowedTools`. **Things to know before using
this:**
- **`--max-budget-usd` (or `COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`) is
  required, not optional** (OP-ClaudeBudgetGate-001). Omit it and the
  command refuses to run at all:
  ```
  ERROR: Claude Code execution would consume usage credits. Set --max-budget-usd or use --mode prompt-file.
  ```
  This is deliberate — see "Working without spending Claude credits"
  below for the full rationale. `0.20` above is a suggested starting
  point to edit, not a value the script assumes for you; there is no
  silent default anywhere in this codebase.
- **One-time workspace trust.** Claude Code refuses to honor this
  project's permission settings — even non-interactively — until you've
  opened `claude` here once interactively and accepted the trust dialog.
  Do that once; after that, `--mode execute --adapter claude_code` works
  unattended. If you skip this, the adapter detects the "not been
  trusted" message and fails with a clear error rather than silently
  running with the wrong permissions.
- **"Semi-automatic," not "unattended," is the honest label** — this is
  why `--adapter claude_code` is not the default. It genuinely calls
  Claude Code for you and, on success, auto-imports the result (Steps B+C
  collapse into one command) — but it depends on that one-time trust step
  outside the adapter's control, and Claude Code's own cost floor means
  even a trivial work order costs real money (a one-line test prompt cost
  ~$0.05 in verification for this feature; a real multi-turn work order
  can cost well over $1). It does **not** `--dangerously-skip-permissions`
  to work around any of this — that flag would defeat the entire
  approval-scope model, so this adapter never passes it, on purpose.
- If it fails partway, check `execute_output.log` and (if present)
  `permission_denials.json` in the session folder before re-running.

### Working without spending Claude credits

**`--mode prompt-file` never spends anything, regardless of adapter** —
it only writes `prompt.md`/`claude_command.txt` locally; nothing calls a
paid API. Neither does the fully manual path (§4/§5 below, or Step B1
above): you paste the prompt into whatever session you already have open
and pay for that the same way you always would, entirely outside
CommandPilot's control. **This is why `manual_prompt` is the default
adapter** — it's the only one with zero risk of CommandPilot itself
triggering a charge.

**Starting `claude_code` with a small budget:** pick a number you're
comfortable losing if the estimate is wrong (repo verification during
development showed a trivial one-line prompt costs ~$0.05 and a real
multi-turn task can run past $1), then either:
```powershell
python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode execute --adapter claude_code --max-budget-usd 0.20 --token $env:COMMANDPILOT_API_TOKEN
```
or set it once per PowerShell window so you don't have to repeat it:
```powershell
$env:COMMANDPILOT_CLAUDE_MAX_BUDGET_USD = "0.20"
python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode execute --adapter claude_code --token $env:COMMANDPILOT_API_TOKEN
```
The CLI flag wins if both are set. Neither this gate nor the CLI's own
`--max-budget-usd` enforcement can be bypassed with a flag — there is no
"skip this check" option, on purpose.

**Why `prompt-file` (+ manual paste) is the safe default:** it's the only
path where a human reads the prompt and decides to spend money *before*
anything happens, in a session they're already paying for and already
watching. `claude_code`'s automation trades that human-in-the-loop moment
for convenience — worth it once you trust the scope and want less
copy-paste, but never the first thing to reach for on a new or unfamiliar
work order.

**Step C — import (only needed if Step B didn't already auto-import).**

```powershell
python scripts/run_work_order.py YOUR_WORK_ORDER_ID --mode import-result --token $env:COMMANDPILOT_API_TOKEN
```

No file path needed — it defaults to the session folder's `result.json`.
This is the same import logic as `scripts/import_work_order_result.py`
(reused, not duplicated), so §6/§7's troubleshooting still applies. The
result JSON is validated before anything is sent — a missing required
field or invalid `finalStatus` value is reported by name, not just "invalid
JSON."

**Safety preconditions (checked before anything is touched):**
- Approval scope must exist and have a non-empty `blocked_actions` list —
  never bypassable, not even with `--force`.
- No blocked-looking keyword (deploy, secret, force push, ...) may appear
  in `allowed_actions`/`requires_approval` — same check as the backend's
  creation-time validator, run again here as defense in depth. Never
  bypassable either.
- The ticket plan must have at least one step — not bypassable.
- Status must be `approved` or `queued` — **this is the only check
  `--force` overrides**, and only use it to restart a work order that's
  already `running` (e.g. a previous attempt crashed) — not as a routine
  step.
- **Auto-execution only** (`--mode execute`, either `--runner-command` or
  an adapter's own `execute()`): if `allowed_actions` implies code changes
  and `allowed_paths` is empty, the run is **blocked outright**, not just
  warned — an unattended run with no path boundary is a real gap, not a
  formality. `--force` overrides this specific check if you're sure. (The
  Create Work Order form now pre-fills sensible default paths for
  `development` work orders specifically so you don't hit this — see §2.)

**Honesty check:** neither adapter streams *live* step-by-step updates
while Claude Code is actually thinking — the harness sets one step to
`running` at the start and then waits for the final result JSON. True live
updates need the runner to call back into CommandPilot mid-session, which
is future work — see system design doc §13/§14.

**`--adapter` flag (OP-Runner-003 / OP-ClaudeAdapter-001):**
- `manual_prompt` (default) — fully manual, always works, no dependencies.
- `claude_code` — semi-automatic, see Step B2 above.
- `codex`/`openclaw` — still named placeholders only; not implemented, not
  evaluated. See `docs/runner-adapter-contract.md`.

## 3. Check it in the UI

If you created the work order via the UI form, you're already here
(it redirects straight to the detail page). Otherwise open
`http://localhost:3000/operator/YOUR_WORK_ORDER_ID`. You should see:
- The goal, status (`draft`), and the full status-flow strip.
- **Execution Plan** with your 6 steps, all `pending`, 0% progress.
- **Approval Scope** with your allowed/needs-approval/blocked lists. If you
  left `blocked_actions` empty, you'll see an explicit warning — that's the
  UI-side half of the "safety scope isn't just convention" requirement.
- **Lifecycle** controls at the top: only "Approve" is enabled (status is
  `draft`).

Click **Approve**, then **Mark Queued**, then **Mark Running** to move the
work order through its lifecycle by hand — each button calls
`PATCH /api/work-orders/{id}` and re-fetches, same endpoint the import
script uses later.

## 4. Generate the runner prompt

On the same page, scroll to **Runner Prompt** → **Generate Runner Prompt**.
This produces a complete, paste-ready prompt containing your goal, approval
scope, the full 6-step ticket plan (with each step's real id embedded), the
repo-wide safety rules, a hard-stop instruction for scope violations, and
the exact result-JSON schema the runner must emit at the end. Click **Copy
Prompt**.

## 5. Run it in Claude Code / Codex

Paste the prompt into a fresh Claude Code or Codex session, in this repo
(or whichever `repo` you set in step 2). Let it work. It will:
- Walk the ticket plan step by step.
- Stop and mark a step `blocked` the instant it needs something outside the
  approval scope — this is expected behavior, not a bug.
- End the session by printing the result JSON block.

Save that JSON block to a file, e.g. `result.json`.

## 6. Import the result

```powershell
python scripts/import_work_order_result.py result.json --token $env:COMMANDPILOT_API_TOKEN
```

Add `--dry-run` first if you want to see exactly which API calls it's about
to make without making them. The script reports `N succeeded, M failed` at
the end and writes one line per step/log/artifact/review-package/final-
status call — partial failures don't block the rest (e.g. if one step id
was mistyped, everything else still imports).

## 7. Review the result

Refresh `/operator/YOUR_WORK_ORDER_ID`. You should now see:
- Each step's real status (`completed`/`blocked`/`failed`), its
  `outputSummary`, and `blockedReason` if applicable — progress bar updated.
- **Activity Log** populated with everything the runner reported.
- **Artifacts** showing whatever the runner produced (plans, diffs, test
  output, ...).
- **Review Package** with the runner's summary, files changed, tests run,
  risks, open questions, and verdict.
- **Lifecycle** controls now offer **Accept** and **Request Rework** (work
  order status is `review_ready`).

Read the Review Package. If it's genuinely done and safe: click **Accept**.
If something needs fixing: click **Request Rework** and go back to step 4
with updated instructions.

## Known Issues

**API tokens expire after ~1 hour.** The bearer token from §1 is a
short-lived Supabase access token (~3600 seconds), not a long-lived key. If
you pause between steps — e.g. while a runner session is working, or
between creating a work order and importing its result — a command can
suddenly start returning `401` even though nothing changed on your end.
This is expected, not a bug: the token simply expired. Fix: repeat
§1 ("Get an API token for the import script") to grab a fresh
`access_token` from Local Storage, re-export it, and retry.

**`$env:` vs bare `$VAR` in PowerShell.** Covered in §1, repeated here
because it's the single most common friction point: `$COMMANDPILOT_API_TOKEN`
(no `env:`) is a different, empty variable in PowerShell. Every command in
this doc uses `$env:COMMANDPILOT_API_TOKEN` — if you see auth failures with
no obvious cause, check this first.

**Windows console encoding (fixed).** Earlier versions of
`scripts/run_work_order.py` and `scripts/import_work_order_result.py`
crashed with `UnicodeEncodeError` on Windows the moment they tried to print
text containing an em dash or arrow (`—`, `→`) — common in German-language
prompt/result text — because Windows consoles often default to the legacy
`cp1252` codepage instead of UTF-8. Both scripts now reconfigure
stdout/stderr to UTF-8 at startup (`errors="replace"` as a last-resort
fallback for anything even that can't represent). If you're on an older
checkout and still hit this, pull the latest version of both scripts.

**Claude Code workspace trust (adapter-specific, not a bug).** The
`claude_code` adapter's `--mode execute` genuinely fails the first time you
use it in a given repo directory, with a message about the workspace not
being trusted — this is Claude Code's own one-time safeguard, not
something this adapter can or should bypass. Fix: run `claude` once,
interactively, in this directory, and accept the trust dialog.

**Claude Code execution costs real, uncapped-by-default money
(OP-ClaudeBudgetGate-001).** Verified during development: a trivial
one-line test prompt cost ~$0.05, and one real multi-turn work order cost
$1.40 — with no budget set at the time, nothing capped it. This is why
`--mode execute --adapter claude_code` now hard-refuses to run at all
without an explicit `--max-budget-usd` or `COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`
— see "Working without spending Claude credits" above. This gate cannot be
bypassed with a flag; if you see the refusal message, that's it working as
designed, not a bug to route around.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `GET /api/work-orders/me` returns an empty list / the operator page shows the amber "seed data" banner | Migrations not run yet, or backend not running — this is the designed fallback, not a crash. |
| `422` on work order creation mentioning a blocked keyword | You put a blocked action in the wrong list — see step 2. |
| Import script: `401` on every call | Token expired — redo step 1. Double-check you used `$env:COMMANDPILOT_API_TOKEN`, not `$COMMANDPILOT_API_TOKEN`. |
| Import script: `404` on a step update | The step id in the result JSON doesn't match one from the work order's ticket plan — the runner may have invented a step; check the prompt was followed. |
| Lifecycle buttons disabled/greyed out | You're viewing seed/mock data (`isLive` is false) — the buttons only mutate a real, API-backed work order. |
| `run_work_order.py --mode prompt-file` refuses to start, "Status ist 'draft'" | Click **Approve** then **Mark Queued** in the UI first — the harness only starts from `approved`/`queued` without `--force`. |
| `run_work_order.py --mode prompt-file` refuses to start, "läuft bereits" (status is `running`) | You (or a previous run) already started it. Use `--force` only if you genuinely want to restart — e.g. a crashed prior attempt. If the runner itself just started it moments ago, this isn't an error to route around, it's the harness correctly refusing a duplicate start. |
| `run_work_order.py --mode prompt-file` refuses to start, "leere blocked_actions-Liste" | Same safety validator as work order creation — add at least one entry to `blocked_actions`, this is intentional, not a bug to route around. |
| `--mode execute` refuses to start, "allowed_paths ist leer" | Auto-execution blocks (doesn't just warn) if code changes are allowed with no path boundary. Add at least one `allowed_paths` entry (the Create form now pre-fills these for `development` work orders), or pass `--force` if you're certain. |
| `--mode execute --adapter claude_code` says "Claude Code execution would consume usage credits. Set --max-budget-usd or use --mode prompt-file." | The budget gate (OP-ClaudeBudgetGate-001) — intentional, not a bug. Add `--max-budget-usd 0.20` (or set `COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`) and retry. See "Working without spending Claude credits" above. |
| `--mode execute --adapter claude_code` fails mentioning "not been trusted" | See Known Issues above — run `claude` interactively here once. |
| `--mode import-result` says "result file not found" | It defaults to `tmp/work-order-runs/YOUR_WORK_ORDER_ID/result.json` — either save your result there, or pass `--result-file <path>` explicitly. |
| `--mode import-result` / import script says "is missing required field(s): ..." | The result JSON is missing one of `workOrderId`/`finalStatus`/`steps`/`activityLogs`/`artifacts`/`reviewPackage` — the error names exactly which. Check the runner actually followed the result-JSON schema in the prompt. |
| `--mode import-result` / import script says "invalid JSON ... at line N, column M" | The result file isn't valid JSON — the line/column point at the exact spot to check (often a trailing comma or unescaped quote if a human hand-edited it). |
| `--mode execute` (generic `--runner-command` path) says "Konnte kein gültiges Ergebnis-JSON automatisch... finden" | Best-effort detection didn't recognize the output as a result JSON — check `execute_output.log` in the session folder, save the JSON block yourself as `result.json`, then run `--mode import-result` manually. This is the expected fallback, not a failure. |
| `--mode import-result` says "finalStatus is 'review_ready' but no step has status 'completed' or 'skipped' — progress would be 0%" | The result claims the work order is done for human review, but every step is still pending/blocked/failed — the operator UI would show a 0% progress bar next to "review ready". Mark at least the steps that actually finished as `completed` (or `skipped` if genuinely not applicable), or set `finalStatus` to `blocked`/`failed` if that's the true state (OP-Import-Integrity-001). |
| `--mode import-result` says "result is missing an update for step id(s) [...]" | The result JSON omits one or more of the work order's real ticketplan steps entirely. Every step must appear in `steps` with a status, even if only to mark it `blocked` or `skipped` — this is checked against the live work order before any API call is made. |
| `--mode import-result` says "ERROR: refusing to set finalStatus='review_ready' ... work order left at its previous status" | One or more step/artifact/review-package writes failed partway through the import (see the itemized causes right above this line and the `FAIL ...` lines earlier in the output) — the script deliberately does not mark the work order `review_ready` in that case, since it wouldn't be truthfully "safe to approve without re-reading the log" (OP-Import-Integrity-001). Fix the underlying cause (often a transient API/network error — check the `FAIL` line for the actual HTTP status). Re-running the same result.json will retry the failed writes, but note it also re-POSTs any activity log entries/artifacts that already succeeded (there's no dedup) — check the work order's activity log afterward for duplicates rather than assuming a clean re-run. |
