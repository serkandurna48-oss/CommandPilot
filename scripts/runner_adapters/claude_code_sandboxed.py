"""Claude Code Sandboxed RunnerAdapter — real, container-isolated autonomy.

`claude_code` (claude_code.py) is deliberately `supports_auto_execute=
"semi_auto"` and never passes `--dangerously-skip-permissions`: without
technical isolation, that flag would let Claude Code run without checking
file/tool permissions at all, defeating the entire ApprovalScope model this
system is built on. This adapter is a SEPARATE, additional mode that earns
`supports_auto_execute="yes"` honestly, by building the technical isolation
that makes `--dangerously-skip-permissions` actually safe, rather than by
asserting it:

1. **Disposable, self-contained clone, never the real working tree.** Before
   every `claude` invocation, `_create_sandbox_worktree()` creates a
   throwaway local clone (`git clone --local`) of the target repo's current
   HEAD. The container only ever sees this clone, bind-mounted at
   `/workspace`; the user's real repo (wherever `run_work_order.py` was
   invoked from) is never touched, never mounted, never in the container's
   reach at all. `_remove_sandbox_worktree()` deletes it in a `finally` on
   every exit path (success, technical failure, timeout, interrupt).

   **Deliberately a `git clone --local`, not a `git worktree add`** — this
   was tried first and verified broken by a real live test: a linked
   worktree's `.git` is a FILE containing an absolute host path
   (`gitdir: C:/Users/.../.git/worktrees/<name>`) back to the main repo's
   object store. That path is meaningless inside the Linux container (no
   `C:/` drive), so every `git` command run BY THE AGENT inside the
   container (status, diff, log — anything a coding agent might reasonably
   run to orient itself) fails with "not a git repository," even though
   the files themselves are visible and editable. A `--local` clone has a
   real, standalone `.git` DIRECTORY (hardlinked to the source's objects
   when on the same filesystem — fast, not a full copy) with no host-path
   dependency at all, so it works identically whether mounted into a
   container or used directly. `_extract_diff()` (point 3 below) still
   works exactly the same either way, since it always ran on the HOST after
   the container exits — this fix was specifically for git usability INSIDE
   the container, not for the extraction step.

   **Known, verified-live limitation (CRLF):** `_extract_diff()`'s own diff
   is confirmed clean — it always runs with the HOST's git against the
   HOST's checkout, so it never sees this. But if the agent itself runs
   `git status`/`git diff` INSIDE the container (plausible, given it has
   `execute_shell`), it will see every tracked file reported as modified
   with symmetric line counts — this is real CRLF/LF normalization drift
   (the clone's working tree was checked out by Windows git with its
   `core.autocrlf` behavior; the container's Linux git has no such
   conversion configured, so re-hashing the same CRLF bytes doesn't match
   the LF-normalized blobs already in the object store). Harmless to the
   actual deliverable (the extracted diff), but potentially confusing/
   noisy for the agent's own in-container git usage. Not fixed this pass —
   flagged here and in CLAUDE.md's Bekannte Risiken rather than shipped
   silently.

2. **`--allowedTools`/`--disallowedTools` still apply, belt-and-suspenders.**
   Exactly the same `_map_allowed_tools()`/`_ALWAYS_DISALLOWED_TOOLS` this
   module imports from claude_code.py are still passed to the containerized
   `claude` process — `--dangerously-skip-permissions` only removes the
   interactive permission PROMPT (which has no TTY to answer anyway in
   `--print` mode); the tool allow/deny list still narrows what's attempted.

3. **Results land as a reviewable diff, never a silent host mutation.**
   After the container exits, `_extract_diff()` runs `git add -A && git
   diff --cached` INSIDE THE DISPOSABLE WORKTREE, on the host (the
   container is already gone by then) — this diff is attached as an
   `artifacts` entry (`type: "diff"`) on the returned result, flowing
   through the exact same `import_result()` write-back path every other
   adapter's artifacts use. Applying that diff to the real repo is a
   separate, human-triggered action, deliberately not built here.

4. **check_scope_errors()/check_scope_warnings()/the budget gate still run
   exactly where they do for every other adapter** (run_work_order.py's
   cmd_prompt_file()/cmd_execute(), before this adapter's execute()/
   execute_step() is ever called) — the container is defense-in-depth ON
   TOP of the existing ApprovalScope model, not a replacement for it.

**Credential**: the host's own `~/.claude` directory is bind-mounted
read-only into the container (`/root/.claude`) — the SAME already-trusted
local session `claude_code` uses directly on the host, not a separately
handled/copied secret. (Alternatives considered: an env-var-forwarded
token — visible via `docker inspect`/process listing inside the container;
a host-side relay proxy — most secure, but real extra engineering not
built this pass. This tradeoff was an explicit, flagged decision, not a
default.)

**Network**: v1 ships with the container's standard bridge network, no
egress lockdown. `claude` genuinely needs to reach the Anthropic API, so
"no network at all" isn't viable — the actual blast-radius containment
here is the disposable filesystem (worktree + container), NOT a network
guarantee. A fully egress-locked network (only the Anthropic API host
reachable) is a stronger but real additional engineering lift, deliberately
deferred — this was also an explicit, flagged decision.

**Container image**: `scripts/sandbox/Dockerfile`, fixed and checked into
the repo — built manually/versioned, never pulled from a registry at run
time. See that file for exact contents.

Never used without `run_work_order.py`'s existing budget gate
(`consumes_paid_credits=True` here, same as `claude_code`) — no default
budget is ever assumed, matching every other paid adapter in this repo.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from .base import (
    AdapterInfo,
    ExecuteOutcome,
    ProgressReporter,
    RunnerAdapter,
    RESULT_JSON_SCHEMA,
    StepExecuteOutcome,
    build_result_example,
    build_runner_prompt,
    build_step_prompt,
    parse_and_validate_result,
)
from .claude_code import _ALWAYS_DISALLOWED_TOOLS, _map_allowed_tools, _run_claude_subprocess

# Fixed, checked-in image (scripts/sandbox/Dockerfile) — never pulled from a
# registry at run time, so what runs is always exactly what's in this repo.
# Rebuild locally with: docker build -t commandpilot-sandbox:latest scripts/sandbox
_SANDBOX_IMAGE = "commandpilot-sandbox:latest"


def _resolve_docker_executable() -> str:
    resolved = shutil.which("docker")
    if not resolved:
        raise FileNotFoundError(
            "Could not find a 'docker' executable on PATH. Is Docker Desktop installed and running? "
            "Try 'docker --version' in this same terminal to confirm."
        )
    return resolved


def _create_sandbox_worktree(session_path: Path, repo_root: Path) -> Path:
    """Creates the disposable, self-contained clone this whole adapter's
    safety argument rests on — see module docstring point 1 for why this is
    a `git clone --local`, not a `git worktree add` (the latter was tried
    first and verified broken by a real live test: a linked worktree's
    `.git` file points back to the host repo via an absolute host path that
    doesn't resolve inside the container)."""
    worktree_path = session_path / "sandbox-worktree"
    if worktree_path.exists():
        _remove_sandbox_worktree(worktree_path)
    subprocess.run(
        ["git", "clone", "--local", str(repo_root), str(worktree_path)],
        check=True, capture_output=True, text=True,
    )
    return worktree_path


def _clear_readonly_and_retry(func, path, exc) -> None:
    """`shutil.rmtree`'s onexc hook: git marks loose object/pack files
    read-only on Windows, and plain `ignore_errors=True` silently gives up
    on the FIRST such file — verified live: it left the clone's `.git`
    directory (and everything under it) behind entirely, exactly the
    orphaned-sandbox-directory nuisance the module docstring warns against.
    Clearing the read-only bit and retrying the failed operation actually
    removes the tree instead of silently no-op'ing on it."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_sandbox_worktree(worktree_path: Path) -> None:
    """Best-effort cleanup, called from a `finally` on every exit path —
    never raises, matching every other best-effort cleanup in this codebase
    (e.g. claude_code.py's pipe-closing finally block). A plain directory
    delete: unlike a linked `git worktree`, a `--local` clone isn't tracked
    in repo_root's worktree list at all, so there's nothing to `git
    worktree remove`/prune on the main repo's side."""
    try:
        shutil.rmtree(worktree_path, onexc=_clear_readonly_and_retry)
    except Exception:
        pass


def _extract_diff(worktree_path: Path) -> str | None:
    """Stages everything (so new/untracked files are captured, not just
    modifications to tracked ones) and diffs against HEAD — on the HOST,
    after the container has already exited. This is the actual mechanism
    behind "reviewable artifact, never silently applied": nothing here
    touches repo_root, only the disposable worktree. Returns None for a
    genuinely empty diff (a read-only/analysis-only step)."""
    subprocess.run(["git", "add", "-A"], cwd=worktree_path, capture_output=True, text=True)
    result = subprocess.run(["git", "diff", "--cached"], cwd=worktree_path, capture_output=True, text=True)
    return result.stdout if result.stdout.strip() else None


def _docker_run_args(docker_path: str, worktree_path: Path, scope: dict, budget_override: float | None) -> list[str]:
    args = [
        docker_path, "run", "--rm", "-i",  # -i: keep stdin open so the piped prompt actually reaches `claude` inside the container
        "-v", f"{worktree_path}:/workspace",
        "-w", "/workspace",
        "-v", f"{Path.home() / '.claude'}:/root/.claude:ro",
        "--network", "bridge",
        _SANDBOX_IMAGE,
        "claude", "--print", "--output-format", "json",
        "--allowedTools", " ".join(_map_allowed_tools(scope)),
        "--disallowedTools", " ".join(_ALWAYS_DISALLOWED_TOOLS),
        "--dangerously-skip-permissions",
    ]
    # Same budget-precedence rule as claude_code.py's _build_cli_args() —
    # the harness-level gate value wins over the work order's own,
    # DB-persisted approval_scope.max_cost_usd.
    effective_cost = budget_override if budget_override is not None else scope.get("max_cost_usd")
    if effective_cost:
        args += ["--max-budget-usd", str(effective_cost)]
    return args


def _run_sandboxed_claude(
    order: dict,
    prompt_text: str,
    session_path: Path,
    max_budget_usd: float | None,
    progress: ProgressReporter | None,
    output_log_path: Path,
    diff_artifact_title: str,
) -> tuple[int, dict | None, float | None, bool]:
    """Shared by execute() and execute_step(): resolves docker, creates the
    disposable worktree, runs `claude` inside a container against it, and —
    critically — ALWAYS tears the worktree down again (`finally`), whether
    the run succeeded, technically failed, timed out, or was interrupted.
    Reuses _run_claude_subprocess() from claude_code.py unchanged: the
    subprocess lifecycle (timeout, interrupt, progress reporting, JSON-
    wrapper parsing, the untrusted-workspace check) is identical whether
    the underlying command is a bare `claude` call or `docker run ...
    claude ...` — only the argv differs.

    Returns the same (exit_code, result_json, cost_usd, interrupted) shape
    _run_claude_subprocess() does. If a result was produced, its
    `artifacts` list gets the extracted diff appended (see module docstring
    point 3) — merged here, not by the caller, so execute()/execute_step()
    never have to remember to do it.
    """
    scope = order.get("approval_scope") or {}
    docker_path = _resolve_docker_executable()
    repo_root = Path.cwd()  # same convention run_work_order.py's _target_worktree() already establishes
    worktree_path = _create_sandbox_worktree(session_path, repo_root)
    time_limit_minutes = order.get("time_limit_minutes") or 90

    try:
        args = _docker_run_args(docker_path, worktree_path, scope, max_budget_usd)
        returncode, result_json, cost_usd, interrupted = _run_claude_subprocess(
            args, prompt_text, time_limit_minutes * 60, time_limit_minutes,
            output_log_path, session_path, progress,
        )
        if result_json is not None:
            diff_text = _extract_diff(worktree_path)
            if diff_text:
                (session_path / f"{output_log_path.stem}.diff").write_text(diff_text, encoding="utf-8")
                result_json.setdefault("artifacts", []).append(
                    {"type": "diff", "title": diff_artifact_title, "content": diff_text}
                )
        return returncode, result_json, cost_usd, interrupted
    finally:
        _remove_sandbox_worktree(worktree_path)


class ClaudeCodeSandboxedAdapter(RunnerAdapter):
    info = AdapterInfo(
        name="claude_code_sandboxed",
        capabilities=["read_repo", "write_local_files", "execute_shell", "modify_files"],
        safety_level="sandboxed",
        supports_live_events=True,
        supports_auto_execute="yes",
        consumes_paid_credits=True,  # same paid claude CLI, just containerized
        command_template=(
            "docker run --rm -i -v <worktree>:/workspace -v ~/.claude:/root/.claude:ro "
            f"{_SANDBOX_IMAGE} claude --print --output-format json --dangerously-skip-permissions"
        ),
        supports_step_execution=True,
    )

    def prepare(self, order: dict, session_path: Path) -> Path:
        prompt_text = build_runner_prompt(order)
        prompt_path = session_path / "prompt.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        (session_path / "result.schema.json").write_text(RESULT_JSON_SCHEMA, encoding="utf-8")
        (session_path / "result.example.json").write_text(
            json.dumps(build_result_example(order), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return prompt_path

    def execute(
        self,
        order: dict,
        session_path: Path,
        runner_command: str | None,
        max_budget_usd: float | None = None,
        progress: ProgressReporter | None = None,
    ) -> ExecuteOutcome:
        prompt_path = session_path / "prompt.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"prompt.md not found at {prompt_path} — run --mode prompt-file first.")
        prompt_text = prompt_path.read_text(encoding="utf-8")
        output_log_path = session_path / "execute_output_sandbox.log"

        returncode, result_json, cost_usd, interrupted = _run_sandboxed_claude(
            order, prompt_text, session_path, max_budget_usd, progress, output_log_path,
            diff_artifact_title="Sandbox-Änderungen",
        )
        return ExecuteOutcome(
            exit_code=returncode, output_log_path=output_log_path,
            result=result_json, cost_usd=cost_usd, interrupted=interrupted,
        )

    def execute_step(
        self,
        order: dict,
        step: dict,
        prior_steps: list[dict],
        session_path: Path,
        max_budget_usd: float | None = None,
        progress: ProgressReporter | None = None,
    ) -> StepExecuteOutcome:
        prompt_text = build_step_prompt(order, step, prior_steps)
        (session_path / f"step_{step['id']}_prompt.md").write_text(prompt_text, encoding="utf-8")
        output_log_path = session_path / f"execute_output_sandbox_step_{step['id']}.log"

        returncode, result_json, cost_usd, interrupted = _run_sandboxed_claude(
            order, prompt_text, session_path, max_budget_usd, progress, output_log_path,
            diff_artifact_title=f"Sandbox-Änderungen (Step: {step['title']})",
        )
        return StepExecuteOutcome(
            exit_code=returncode, output_log_path=output_log_path,
            step_result=result_json, cost_usd=cost_usd, interrupted=interrupted,
        )

    def collect_result(self, session_path: Path, result_file: str | None) -> dict:
        path_arg = result_file or str(session_path / "result.json")
        path = Path(path_arg)
        if not path.exists():
            raise FileNotFoundError(
                f"result file not found: {path} (default expected: {session_path / 'result.json'} — "
                f"or pass --result-file). If --mode execute --adapter claude_code_sandboxed ran, check "
                f"{session_path / 'execute_output_sandbox.log'} for what actually happened."
            )
        return parse_and_validate_result(path.read_text(encoding="utf-8"), str(path))
