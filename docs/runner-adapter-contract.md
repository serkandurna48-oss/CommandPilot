# RunnerAdapter Contract

## Why CommandPilot orchestrates instead of replacing

CommandPilot is not going to become a coding agent. It is the **Control
Plane**: work orders, approval scopes, execution plans (ticket steps),
activity logs, review packages, safety rules, and the context around all
of it. The actual work — reading code, writing a diff, running tests — is
always done by something else: Claude Code today, possibly Codex or
OpenClaw tomorrow, possibly a fully custom local script later. That
"something else" is a **RunnerAdapter**.

This split exists so that CommandPilot never has to be rebuilt when the
tool doing the work changes. Claude Code has a different CLI than Codex;
OpenClaw (unevaluated, see below) might have a different one again; a
future in-house tool might not even be a CLI. None of that should ever
touch `run_work_order.py`'s orchestration logic, the backend, or the
frontend — only a new file under `scripts/runner_adapters/`. If adding a
runtime ever requires changing anything outside that directory, the
contract has leaked and needs fixing before the new adapter is finished.

The Control Plane / Execution Plane boundary this formalizes was already
load-bearing in OP-Runner-002
(`docs/background-dev-team-system-design.md` §13): the backend has never
executed a shell command and still doesn't. This document is that same
principle, made into a concrete interface.

## The adapter interface

Defined in `scripts/runner_adapters/base.py`. Every adapter extends
`RunnerAdapter` (an `abc.ABC`) and provides:

```python
@dataclass
class AdapterInfo:
    name: str
    capabilities: list[str]        # what this adapter needs to do its job
    safety_level: str               # "manual" | "supervised" | "sandboxed"
    supports_live_events: bool       # can it report progress mid-run?
    supports_auto_execute: Literal["yes", "no", "semi_auto"]  # see below
    consumes_paid_credits: bool = False  # does execute() spend real LLM API money?
    command_template: str | None    # e.g. "claude --print < {prompt_file}"

class RunnerAdapter(ABC):
    info: AdapterInfo

    def check_scope_errors(self, order: dict) -> list[str]: ...     # hard, blocking
    def check_scope_warnings(self, order: dict) -> list[str]: ...   # soft, non-blocking

    @abstractmethod
    def prepare(self, order: dict, session_path: Path) -> Path: ...

    def execute(self, order: dict, session_path: Path, runner_command: str | None) -> ExecuteOutcome: ...

    @abstractmethod
    def collect_result(self, session_path: Path, result_file: str | None) -> dict: ...
```

- **`prepare(order, session_path)`** — write whatever the adapter needs
  into the work order's local session folder
  (`tmp/work-order-runs/<id>/`). For every adapter today this means a
  `prompt.md` built from the shared `build_runner_prompt()` in `base.py`,
  plus `result.schema.json`/`result.example.json` for reference. Returns
  the path to the primary artifact.
- **`execute(order, session_path, runner_command, max_budget_usd=None)`** —
  *adapter-native* invocation: the adapter knows how to actually start its
  own runtime (using its own `command_template`), without a human
  supplying `--runner-command`. Optional — only adapters with
  `supports_auto_execute` set to `"yes"` or `"semi_auto"` are expected to
  implement this meaningfully; the base class raises `NotImplementedError`
  otherwise. `"yes"` vs. `"semi_auto"` is a real distinction, not a
  formality: `"yes"` means fully unattended with no known gap; `"semi_auto"`
  means `execute()` is real but depends on something outside the adapter's
  control (see `claude_code`'s one-time workspace-trust requirement below)
  — a caller should not treat a `"semi_auto"` run's success as
  unconditional the way it would a `"yes"` adapter's. Not to be confused
  with `run_work_order.py --mode execute --runner-command "..."`, which is
  a separate, generic, adapter-agnostic escape hatch that works with any
  adapter because a human still types the exact command — that path
  predates this contract (OP-Runner-002) and is kept for backward
  compatibility, not part of the interface a new adapter must implement.

  **Budget gate (OP-ClaudeBudgetGate-001):** for any adapter declaring
  `info.consumes_paid_credits=True`, `run_work_order.py` refuses to call
  `execute()` at all — before touching anything, before `prepare()` even
  runs — unless a human has explicitly set `--max-budget-usd` or
  `COMMANDPILOT_CLAUDE_MAX_BUDGET_USD`. That value is threaded through as
  the `max_budget_usd` parameter; an adapter that spends real money while
  ignoring it isn't meeting the contract. No adapter, including
  `claude_code`, is allowed to invent a "safe-sounding" default budget of
  its own — the whole point is that CommandPilot never silently burns
  usage credits. See `docs/background-dev-team-runbook.md`'s "Working
  without spending Claude credits" section for the user-facing side of
  this.
- **`collect_result(session_path, result_file)`** — read back a runner's
  result JSON (see the schema in `base.py`'s `RESULT_JSON_SCHEMA`) and
  return it as a dict, ready for `import_work_order_result.import_result()`.

`run_work_order.py` (the orchestration layer, unchanged in spirit since
OP-Runner-002) only ever calls these methods. It does not know or care
whether "prepare" means "write a text file" or, for a future adapter,
"open a websocket" — that's the adapter's business.

`ExecuteOutcome` (CP-OP02 addition: `cost_usd`) —

```python
@dataclass
class ExecuteOutcome:
    exit_code: int
    output_log_path: Path
    result: dict | None       # parsed result JSON, if one was produced
    cost_usd: float | None = None  # actual spend for THIS call, if known
```

An adapter that can report its own real cost (`claude_code`'s
`--output-format json` wrapper's `total_cost_usd` field) should populate
`cost_usd` — the harness's bounded-retry loop (see below) uses it to track
spend cumulatively across attempts. `None` means "unknown," not "zero":
the harness treats an unreported cost conservatively (assumes the entire
remaining budget was spent), never optimistically.

## Retry contract (CP-OP02) — what the harness does, not the adapter

Adapters do not implement their own retry logic — `run_work_order.py`'s
`--mode execute` owns a bounded retry loop (max. 3 attempts total) around
a single adapter's `execute()` calls. This is deliberate: retry-or-not is
a policy decision (is this failure technical, or did the runner tell us
something real?) that belongs at the orchestration layer, not duplicated
in every adapter.

**What counts as a retryable "technical failure"**: `execute()` raising an
exception, or returning an `ExecuteOutcome` with `result=None` (no usable
result JSON at all — a timeout is the common case). **What is never
retried**: any call that returns a real, parsed `result` — regardless of
its `finalStatus`. A runner reporting `blocked` or `failed` already told
the operator something true about the work order; silently trying again
would contradict that report exactly the same way faking a `review_ready`
would (see "What an adapter must never do," below).

**Working-tree safety**: before and after each attempt, the harness
snapshots the git state of wherever `execute()`'s subprocess actually runs
(the harness process's own current working directory at invocation time —
not this repo's root, which matters for a cross-repo work order). If the
working tree changed during a technical failure — or its state couldn't
be determined at all — the harness does **not** retry; it fails the work
order outright and asks for human intervention. This exists because
retrying a technical failure against a worktree the failed attempt
already touched risks compounding a half-finished change, not cleanly
re-trying from the same starting point.

**Cumulative budget**: for adapters with `consumes_paid_credits=True`, the
budget gate's value is a ceiling shared across every attempt in a retry
sequence, not reissued per attempt — see `ExecuteOutcome.cost_usd` above.

An adapter implementation does not need to do anything special to support
this — it just needs to raise on a genuine failure (rather than returning
a fabricated/partial `result`) and populate `cost_usd` when it can. See
`docs/background-dev-team-system-design.md` §17 for the full CP-OP02
writeup, including why a work order stays `running` throughout a retry
sequence instead of visiting some intermediate status.

## Safety requirements — non-negotiable for every adapter

1. **Declare capabilities honestly.** `info.capabilities` is not
   decorative — `check_scope_errors()`'s default implementation checks
   every declared capability (and `command_template`, if set) against the
   same blocked-action keyword list used everywhere else in this system
   (`deploy`, `secret`, `force push`, ...). An adapter that needs something
   it shouldn't have is caught here, before `prepare()` or `execute()` ever
   run.
2. **Check the ApprovalScope before touching anything.**
   `run_work_order.py` runs both the harness-level `validate_preconditions()`
   (work-order-level: scope exists, `blocked_actions` non-empty, no
   smuggled actions, ticket plan non-empty, valid status) **and** the
   chosen adapter's `check_scope_errors()`/`check_scope_warnings()` before
   `prepare()` is called. Both must pass. Neither is a substitute for the
   other — the harness check is about the work order itself, the adapter
   check is about whether *this specific adapter* is an appropriate match
   for it.
3. **Stop on scope violation — don't degrade gracefully into doing it
   anyway.** A non-empty `check_scope_errors()` aborts the run with exit
   code 1 and zero state mutated. There is no "warn and continue" path for
   a hard error, ever. (`check_scope_warnings()` is different by design —
   warnings print but don't block, because they flag ambiguity, not a
   confirmed violation.)
4. **Never assume a permission beyond what's declared.** If an adapter
   later needs a new capability (e.g. network access to call an external
   API), that capability must be added to `info.capabilities` — visibly,
   in a diff someone reviews — not quietly exercised at runtime.

None of this is execution-level sandboxing. `check_scope_errors()` is a
keyword check against free-text scope fields — a best-effort net, the same
limitation `backend/app/core/safety_rules.py`'s validator has (see
`docs/background-dev-team-system-design.md` §11). **Nothing in this
contract stops a misbehaving adapter implementation from doing something
blocked anyway once `execute()` actually runs** — that requires a real
execution sandbox/allowlist, which is future work (§9 step 3b in the
system design doc), not something this contract claims to solve.

## Claude Code, Codex, OpenClaw — current status

| Adapter | File | Status |
| --- | --- | --- |
| `manual_prompt` | `scripts/runner_adapters/manual_prompt.py` | **Implemented.** Writes a prompt for a human to paste into any LLM-driven tool by hand; reads back a human-saved `result.json`. `safety_level="manual"`, `supports_auto_execute="no"`, `consumes_paid_credits=False` (never calls a paid API itself — the human's own later session pays for whatever they paste it into). |
| `claude_code` | `scripts/runner_adapters/claude_code.py` | **Implemented, `supports_auto_execute="semi_auto"`, `consumes_paid_credits=True` (OP-ClaudeAdapter-001, budget-gated since OP-ClaudeBudgetGate-001).** Verified against the real `claude` CLI (v2.1.199), not guessed: `execute()` genuinely invokes `claude --print --output-format json` via `subprocess.run()` with an argument list (never `shell=True`), maps the work order's `allowed_actions` onto `--allowedTools`/`--disallowedTools`, and parses the embedded result JSON out of the CLI's JSON-wrapper response. "semi_auto" rather than "yes" because it depends on a one-time, out-of-adapter-control step — the workspace must already be interactively trusted by Claude Code, or every call fails (detected and reported clearly, not silently degraded). Never passes `--dangerously-skip-permissions` to work around this. Because `consumes_paid_credits=True`, `run_work_order.py` refuses to call `execute()` at all without an explicit `--max-budget-usd`/`COMMANDPILOT_CLAUDE_MAX_BUDGET_USD` — that value (or, absent one, the work order's own `approval_scope.max_cost_usd`) is what actually reaches `--max-budget-usd` on the CLI call. See `docs/background-dev-team-runbook.md`'s Fast Path §B2. |
| `codex` | `scripts/runner_adapters/codex.py` | **Placeholder**, same pattern `claude_code` had before this pass — `command_template="codex exec --prompt-file {prompt_file}"` is an unverified guess, `supports_auto_execute="semi_auto"` is provisional pending the same kind of real `--help`-plus-live-call verification `claude_code` just got. `consumes_paid_credits=True` set now on the conservative assumption that a real Codex CLI would also spend money — the budget gate will apply to it automatically once it's ever implemented for real. |
| `openclaw` | `scripts/runner_adapters/openclaw.py` | **Named slot only, `supports_auto_execute="no"`.** OpenClaw's actual capabilities have not been researched or verified — `capabilities`/`command_template` are placeholders, not claims. `consumes_paid_credits=True` set conservatively for the same reason as `codex`. Every method raises `NotImplementedError`. Do not wire this up without evaluating OpenClaw for real first. |

Use `--adapter manual_prompt` (the default) if you want zero dependencies
and a fully human-supervised loop; use `--adapter claude_code` once you've
accepted the one-time workspace-trust step and want the CLI invoked for
you. `codex`/`openclaw` exist so the *shape* of adding a real runtime is
already decided — implementing one for real means filling in
`prepare()`/`execute()`/`collect_result()` on an existing file (the way
`claude_code` just went from placeholder to real), not inventing the
interface under time pressure.

## What an adapter must never do

Regardless of runtime, capability declaration, or approval scope, no
adapter may:
- Deploy anything.
- Read, display, or log a secret (API keys, tokens, `.env` contents) —
  including the user's own `COMMANDPILOT_API_TOKEN`, which adapters never
  need direct access to (only `run_work_order.py`'s orchestration layer
  talks to the CommandPilot API).
- Send an email.
- Trigger a payment (Stripe or otherwise).
- Modify production data.
- Run a destructive git command (`reset --hard`, `force push`, `clean -f`).
- Push directly to `main`, or push/create a PR at all without that being
  an explicit, approved action in the work order's scope.
- Export user data.
- Call an external service not explicitly named in the work order's
  `allowed_actions`.

This list is the same repo-wide safety baseline as everywhere else in this
system (`frontend/lib/safetyRules.ts`, `backend/app/core/safety_rules.py`,
`scripts/runner_adapters/base.py`'s `BLOCKED_ACTION_KEYWORDS`) — an adapter
doesn't get its own, looser version of it.
