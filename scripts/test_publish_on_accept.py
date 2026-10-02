#!/usr/bin/env python3
"""Tests for scripts/run_work_order_daemon.py's Publish-on-Accept feature
(K3): an accepted work order's reviewPackage.files_changed becomes a real
branch + PR, via local git + `gh` — merge always stays a human decision.

Two styles, deliberately:
- `PublishWorkOrderGitIntegrationTests` runs REAL git against a throwaway
  temp repo (with a local bare "origin" remote so `git push` succeeds
  without network/GitHub) — only `_run_gh()` (the `gh` CLI call) and
  `call_api()` (the backend) are mocked. This is the one place a fake git
  could hide a real bug (e.g. staging the wrong files, losing unrelated
  uncommitted work, or not returning to the original branch).
- Everything else (idempotency, the env-var gate, non-git error paths)
  mocks `_run_git`/`_run_gh` directly — faster, and the git mechanics are
  already covered by the integration tests above.

Run:
    python scripts/test_publish_on_accept.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_work_order_daemon as daemon  # noqa: E402


def _args(**overrides):
    import argparse
    base = dict(
        adapter="claude_code", max_budget_usd=0.20, per_step=False,
        poll_interval=15.0, api_url="http://localhost:8000", token="fake-token",
        frontend_url="http://localhost:3001",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _session(access_token="fake-token", **overrides):
    base = dict(access_token=access_token, refresh_token=None, supabase_url=None, supabase_anon_key=None)
    base.update(overrides)
    return daemon.TokenSession(**base)


def _detail(order_id, files_changed=None, artifacts=None, title="Test WO", goal="Mach das Ding"):
    return {
        "id": order_id, "title": title, "goal": goal,
        "acceptance_criteria": ["Es funktioniert."],
        "status": "accepted",
        "review_package": {"files_changed": files_changed if files_changed is not None else []},
        "artifacts": artifacts if artifacts is not None else [],
    }


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30)


class PublishWorkOrderGitIntegrationTests(unittest.TestCase):
    """Real git against a throwaway repo + local bare remote. Only `_run_gh`
    and `call_api` are mocked."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "work"
        self.bare_remote = Path(self._tmp.name) / "remote.git"
        self.repo.mkdir()
        self.bare_remote.mkdir()
        _run(["git", "init", "--bare"], self.bare_remote)
        _run(["git", "init", "-b", "main"], self.repo)
        _run(["git", "config", "user.email", "t@example.com"], self.repo)
        _run(["git", "config", "user.name", "Test"], self.repo)
        (self.repo / "a.txt").write_text("original a\n", encoding="utf-8")
        (self.repo / "b.txt").write_text("original b\n", encoding="utf-8")
        _run(["git", "add", "."], self.repo)
        _run(["git", "commit", "-m", "initial"], self.repo)
        _run(["git", "remote", "add", "origin", str(self.bare_remote)], self.repo)
        _run(["git", "push", "-u", "origin", "main"], self.repo)

    def tearDown(self):
        self._tmp.cleanup()

    def _dirty_working_tree(self):
        # a.txt is the file this work order touched; b.txt represents
        # unrelated, already-in-progress local work that must survive
        # untouched.
        (self.repo / "a.txt").write_text("changed a\n", encoding="utf-8")
        (self.repo / "b.txt").write_text("changed b\n", encoding="utf-8")

    def test_publishes_only_the_listed_files_and_returns_to_original_branch(self):
        self._dirty_working_tree()
        detail = _detail("wo-12345678-abcd", files_changed=["a.txt"])

        posted = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            posted.append((method, path, payload))
            return {}

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_gh", return_value=MagicMock(
                 returncode=0, stdout="https://github.com/acme/repo/pull/1\n", stderr="")) as mock_gh:
            daemon.publish_work_order(_args(), _session(), "wo-12345678-abcd", repo_root=self.repo)

        # Back on the original branch.
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repo).stdout.strip()
        self.assertEqual(branch, "main")

        # The new branch exists and its commit touched ONLY a.txt.
        branches = _run(["git", "branch", "--list", "wo/wo-12345"], self.repo).stdout
        self.assertIn("wo/wo-12345", branches)
        changed_files = _run(
            ["git", "show", "--name-only", "--format=", "wo/wo-12345"], self.repo
        ).stdout.split()
        self.assertEqual(changed_files, ["a.txt"])

        # b.txt's uncommitted change is still sitting in the working tree,
        # untouched and unstaged, back on the original branch.
        status = _run(["git", "status", "--porcelain"], self.repo).stdout
        self.assertIn("b.txt", status)
        self.assertEqual((self.repo / "b.txt").read_text(encoding="utf-8"), "changed b\n")
        status_lines = {line[:2].strip(): line[3:] for line in status.splitlines()}
        self.assertEqual(status_lines.get("M"), "b.txt")

        # gh was invoked with --base main, never asked to merge.
        gh_args = mock_gh.call_args.args[0]
        self.assertEqual(gh_args[:4], ["pr", "create", "--base", "main"])
        self.assertNotIn("merge", gh_args)

        # Result recorded back on the work order.
        artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
        self.assertEqual(len(artifact_posts), 1)
        self.assertEqual(artifact_posts[0]["type"], "summary")
        self.assertEqual(artifact_posts[0]["title"], "Pull Request")
        self.assertEqual(artifact_posts[0]["content"], "https://github.com/acme/repo/pull/1")
        log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
        self.assertEqual(len(log_posts), 1)
        self.assertEqual(log_posts[0]["level"], "info")

    def test_no_files_changed_posts_no_change_artifact_without_touching_git(self):
        self._dirty_working_tree()
        detail = _detail("wo-empty", files_changed=[])
        posted = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            posted.append((method, path, payload))
            return {}

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_git") as mock_git, \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(_args(), _session(), "wo-empty", repo_root=self.repo)

        mock_git.assert_not_called()
        mock_gh.assert_not_called()
        artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
        self.assertEqual(artifact_posts[0]["content"], "keine Änderungen")
        log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
        self.assertIn("nichts zu veröffentlichen", log_posts[0]["message"])


class PublishIdempotencyTests(unittest.TestCase):
    """Criterion 2: a second poll must not republish."""

    def test_existing_pull_request_artifact_short_circuits_before_any_git_call(self):
        detail = _detail("wo-1", files_changed=["a.txt"], artifacts=[
            {"type": "summary", "title": "Pull Request", "content": "https://github.com/x/y/pull/1"},
        ])
        with patch.object(daemon, "call_api", return_value=detail) as mock_call, \
             patch.object(daemon, "_run_git") as mock_git, \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(_args(), _session(), "wo-1")

        mock_git.assert_not_called()
        mock_gh.assert_not_called()
        mock_call.assert_called_once()  # only the GET, no artifact/activity-log POST either

    def test_second_poll_cycle_does_not_republish(self):
        state = {"published": False}

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                artifacts = [{"type": "summary", "title": "Pull Request", "content": "x"}] if state["published"] else []
                return _detail("wo-1", files_changed=["a.txt"], artifacts=artifacts)
            if path.endswith("/artifacts"):
                state["published"] = True
            return {}

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "get_current_branch", return_value="main"), \
             patch.object(daemon, "_run_git", return_value=MagicMock(returncode=0, stdout="", stderr="")), \
             patch.object(daemon, "_run_gh", return_value=MagicMock(returncode=0, stdout="https://x/pull/1\n", stderr="")) as mock_gh:
            daemon.publish_work_order(_args(), _session(), "wo-1")  # 1st: publishes
            daemon.publish_work_order(_args(), _session(), "wo-1")  # 2nd: must no-op

        mock_gh.assert_called_once()


class PublishErrorPathTests(unittest.TestCase):
    """Criterion 3: any failure returns to the original branch, logs an
    error, writes a 'fehlgeschlagen' artifact, and never uses force/reset."""

    def _assert_no_destructive_git_flags(self, mock_git):
        for call in mock_git.call_args_list:
            git_args = call.args[0]
            joined = " ".join(git_args)
            self.assertNotIn("--force", joined)
            self.assertNotIn(" -f", f" {joined}")
            self.assertNotIn("reset", joined)
            self.assertNotIn("--hard", joined)
            if git_args and git_args[0] == "push":
                self.assertNotIn("main", git_args)

    def test_push_failure_returns_to_original_branch_and_logs_error(self):
        detail = _detail("wo-1", files_changed=["a.txt"])
        posted = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            posted.append((method, path, payload))
            return {}

        def fake_run_git(git_args, repo_root, timeout=30):
            if git_args[0] == "push":
                return MagicMock(returncode=1, stdout="", stderr="remote rejected")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "get_current_branch", return_value="main"), \
             patch.object(daemon, "_run_git", side_effect=fake_run_git) as mock_git, \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(_args(), _session(), "wo-1")

        mock_gh.assert_not_called()  # never reached — push failed first
        # Last git call switches back to the original branch.
        last_call = mock_git.call_args_list[-1].args[0]
        self.assertEqual(last_call, ["switch", "main"])
        self._assert_no_destructive_git_flags(mock_git)

        log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
        self.assertEqual(log_posts[0]["level"], "error")
        artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
        self.assertTrue(artifact_posts[0]["content"].startswith("fehlgeschlagen:"))

    def test_branch_already_exists_is_handled_without_destructive_recovery(self):
        # Real git: pre-create wo/wo-1 so `git switch -c` genuinely collides.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _run(["git", "init", "-b", "main"], repo)
            _run(["git", "config", "user.email", "t@example.com"], repo)
            _run(["git", "config", "user.name", "Test"], repo)
            (repo / "a.txt").write_text("x\n", encoding="utf-8")
            _run(["git", "add", "."], repo)
            _run(["git", "commit", "-m", "initial"], repo)
            _run(["git", "branch", "wo/wo-1"], repo)

            detail = _detail("wo-1", files_changed=["a.txt"])
            posted = []

            def fake_call_api(api_url, session, method, path, payload=None):
                if method == "GET":
                    return detail
                posted.append((method, path, payload))
                return {}

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", repo_root=repo)

            mock_gh.assert_not_called()
            branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()
            self.assertEqual(branch, "main")
            log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
            self.assertEqual(log_posts[0]["level"], "error")

    def test_missing_file_in_files_changed_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _run(["git", "init", "-b", "main"], repo)
            _run(["git", "config", "user.email", "t@example.com"], repo)
            _run(["git", "config", "user.name", "Test"], repo)
            (repo / "a.txt").write_text("x\n", encoding="utf-8")
            _run(["git", "add", "."], repo)
            _run(["git", "commit", "-m", "initial"], repo)

            detail = _detail("wo-1", files_changed=["does-not-exist.txt"])
            posted = []

            def fake_call_api(api_url, session, method, path, payload=None):
                if method == "GET":
                    return detail
                posted.append((method, path, payload))
                return {}

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", repo_root=repo)

            mock_gh.assert_not_called()
            branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()
            self.assertEqual(branch, "main")
            log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
            self.assertEqual(log_posts[0]["level"], "error")
            # `git switch -c` itself succeeded before `git add` failed, so a
            # local wo/wo-1 branch pointer may exist — that's harmless as
            # long as it carries no actual commit beyond main (no data was
            # ever staged/committed for it).
            branches = _run(["git", "branch"], repo).stdout
            if "wo/wo-1" in branches:
                main_sha = _run(["git", "rev-parse", "main"], repo).stdout.strip()
                branch_sha = _run(["git", "rev-parse", "wo/wo-1"], repo).stdout.strip()
                self.assertEqual(branch_sha, main_sha)


class PublishOnAcceptEnvGateTests(unittest.TestCase):
    """Criterion 4: PUBLISH_ON_ACCEPT=0 disables the feature entirely."""

    def test_default_is_enabled(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("PUBLISH_ON_ACCEPT", None)
            self.assertTrue(daemon.publish_on_accept_enabled())

    def test_explicit_zero_disables(self):
        with patch.dict("os.environ", {"PUBLISH_ON_ACCEPT": "0"}):
            self.assertFalse(daemon.publish_on_accept_enabled())

    def test_disabled_makes_no_calls_at_all(self):
        with patch.dict("os.environ", {"PUBLISH_ON_ACCEPT": "0"}), \
             patch.object(daemon, "call_api") as mock_call, \
             patch.object(daemon, "_run_git") as mock_git, \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_accepted_work_orders(_args(), _session())

        mock_call.assert_not_called()
        mock_git.assert_not_called()
        mock_gh.assert_not_called()

    def test_enabled_fetches_accepted_orders(self):
        with patch.dict("os.environ", {"PUBLISH_ON_ACCEPT": "1"}), \
             patch.object(daemon, "call_api", return_value=[]) as mock_call:
            daemon.publish_accepted_work_orders(_args(), _session())

        mock_call.assert_called_once()


class FetchAcceptedWorkOrdersTests(unittest.TestCase):
    def test_filters_to_accepted_only(self):
        orders = [
            {"id": "wo-queued", "status": "queued"},
            {"id": "wo-accepted", "status": "accepted"},
            {"id": "wo-blocked", "status": "blocked"},
        ]
        with patch.object(daemon, "call_api", return_value=orders):
            result = daemon.fetch_accepted_work_orders("http://api", _session())
        self.assertEqual([o["id"] for o in result], ["wo-accepted"])


if __name__ == "__main__":
    unittest.main()
