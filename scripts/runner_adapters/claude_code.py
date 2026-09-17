"""Claude Code RunnerAdapter v0 — semi-automatic execution.

Verified against the local `claude` CLI (v2.1.199) via `claude --help` plus
one minimal, cost-capped live invocation (`--max-budget-usd 0.02`) — not
guessed. Confirmed, first-hand:
- `-p/--print` genuinely runs non-interactively; a piped stdin prompt is
  accepted as the prompt (no positional argument needed).
- `--output-format json` returns a structured wrapper: a `result` field
  (the model's final text response — where our embedded work-order result
  JSON lives), plus `total_cost_usd`, `usage`, and `permission_denials`.
- `--max-budget-usd` is enforced by the CLI itself, independent of and in
  addition to ApprovalScope.max_cost_usd.
- A trivial one-line prompt still cost ~$0.05 from context/cache overhead
  alone — real invocations have a non-trivial cost floor; this is passed
  through to `--max-budget-usd` from the work order's own scope, not
  invented here.
- **Hard, verified precondition:** an untrusted workspace makes Claude Code
  print "this workspace has not been trusted" and ignore the project's own
  `permissions.allow` entries — even in `--print` mode. This must be
  accepted once, interactively, in this exact directory before automated
  runs behave as configured. This adapter detects the message and fails
  with a clear, actionable error rather than silently running with
  narrowed permissions.

This is why `supports_auto_execute="semi_auto"`, not `"yes"`: execute()
is real, not a stub, but its behavior depends on a one-time manual step
outside this adapter's control, and — deliberately — this adapter never
passes `--dangerously-skip-permissions`/`--permission-mode
bypassPermissions` to paper over that. Doing so would let Claude Code run
without checking file/tool permissions at all, which defeats the entire
ApprovalScope model this system is built on. See
docs/runner-adapter-contract.md.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .base import (
    AdapterInfo,
    ExecuteOutcome,
    RunnerAdapter,
    RESULT_JSON_SCHEMA,
    build_result_example,
    build_runner_prompt,
    extract_json_result,
    parse_and_validate_result,
)

# Tools always safe to grant regardless of scope — pure reads.
_BASE_ALLOWED_TOOLS = ["Read", "Glob", "Grep"]

# Deny these unconditionally: they map directly to this system's repo-wide
# blocked actions (destructive git, direct main pushes, external network
# calls this adapter has no approval-scope concept for yet). blocked_actions
# always wins over anything allowed_actions says — see check_scope_errors()
# in base.py for the declaration-time half of this; this is the
# execution-time half, specific to this adapter's own runtime.
_ALWAYS_DISALLOWED_TOOLS = [
    "Bash(git push*)",
    "Bash(git reset --hard*)",
    "Bash(git clean*)",
    "Bash(git commit --amend*)",
    "WebFetch",
    "WebSearch",
]


def _map_allowed_tools(scope: dict) -> list[str]:
    """Best-effort mapping from the work order's free-text allowed_actions
    onto Claude Code's --allowedTools vocabulary. Only recognizes the
    Background Dev Team default slugs (see
    frontend/components/operator/CreateWorkOrderForm.tsx) — anything else
    falls back to Claude Code's own default permission handling (which
    prompts/denies rather than silently allowing, since there's no TTY to
    prompt against in --print mode). The `Bash(...)` pattern syntax below
    is inferred from the one example in `claude --help` ("Bash(git *)"),
    not exhaustively verified beyond that.
    """
    allowed = [a.lower() for a in scope.get("allowed_actions", [])]
    tools = list(_BASE_ALLOWED_TOOLS)
    if any("code_edit" in a or "edit" in a or "code" in a for a in allowed):
        tools += ["Edit", "Write"]
    if any("test" in a or "lint" in a or "typecheck" in a for a in allowed):
        tools += ["Bash(npm run *)", "Bash(npx tsc*)", "Bash(python -m pytest*)", "Bash(python -m py_compile*)"]
    if any("local_artifact" in a for a in allowed):
        tools += ["Write"]
    return sorted(set(tools))


def _resolve_claude_executable() -> str:
    """Resolves the real path to the `claude` executable via shutil.which(),
    which is PATHEXT-aware on Windows (tries .cmd/.ps1/.exe in PATHEXT
    order), rather than passing the bare string "claude" to
    subprocess.run(..., shell=False).

    This matters because npm installs CLI tools on Windows as a shim: a
    plain extensionless `claude` file (a POSIX shell script, for Git
    Bash/WSL) sitting next to `claude.cmd`/`claude.ps1` (the actual
    Windows-invocable wrappers). subprocess.run() with shell=False calls
    CreateProcess directly and does NOT do the PATHEXT-based extension
    search cmd.exe/PowerShell do when you type a bare command name — so it
    can resolve to the wrong file (or fail unpredictably) on Windows.
    shutil.which() replicates the shell's search behavior without needing
    shell=True, so this stays consistent with "never shell=True" while
    actually working on Windows. This bug produced a real, reproducible
    silent hang during verification: the adapter appeared to do nothing
    with no output ever written, because the wrong artifact was invoked.
    """
    resolved = shutil.which("claude")
    if not resolved:
        raise FileNotFoundError(
            "Could not find a 'claude' executable on PATH. Is Claude Code installed and on PATH? "
            "Try 'claude --version' in this same terminal to confirm."
        )
    return resolved


def _build_cli_args(scope: dict, claude_path: str, budget_override: float | None = None) -> list[str]:
    args = [
        claude_path, "--print", "--output-format", "json",
        "--allowedTools", " ".join(_map_allowed_tools(scope)),
        "--disallowedTools", " ".join(_ALWAYS_DISALLOWED_TOOLS),
    ]
    # budget_override is run_work_order.py's harness-level gate value
    # (--max-budget-usd / COMMANDPILOT_CLAUDE_MAX_BUDGET_USD) — required
    # before execute() is ever called (see cmd_execute()'s budget gate).
    # It takes precedence over the work order's own, DB-persisted
    # approval_scope.max_cost_usd (which can be unset — that gap is exactly
    # what caused a real, uncapped $1.40 charge during verification of this
    # adapter). Whichever is smaller effectively wins, since the CLI's own
    # --max-budget-usd is a hard ceiling regardless of which value produced it.
    effective_cost = budget_override if budget_override is not None else scope.get("max_cost_usd")
    if effective_cost:
        args += ["--max-budget-usd", str(effective_cost)]
    return args


class ClaudeCodeAdapter(RunnerAdapter):
    info = AdapterInfo(
        name="claude_code",
        capabilities=["read_repo", "write_local_files", "execute_shell", "modify_files"],
        safety_level="supervised",
        supports_live_events=False,  # would require Claude Code to call back into CommandPilot mid-session
        supports_auto_execute="semi_auto",
        consumes_paid_credits=True,  # execute() calls the real, paid claude CLI
        command_template="claude --print --output-format json < {prompt_file}",
    )

    def prepare(self, order: dict, session_path: Path) -> Path:
        prompt_text = build_runner_prompt(order)
        prompt_path = session_path / "prompt.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        (session_path / "result.schema.json").write_text(RESULT_JSON_SCHEMA, encoding="utf-8")
        (session_path / "result.example.json").write_text(
            json.dumps(build_result_example(order), indent=2, ensure_ascii=False), encoding="utf-8"
        )

        scope = order.get("approval_scope") or {}
        claude_path = _resolve_claude_executable()
        args = _build_cli_args(scope, claude_path)
        (session_path / "claude_command.txt").write_text(
            "# Command this adapter runs via subprocess (argument list, no shell=True):\n"
            + " ".join(f'"{a}"' if " " in a else a for a in args) + "  (prompt piped via stdin)\n\n"
            "# PowerShell equivalent if you want to run it yourself instead:\n"
            f"Get-Content \"{prompt_path}\" -Raw | " + " ".join(f'"{a}"' if " " in a else a for a in args) + "\n",
            encoding="utf-8",
        )
        return prompt_path

    def execute(
        self,
        order: dict,
        session_path: Path,
        runner_command: str | None,
        max_budget_usd: float | None = None,
    ) -> ExecuteOutcome:
        prompt_path = session_path / "prompt.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"prompt.md not found at {prompt_path} — run --mode prompt-file first.")

        scope = order.get("approval_scope") or {}
        claude_path = _resolve_claude_executable()
        args = _build_cli_args(scope, claude_path, budget_override=max_budget_usd)
        prompt_text = prompt_path.read_text(encoding="utf-8")

        # Minimal, explicit env for the child process — never pass
        # CommandPilot's own API token through to the runner's runtime; it
        # has no legitimate use for it and shouldn't be able to log it.
        child_env = {k: v for k, v in os.environ.items() if k != "COMMANDPILOT_API_TOKEN"}

        time_limit_s = (order.get("time_limit_minutes") or 90) * 60
        output_log_path = session_path / "execute_output.log"

        # Popen + a communicate()-with-timeout polling loop instead of a single
        # blocking subprocess.run() — a real work order can legitimately take
        # minutes (multi-turn tool use), and a silent terminal for that long
        # is indistinguishable from a genuine hang. Printing progress here is
        # purely local terminal feedback; it does not change what's sent to
        # Claude Code and adds no new capability — see collect_result()'s
        # docstring/module docs for what "semi_auto" does and doesn't cover.
        # Python's docs explicitly support calling communicate(timeout=...)
        # repeatedly after a TimeoutExpired — buffered output isn't lost
        # between calls.
        proc = subprocess.Popen(
            args,  # argument list — never shell=True, no shell-metacharacter risk from prompt content
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env,
        )
        start = time.monotonic()
        poll_interval_s = 2
        progress_every_s = 15
        next_progress_at = progress_every_s
        stdout = stderr = ""
        returncode: int | None = None
        try:
            proc.stdin.write(prompt_text)
            proc.stdin.close()
            while True:
                try:
                    stdout, stderr = proc.communicate(timeout=poll_interval_s)
                    returncode = proc.returncode
                    break
                except subprocess.TimeoutExpired:
                    elapsed = time.monotonic() - start
                    if elapsed >= time_limit_s:
                        proc.kill()
                        stdout, stderr = proc.communicate()
                        returncode = 124
                        output_log_path.write_text(
                            f"TIMEOUT nach {order.get('time_limit_minutes', 90)} Minuten.\n\n"
                            f"stdout bis dahin:\n{stdout}\n\nstderr bis dahin:\n{stderr}",
                            encoding="utf-8",
                        )
                        return ExecuteOutcome(exit_code=returncode, output_log_path=output_log_path, result=None)
                    if elapsed >= next_progress_at:
                        print(f"  ... Claude Code arbeitet noch ({int(elapsed)}s vergangen, Limit {time_limit_s}s)")
                        next_progress_at += progress_every_s
        finally:
            # Popen doesn't auto-close stdin/stdout/stderr pipe handles the
            # way subprocess.run's context management did — close explicitly
            # so a crash mid-loop (or the timeout-kill path above, which
            # returns early) never leaks file descriptors.
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass

        combined = stdout + (("\n--- stderr ---\n" + stderr) if stderr else "")
        output_log_path.write_text(combined, encoding="utf-8")

        result_json: dict | None = None
        cost_usd: float | None = None
        try:
            wrapper = json.loads(stdout)
        except json.JSONDecodeError:
            wrapper = None

        if wrapper is None:
            # stdout wasn't valid JSON at all — this is how a genuine
            # CLI-level rejection (e.g. an untrusted workspace) actually
            # manifests: Claude Code prints a plain-text warning instead of
            # the --output-format json wrapper, so json.loads(stdout) fails.
            # ONLY check for the trust phrase here, in the unparseable case —
            # a real run confirmed this the hard way: once stdout genuinely
            # parses as our JSON wrapper, its own `result` text can
            # legitimately quote/describe this exact phrase (e.g. reporting
            # on a PRIOR trust failure it found in run.log) without THIS run
            # having failed for that reason. An earlier version of this
            # check scanned the entire combined output regardless, which
            # threw away a real, successful, $1.40 / 24-turn run because its
            # own analysis text happened to mention "has not been trusted."
            if "has not been trusted" in combined:
                raise RuntimeError(
                    "Claude Code meldet: dieser Workspace ist nicht 'trusted'. Öffne einmalig `claude` "
                    "interaktiv in diesem Repo-Verzeichnis und akzeptiere den Trust-Dialog — erst danach "
                    "gelten die Projekt-Permissions auch non-interactive. Dieser Adapter setzt bewusst "
                    "NICHT --dangerously-skip-permissions, um das zu umgehen (siehe Moduldoku). "
                    f"Rohausgabe: {output_log_path}."
                )
            # Not JSON, and not a recognized trust error either — fall back
            # to scanning raw stdout directly in case a result JSON is
            # embedded in otherwise-unstructured output.
            result_json = extract_json_result(stdout)
        else:
            denials = wrapper.get("permission_denials")
            if denials:
                (session_path / "permission_denials.json").write_text(
                    json.dumps(denials, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            result_text = wrapper.get("result", "")
            if isinstance(result_text, str):
                result_json = extract_json_result(result_text)
            cost_usd = wrapper.get("total_cost_usd")

        return ExecuteOutcome(exit_code=returncode, output_log_path=output_log_path, result=result_json, cost_usd=cost_usd)

    def collect_result(self, session_path: Path, result_file: str | None) -> dict:
        path_arg = result_file or str(session_path / "result.json")
        path = Path(path_arg)
        if not path.exists():
            raise FileNotFoundError(
                f"result file not found: {path} (default expected: {session_path / 'result.json'} — "
                f"or pass --result-file). If --mode execute --adapter claude_code ran, check "
                f"{session_path / 'execute_output.log'} for what actually happened, and "
                f"{session_path / 'permission_denials.json'} (if present) for anything Claude Code refused."
            )
        return parse_and_validate_result(path.read_text(encoding="utf-8"), str(path))
