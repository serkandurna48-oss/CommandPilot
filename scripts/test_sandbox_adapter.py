#!/usr/bin/env python3
"""Tests for scripts/runner_adapters/claude_code_sandboxed.py.

A real Docker container can't realistically run inside this test suite —
everything Docker/git-subprocess-related is mocked (same spirit as
claude_code.py's tests would mock the `claude` CLI subprocess). What this
DOES verify without Docker: worktree create/cleanup happens on every exit
path (including when the "claude" call raises), the diff-extraction/
artifact-merge logic, and that the docker argv is built correctly
(--dangerously-skip-permissions present, --allowedTools/--disallowedTools
still passed, credential mount present, no accidental bind-mount of the
real repo).

A real, live Docker verification pass (build the image, run a genuine
work order through it) is still required before calling this "verified"
end-to-end — see docs/manual-e2e-checklist.md.

Run:
    python scripts/test_sandbox_adapter.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runner_adapters.claude_code_sandboxed as sandboxed  # noqa: E402


def _order():
    return {
        "id": "wo-1",
        "title": "Test Order",
        "goal": "Do the thing",
        "repo": "commandpilot",
        "time_limit_minutes": 90,
        "acceptance_criteria": [],
        "missing_context": [],
        "approval_scope": {
            "allowed_actions": ["code_edit_within_scope"],
            "requires_approval": [],
            "blocked_actions": ["deploy"],
            "max_runtime_minutes": 90,
        },
        "steps": [{"id": "s1", "order_index": 0, "title": "Step 1", "assigned_role": "coder",
                    "description": "d1", "acceptance_criteria": []}],
    }


class DockerArgsTests(unittest.TestCase):
    def test_docker_run_args_includes_skip_permissions_and_tool_lists(self):
        args = sandboxed._docker_run_args(
            "docker", Path("/tmp/worktree"), {"allowed_actions": ["code_edit_within_scope"]}, None,
        )
        self.assertIn("--dangerously-skip-permissions", args)
        self.assertIn("--allowedTools", args)
        self.assertIn("--disallowedTools", args)
        self.assertIn(sandboxed._SANDBOX_IMAGE, args)
        self.assertIn("-i", args)  # stdin must stay open for the piped prompt

    def test_docker_run_args_mounts_worktree_not_real_repo(self):
        args = sandboxed._docker_run_args("docker", Path("/tmp/some-worktree"), {}, None)
        mounts = [a for a in args if str(Path("/tmp/some-worktree")) in a]
        self.assertTrue(mounts, "expected the worktree path to appear in a -v mount argument")
        self.assertIn("/workspace", " ".join(args))

    def test_docker_run_args_mounts_credential_readonly(self):
        args = sandboxed._docker_run_args("docker", Path("/tmp/worktree"), {}, None)
        cred_mounts = [a for a in args if ".claude" in a and a.endswith(":ro")]
        self.assertTrue(cred_mounts, "expected a read-only ~/.claude mount")

    def test_docker_run_args_budget_override_wins_over_scope(self):
        args = sandboxed._docker_run_args("docker", Path("/tmp/worktree"), {"max_cost_usd": 5.0}, 0.20)
        idx = args.index("--max-budget-usd")
        self.assertEqual(args[idx + 1], "0.2")

    def test_docker_run_args_falls_back_to_scope_cost_when_no_override(self):
        args = sandboxed._docker_run_args("docker", Path("/tmp/worktree"), {"max_cost_usd": 5.0}, None)
        idx = args.index("--max-budget-usd")
        self.assertEqual(args[idx + 1], "5.0")


class WorktreeLifecycleTests(unittest.TestCase):
    def test_create_sandbox_worktree_invokes_git_clone_local_not_worktree_add(self):
        # Deliberately a `git clone --local`, not `git worktree add` — the
        # latter was tried first and verified broken by a real live Docker
        # test: a linked worktree's `.git` file points back to the host
        # repo via an absolute host path that a Linux container can't
        # resolve, so `git` commands inside the container fail even though
        # the files themselves are visible.
        with patch.object(sandboxed.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with tempfile.TemporaryDirectory() as tmp:
                session_path = Path(tmp)
                repo_root = Path("/repo")
                result = sandboxed._create_sandbox_worktree(session_path, repo_root)

        self.assertEqual(result, session_path / "sandbox-worktree")
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[0:3], ["git", "clone", "--local"])
        self.assertIn(str(repo_root), cmd)
        self.assertIn(str(session_path / "sandbox-worktree"), cmd)

    def test_remove_sandbox_worktree_never_raises_even_on_error(self):
        with patch.object(sandboxed.shutil, "rmtree", side_effect=OSError("boom")):
            # Must not raise — this is a best-effort cleanup called from a
            # `finally`, matching claude_code.py's own pipe-closing pattern.
            sandboxed._remove_sandbox_worktree(Path("/tmp/some-worktree"))

    def test_extract_diff_returns_none_for_empty_diff(self):
        with patch.object(sandboxed.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            result = sandboxed._extract_diff(Path("/tmp/worktree"))
        self.assertIsNone(result)

    def test_extract_diff_returns_text_for_real_diff(self):
        diff_text = "diff --git a/foo.py b/foo.py\n+added line\n"
        with patch.object(sandboxed.subprocess, "run") as mock_run:
            mock_run.side_effect = [
                MagicMock(),  # git add -A
                MagicMock(stdout=diff_text),  # git diff --cached
            ]
            result = sandboxed._extract_diff(Path("/tmp/worktree"))
        self.assertEqual(result, diff_text)


class ExecuteFlowTests(unittest.TestCase):
    """Verifies execute()/execute_step() wire the pieces together correctly
    — worktree lifecycle, diff-into-artifacts merge, and that cleanup runs
    even when the underlying subprocess call raises."""

    def test_execute_merges_diff_into_result_artifacts(self):
        order = _order()
        result_json = {"workOrderId": "wo-1", "finalStatus": "review_ready", "steps": [], "activityLogs": [], "artifacts": []}
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            (session_path / "prompt.md").write_text("prompt text", encoding="utf-8")
            with patch.object(sandboxed, "_resolve_docker_executable", return_value="docker"), \
                 patch.object(sandboxed, "_create_sandbox_worktree", return_value=session_path / "sandbox-worktree") as create_wt, \
                 patch.object(sandboxed, "_remove_sandbox_worktree") as remove_wt, \
                 patch.object(sandboxed, "_run_claude_subprocess", return_value=(0, result_json, 0.05, False)), \
                 patch.object(sandboxed, "_extract_diff", return_value="diff --git a/x b/x\n+y\n"):
                adapter = sandboxed.ClaudeCodeSandboxedAdapter()
                outcome = adapter.execute(order, session_path, None, max_budget_usd=0.5, progress=None)

        create_wt.assert_called_once()
        remove_wt.assert_called_once()  # cleanup happened
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.cost_usd, 0.05)
        self.assertFalse(outcome.interrupted)
        artifacts = outcome.result["artifacts"]
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["type"], "diff")
        self.assertIn("diff --git", artifacts[0]["content"])

    def test_execute_step_uses_step_scoped_prompt_and_labels_diff_with_step_title(self):
        order = _order()
        step = order["steps"][0]
        result_json = {"workOrderId": "wo-1", "steps": [{"id": "s1", "status": "completed"}], "activityLogs": [], "artifacts": []}
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            with patch.object(sandboxed, "_resolve_docker_executable", return_value="docker"), \
                 patch.object(sandboxed, "_create_sandbox_worktree", return_value=session_path / "sandbox-worktree"), \
                 patch.object(sandboxed, "_remove_sandbox_worktree"), \
                 patch.object(sandboxed, "_run_claude_subprocess", return_value=(0, result_json, None, False)) as mock_run, \
                 patch.object(sandboxed, "_extract_diff", return_value="diff --git a/y b/y\n+z\n"):
                adapter = sandboxed.ClaudeCodeSandboxedAdapter()
                outcome = adapter.execute_step(order, step, [], session_path, max_budget_usd=0.2, progress=None)

        # The prompt actually sent came from build_step_prompt(), not the
        # whole-order build_runner_prompt() — verify it mentions the step,
        # not the full ticketplan section header.
        sent_prompt = mock_run.call_args.args[1]
        self.assertIn("Step 1", sent_prompt)
        self.assertNotIn("## Ticketplan", sent_prompt)

        self.assertIn("Step 1", outcome.step_result["artifacts"][0]["title"])
        self.assertEqual(outcome.step_result["steps"][0]["id"], "s1")

    def test_worktree_is_cleaned_up_even_when_claude_call_raises(self):
        order = _order()
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            (session_path / "prompt.md").write_text("prompt text", encoding="utf-8")
            with patch.object(sandboxed, "_resolve_docker_executable", return_value="docker"), \
                 patch.object(sandboxed, "_create_sandbox_worktree", return_value=session_path / "sandbox-worktree"), \
                 patch.object(sandboxed, "_remove_sandbox_worktree") as remove_wt, \
                 patch.object(sandboxed, "_run_claude_subprocess", side_effect=RuntimeError("untrusted workspace")):
                adapter = sandboxed.ClaudeCodeSandboxedAdapter()
                with self.assertRaises(RuntimeError):
                    adapter.execute(order, session_path, None, max_budget_usd=0.2, progress=None)

        remove_wt.assert_called_once()  # cleanup still ran despite the exception

    def test_execute_produces_no_artifact_when_diff_is_empty(self):
        order = _order()
        result_json = {"workOrderId": "wo-1", "finalStatus": "review_ready", "steps": [], "activityLogs": [], "artifacts": []}
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp)
            (session_path / "prompt.md").write_text("prompt text", encoding="utf-8")
            with patch.object(sandboxed, "_resolve_docker_executable", return_value="docker"), \
                 patch.object(sandboxed, "_create_sandbox_worktree", return_value=session_path / "sandbox-worktree"), \
                 patch.object(sandboxed, "_remove_sandbox_worktree"), \
                 patch.object(sandboxed, "_run_claude_subprocess", return_value=(0, result_json, None, False)), \
                 patch.object(sandboxed, "_extract_diff", return_value=None):  # read-only/analysis-only step
                adapter = sandboxed.ClaudeCodeSandboxedAdapter()
                outcome = adapter.execute(order, session_path, None, max_budget_usd=0.2, progress=None)

        self.assertEqual(outcome.result["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
