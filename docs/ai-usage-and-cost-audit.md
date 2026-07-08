# AI Usage & Cost Audit

Pure analysis, no implementation (OP-AI-Usage-Audit-001). Every claim below is
traced to a specific file; nothing here is guessed. No secrets were read, no
`.env` files were opened (only `.env.example`/`.env.local.example` template
files, which contain variable names and non-secret placeholders/URLs, not real
credentials), no LLM calls were made to produce this document.

## 1. Executive Summary

CommandPilot has exactly **one production AI touchpoint that costs money on
its own initiative**: `POST /api/plans/generate` (OpenAI `gpt-4o`), and it is
already well-guarded — daily spend cap, usage logging, pre-flight duplicate
check. The **second** real-money surface is the local `claude_code`
RunnerAdapter, which is human-triggered only (never backend-triggered) and
was just hardened with a mandatory budget gate (OP-ClaudeBudgetGate-001)
after a real, uncapped $1.40 run during its own verification.

The most important finding isn't cost, though — it's **scope enforcement**:
`approval_scope.allowed_paths`/`blocked_paths` are checked by our own harness
before a run starts, but **never actually handed to Claude Code's own tool
permissions**. Once `claude_code` is running, nothing technical stops it from
reading (or, depending on how `--allowedTools` resolves in practice, writing)
outside the paths a work order claims to restrict it to. That gap matters
more the closer this system gets to less-supervised automation, and should be
closed before that happens — see §9.

Everything else found is either already well-bounded (the runner prompt,
review context, project context) or a small, cheap fix (the daily-plan
prompt's one unbounded input: user rules).

## 2. Alle AI Touchpoints

| # | Touchpoint | File(s) | Triggered by |
| - | --- | --- | --- |
| A | Daily plan generation | `backend/app/services/ai_service.py`, `backend/app/routers/plans.py` | `POST /api/plans/generate` — one real OpenAI completion per call |
| B | AI health/reachability probe | `backend/app/routers/health.py` | `GET /api/health/ai?ping=true`, gated behind `X-Debug-Token` header matching `DEBUG_HEALTH_TOKEN` env var (empty by default → disabled) |
| C | Morning check-in submit button | `frontend/components/morning/CheckinForm.tsx` | UI trigger for **A** — the only UI path that reaches a real backend AI call |
| D | "Generate Runner Prompt" button | `frontend/components/operator/RunnerPromptPanel.tsx`, `frontend/lib/generateRunnerPrompt.ts` | Click — **100% client-side string building, zero network call, zero LLM cost** |
| E | Local Runner panel | `frontend/components/operator/LocalRunnerPanel.tsx` | Displays copy-paste commands only — never calls AI itself; the human's own terminal does |
| F | `claude_code` adapter execute | `scripts/runner_adapters/claude_code.py`, `scripts/run_work_order.py` | Human runs `--mode execute --adapter claude_code` locally — real `claude` CLI call, now budget-gated |
| G | `manual_prompt` adapter | `scripts/runner_adapters/manual_prompt.py` | Human pastes `prompt.md` into their own, separate Claude Code/Codex session — real cost, but entirely outside CommandPilot's visibility or control |
| H | `codex` / `openclaw` adapters | `scripts/runner_adapters/codex.py`, `openclaw.py` | Not implemented — `execute()` raises `NotImplementedError` unconditionally. Zero real calls today |

## 3. Welche Modelle/Tools werden genutzt

Two **entirely separate billing surfaces** — worth stating explicitly, since
nothing in the codebase unifies them and it would be easy to assume they're
the same budget:

- **OpenAI** (`backend/app/services/ai_service.py`): `gpt-4o` by default,
  overridable via `OPENAI_MODEL` env var (name only — see `backend/app/core/config.py`).
  Called via `AsyncOpenAI().chat.completions.create(...)` with a strict JSON
  schema (`response_format`). Billed against whatever `OPENAI_API_KEY` account
  is configured for this deployment.
- **Claude** (`scripts/runner_adapters/claude_code.py`): the local `claude`
  CLI, resolved via `shutil.which("claude")`, invoked as a subprocess. Billed
  against whatever account the operator's own `claude` CLI is authenticated
  with (their own Claude subscription/API key) — **not** `OPENAI_API_KEY`,
  and not tracked in `ai_usage_log` at all (see §7).
- **Codex / OpenClaw**: unresearched. `codex.py`'s `command_template` is an
  explicit, documented guess (`"codex exec --prompt-file {prompt_file}"`),
  never verified the way `claude`'s CLI was (via real `--help` output plus a
  live, cost-capped call). `openclaw.py` is a named slot with zero
  verification of any kind.

## 4. Wann wird KI ausgelöst?

- **A/C (OpenAI daily plan)**: exactly once per user per calendar day under
  normal use — blocked by a pre-flight duplicate-plan check (`409` if a plan
  already exists for the date) before the AI call happens. A failed attempt
  can be retried (the client preserves `checkinId` rather than creating a
  new check-in), so a user could in principle trigger multiple real OpenAI
  calls in one day by retrying after failures — bounded in practice by the
  daily spend cap, not by a call-count limit.
- **B (health ping)**: only when explicitly queried with the right debug
  token — not part of any normal user flow.
- **F (claude_code execute)**: only when a human explicitly runs
  `--mode execute --adapter claude_code` with a budget set. Never triggered
  by the backend, never triggered automatically, never triggered by any UI
  button — `LocalRunnerPanel` only ever shows the command to copy.
- **G (manual_prompt)**: whenever a human decides to paste `prompt.md`
  somewhere — entirely a human action, at a time of their choosing.

## 5. Verbrauchsrisiko: low / medium / high

| Touchpoint | Risk | Why |
| --- | --- | --- |
| A/C — Daily plan generation | **Medium** | Real cost every call, but capped ($0.50/user/day soft cap in `usage_service.py`), single structured completion, fixed model, logged. Medium rather than low only because the daily cap is soft (can be exceeded slightly by concurrent requests, per the service's own documented semantics) and one input (rules) is unbounded — see §6/§9. |
| B — Health ping | **Low** | `models.list()` is a reachability check, not a completion — negligible cost. Gated behind a token that's empty (disabled) by default. |
| D — Generate Runner Prompt | **None** | Verified: zero network calls, pure client-side string templating. |
| F — claude_code execute | **Medium** (was **High** before this session's budget gate) | A real run cost $1.40 over 24 turns with no cap set at the time — proof this was a real, not theoretical, risk. Now hard-gated: `execute()` refuses without an explicit `--max-budget-usd`/`COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`. Still Medium, not Low, because nothing scopes *which* files it reads (§6) and the budget is a spend ceiling, not a scope ceiling. |
| G — manual_prompt | **Untracked, not "none"** | Real cost happens (the human is paying for their own Claude Code/Codex session), but CommandPilot has zero visibility into it — not logged anywhere in this system, unlike A. |
| H — codex/openclaw | **None today** | Not implemented. |

## 6. Big-O / Kontext-Risiko

**Daily plan prompt (`backend/app/prompts/daily_plan.py:build_user_prompt`)**
— mostly O(1) per call, with one clear exception:
- `rules_block`: **O(number of active rules for the user), unbounded.**
  `checkin_service.get_active_rules_for_user()` has no `LIMIT` and no
  character cap — every active rule a user has ever created is included on
  *every single* daily plan generation, forever. A long-time user who
  accumulates 100+ "always relevant" rules pays (in tokens, on every call)
  for all of them, silently, with no warning anywhere.
- `review_block`: **bounded** — `_REVIEW_CONTEXT_CAP = 500` characters,
  already capped. Good existing pattern.
- `projects_block`: **bounded** — `project_service.get_active_projects_for_morning()`
  explicitly caps at 5 (3 active + 2 waiting), with deterministic Main
  Signal / Secondary / Noise assignment done in Python *before* the prompt is
  built — the docstring even says so: "Signal logic (deterministic — AI does
  not choose)." This is the model the rules cap below should copy.
- `checkin.raw_input`/`important_tasks`/`fixed_events`: unbounded free text,
  but self-limiting in practice (a human typing during a morning check-in).

**Runner prompt (`scripts/runner_adapters/base.py:build_runner_prompt`,
mirrored in `frontend/lib/generateRunnerPrompt.ts`)** — O(ticket-plan step
count × step description length) + O(acceptance-criteria count). Confirmed
by reading the function body: it draws only from `order`'s `steps`,
`acceptance_criteria`, `missing_context`, and `approval_scope` — **it does
not include `activity_log`, `artifacts`, or `agent_runs`.** This is a good,
already-bounded design: prompt size scales with how much a human explicitly
planned (steps someone typed), not with how much history has accumulated
(logs/artifacts from past runs never leak back into a future prompt). The
only latent gap: nothing server-side caps the number of steps a work order
can have (`WorkOrderStepCreate` has no max-length validator) — low risk in
practice since steps are human-authored, not machine-generated in a loop.

**The real unbounded surface is what happens *after* `claude_code.py` invokes
the CLI, not the prompt we hand it.** Once running, Claude Code's own
agentic loop reads the repo via its `Read`/`Glob`/`Grep` tools — access that
`_map_allowed_tools()` grants unconditionally
(`_BASE_ALLOWED_TOOLS = ["Read", "Glob", "Grep"]`, no path scoping) regardless
of the work order's `allowed_paths`. This was empirically observed, not
theorized: one real work order (documentation-only in scope) took 24 turns
and read over 1,000,000 cached input tokens before finishing, at a cost of
$1.40. That is effectively **O(repo size × exploration depth)**, and neither
quantity is bounded by anything CommandPilot controls today — only the
CLI's own `--max-budget-usd` (a dollar ceiling, added this session) and the
harness's wall-clock timeout act as backstops. Nothing scopes *which* files
are even visible to it.

**Minor, low-priority items:**
- `scripts/runner_adapters/base.py:extract_json_result()` does a backward
  brace-matching scan that is O(n²) in a pathological worst case (many
  unmatched `}` characters). Negligible at realistic CLI-output sizes
  (KB-scale); not worth touching unless output sizes grow dramatically.
- `usage_service.get_daily_spend_usd()` sums `cost_usd` rows in Python after
  fetching all of a user's rows for the day rather than using a SQL `SUM` —
  explicitly documented as fine at the expected scale (<20 rows/user/day,
  self-limiting because the cap itself prevents unbounded accumulation).

## 7. Stellen mit unnötigem Kontext

1. **`rules_block` has no cap** — every active rule, every call, forever.
   The single clearest "unnecessary context" finding in the whole codebase,
   and the cheapest to fix (§8).
2. **Claude Code's file visibility isn't scoped to `allowed_paths`.** The
   adapter grants blanket `Read`/`Glob`/`Grep` (and, when code-edit actions
   are allowed, blanket `Edit`/`Write`) with no path restriction passed to
   the CLI at all — `allowed_paths`/`blocked_paths` exist only as (a) a
   pre-flight "must not be empty" check in `run_work_order.py`'s
   `check_execute_path_safety()`, and (b) narrative text in the generated
   prompt asking the agent to respect them. There is no technical boundary
   matching the two blocked-content categories that matter most —
   `blocked_paths` explicitly lists `.env`, `**/*token*`, `**/*key*`,
   `**/secrets/**`, yet nothing prevents the `Read` tool from opening them.
3. **`--allowedTools`/`--disallowedTools` are repo-wide, not path-scoped.**
   `_map_allowed_tools()` maps work-order action slugs onto blanket tool
   names (`"Edit"`, `"Write"`) rather than any path-qualified form — if
   Claude Code's permission syntax supports path-scoped tool grants (its
   `--help` output shows `Bash(git *)`-style patterns for one case, but this
   wasn't verified for `Edit`/`Write`/`Read`), that capability isn't used
   here yet.

## 8. Quick Wins

Cheap, low-risk, no architecture change required:

- **Cap `rules_block`** the same way `review_block` already is: add a
  `LIMIT` to `get_active_rules_for_user()`'s query (e.g. top 20 by
  `priority`, which the query already orders by) and/or a total-character
  cap mirroring `_REVIEW_CONTEXT_CAP`. Directly copies an existing, proven
  pattern in the same file family.
- **Warn (or soft-cap) on very large ticket plans** — e.g. a client-side or
  server-side notice above ~15 steps on work-order creation, before it
  becomes a real prompt-size habit.
- **Log a pre-flight token/size estimate for the daily-plan prompt**, not
  just post-hoc actual usage — cheap (just `len(prompt)`-style logging),
  purely diagnostic, no behavior change.
- **Document the two-billing-surfaces split explicitly** (OpenAI daily cap
  vs. Claude budget gate) in one place a future reader will actually find —
  today it's implicit across three different docs.

## 9. Must Fix vor weiterer Automatisierung

1. **Path/tool scoping enforcement gap (§7, items 2–3).** This is the one
   finding that's a genuine safety gap, not just a cost-efficiency one: a
   work order's `allowed_paths`/`blocked_paths` are currently enforced by
   *convention* (the prompt asks nicely) and by a *pre-flight* check (the
   harness refuses to start if the field is empty) — never by anything that
   stops the running CLI itself from touching an out-of-scope file. Before
   building the previously-discussed "Sandbox Worker MVP" or reducing human
   supervision any further, this needs either (a) verified, path-scoped
   `--allowedTools`/`--add-dir` usage if Claude Code's CLI actually supports
   it — checked for real, the way the CLI's `-p`/`--output-format json`
   behavior was verified this session, not guessed — or (b) a real
   filesystem-level sandbox/allowlist wrapping the subprocess.
2. **Cap `get_active_rules_for_user()`.** Unbounded growth that silently
   costs real money on every single daily-plan call, for the lifetime of a
   user's account. Small, mechanical fix; no design questions to resolve.
3. **State explicitly, somewhere both are documented, that the OpenAI daily
   cap and the Claude budget gate are two unrelated systems** with no shared
   accounting — not urgent to unify, but risky to leave implicit if someone
   later assumes "budget" means one combined number.

## 10. Empfohlene Budget-/Usage-Gates

- **OpenAI / daily plan (already has one)**: `DAILY_CAP_USD = $0.50/user/day`
  (soft cap, `usage_service.py`). Recommend pairing it with the rules-cap
  fix above (§9.2) so the cap is protecting against genuinely bounded
  inputs, not silently eroding headroom as a user's rule list grows.
- **claude_code (already has one, added this session)**:
  `--max-budget-usd` / `COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`, hard-required
  before `execute()` runs at all, no silent default anywhere in the code.
  Recommend it stay paired with the scope-enforcement fix (§9.1) — a dollar
  cap alone doesn't stop a run from touching the wrong files within that
  budget.
- **Single-number visibility**: consider surfacing one combined "max this
  run could cost" figure in the Operator UI per work order (today an
  operator has to mentally combine `approval_scope.max_cost_usd` and
  whatever `--max-budget-usd` they typed — `claude_code.py`'s
  `_build_cli_args()` already resolves these into one effective number
  internally; showing that resolved number, not just the two separate
  inputs, would remove a small but real point of confusion).
- **codex/openclaw**: the `consumes_paid_credits` gate in
  `RunnerAdapter`/`run_work_order.py` already generalizes to any future
  adapter — when either is implemented for real, make sure
  `consumes_paid_credits=True` stays set (it already is, conservatively) and
  that the same budget gate is exercised by a real dry run before shipping,
  the same way `claude_code` was.

## 11. Empfehlung für Runner-Auswahl

- **`manual_prompt`** — recommended default for anything exploratory,
  unfamiliar in scope, or cost-sensitive. Zero risk from CommandPilot's own
  perspective (§5); the human stays in the loop for every single action,
  and whatever it costs is paid for and watched by them directly in a
  session they already control.
- **`claude_code`** — reasonable once (a) the one-time workspace trust is
  accepted, (b) a small, deliberate budget is set every time (never assume
  a previous session's habit), and (c) the work order's scope is narrow and
  well-understood. **Not yet recommended for large, exploratory, or
  many-step work orders** until §9.1's path-scoping gap is closed — a
  broad/ambiguous task is exactly what produced the real $1.40/24-turn
  session this audit keeps citing as evidence, not a hypothetical.
- **`codex`** — not usable yet. `command_template` is an explicit, labeled
  guess; do not wire it up without the same real, empirical CLI
  verification `claude_code` received (real `--help` output plus one
  minimal, cost-capped live call) — guessing flags for a second CLI would
  repeat the exact risk this audit is trying to head off.
- **`openclaw` (future)** — entirely unresearched. Treat
  `consumes_paid_credits=True` as a conservative placeholder, not a
  finding; nothing about its actual cost or capability profile is known,
  and it should not be treated as if it were.

## Consolidated Priority List

**Must Fix** (before less-supervised automation):
1. Path/tool scoping enforcement gap — `allowed_paths`/`blocked_paths` not
   enforced at the Claude Code tool-permission layer (§7.2–3, §9.1).
2. Unbounded `rules_block` in the daily-plan prompt — no `LIMIT`, no
   character cap (§6, §9.2).

**Should Fix** (cheap, no architecture change, do when convenient):
3. Warn/soft-cap on very large ticket plans (many work-order steps) (§8).
4. Log a pre-flight size/token estimate for the daily-plan prompt, not just
   post-hoc (§8).
5. Document the OpenAI-daily-cap vs. Claude-budget-gate split as two
   unrelated systems, explicitly, in one place (§8, §9.3).
6. Surface one resolved "max this run could cost" number in the Operator UI
   per work order, instead of two separate inputs an operator has to
   combine mentally (§10).

**Later** (low priority, no action needed now):
7. `extract_json_result()`'s O(n²) worst-case brace-matching scan —
   negligible at realistic output sizes (§6).
8. `get_daily_spend_usd()` sums rows in Python rather than SQL `SUM` —
   fine at documented expected scale, self-limiting by the cap itself (§6).
9. `plan/CampsPilot-Roadmap-v0.2-v0.3.pdf` could not be rendered in this
   environment (`pdftoppm`/poppler-utils not installed) — not read, not
   confirmed relevant to AI usage/cost; flagged rather than skipped
   silently. No dependency was installed to work around this (installing
   one is itself an action requiring approval, and out of scope here).

---

*No application code was changed to produce this document. No LLM calls were
made. No secrets or `.env` files (only `.env.example`/`.env.local.example`
templates) were read.*
