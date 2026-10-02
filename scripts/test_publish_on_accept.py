#!/usr/bin/env python3
"""Tests for scripts/run_work_order_daemon.py's Publish-on-Accept feature
(K3/K3b/K4): an accepted work order's reviewPackage.files_changed becomes a
real branch + PR, via local git + `gh` — merge always stays a human decision.

K4 rewrote the git mechanics: publish_work_order() now operates entirely
inside the order's own worktree (already checked out on 'wo/<id8>' since
claim time, see test_worktree_per_order.py) — no more 'git switch -c'/
'switch back to main' dance, and no more "must be on main" guard (replaced
by "the worktree exists and is on its own branch").

Two styles, deliberately:
- `PublishWorkOrderGitIntegrationTests`/`PublishPathSafetyGuardTests` run
  REAL git against a throwaway admin repo + local bare remote + a real
  worktree created via the real `ensure_order_worktree()` — only `_run_gh()`
  (the `gh` CLI call) and `call_api()` (the backend) are mocked. This is the
  one place a fake git could hide a real bug (staging the wrong files,
  losing unrelated uncommitted work in the admin repo, not removing the
  worktree on success).
- Everything else (idempotency, the env-var gate, non-git error paths)
  mocks `_run_git`/`_run_gh`/`get_current_branch` directly — faster, and
  the git mechanics are already covered by the integration tests above.
  These only need a worktree DIRECTORY to exist (for the
  Path.exists() guard) — its contents don't matter since git calls are
  mocked.

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


def _detail(order_id, files_changed=None, artifacts=None, title="Test WO", goal="Mach das Ding",
            allowed_paths=None, activity_log=None, accepted_at=None):
    # allowed_paths defaults to "allow everything" ("**") — tests that aren't
    # specifically exercising the path-safety guard shouldn't need to know
    # about it. accepted_at, if given, is injected as a synthetic
    # status_transition activity_log entry (the cutoff guard's primary
    # timestamp source) so cutoff tests don't need to fake the whole entry
    # shape.
    log_entries = list(activity_log) if activity_log is not None else []
    if accepted_at is not None:
        log_entries.append({
            "event_type": "status_transition", "created_at": accepted_at,
            "metadata": {"to_status": "accepted"},
        })
    return {
        "id": order_id, "title": title, "goal": goal,
        "acceptance_criteria": ["Es funktioniert."],
        "status": "accepted",
        "review_package": {"files_changed": files_changed if files_changed is not None else []},
        "artifacts": artifacts if artifacts is not None else [],
        "approval_scope": {"allowed_paths": allowed_paths if allowed_paths is not None else ["**"]},
        "activity_log": log_entries,
    }


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30)


def _fake_worktree_dir(worktree_root: Path, order_id: str) -> Path:
    """For mocked-git tests: publish_work_order() does a real
    Path.exists() check before anything else, so a directory needs to
    genuinely exist at the path ensure_order_worktree() would have used —
    its contents don't matter since all git calls are mocked in these
    tests."""
    path = Path(worktree_root) / f"wo-{order_id[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class _AdminRepoTestCase(unittest.TestCase):
    """A real admin repo (stand-in for REPO_ROOT) with a local bare 'origin'
    remote, so the full claim (ensure_order_worktree) + publish flow can run
    for real without network access. Same fixture shape as
    test_worktree_per_order.py's base class."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.admin_repo = Path(self._tmp.name) / "admin"
        self.bare_remote = Path(self._tmp.name) / "remote.git"
        self.worktree_root = Path(self._tmp.name) / "commandpilot-orders"
        self.admin_repo.mkdir()
        self.bare_remote.mkdir()
        _run(["git", "init", "--bare"], self.bare_remote)
        _run(["git", "init", "-b", "main"], self.admin_repo)
        _run(["git", "config", "user.email", "t@example.com"], self.admin_repo)
        _run(["git", "config", "user.name", "Test"], self.admin_repo)
        (self.admin_repo / "a.txt").write_text("original a\n", encoding="utf-8")
        (self.admin_repo / "secret.txt").write_text("original secret\n", encoding="utf-8")
        _run(["git", "add", "."], self.admin_repo)
        _run(["git", "commit", "-m", "initial"], self.admin_repo)
        _run(["git", "remote", "add", "origin", str(self.bare_remote)], self.admin_repo)
        _run(["git", "push", "-u", "origin", "main"], self.admin_repo)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_worktree(self, order_id):
        return daemon.ensure_order_worktree(order_id, repo_root=self.admin_repo, worktree_root=self.worktree_root)


class PublishWorkOrderGitIntegrationTests(_AdminRepoTestCase):
    def test_publishes_only_the_listed_files_removes_worktree_and_leaves_admin_untouched(self):
        worktree = self._make_worktree("wo-12345678-abcd")
        self.assertIsNotNone(worktree)
        (worktree / "a.txt").write_text("changed a\n", encoding="utf-8")

        admin_branch_before = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.admin_repo).stdout.strip()
        admin_head_before = _run(["git", "rev-parse", "HEAD"], self.admin_repo).stdout.strip()
        admin_status_before = _run(["git", "status", "--porcelain"], self.admin_repo).stdout

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
            daemon.publish_work_order(
                _args(), _session(), "wo-12345678-abcd",
                repo_root=self.admin_repo, worktree_root=self.worktree_root,
            )

        # Worktree removed on success.
        self.assertFalse(worktree.exists())

        # Admin repo ("Haupt-Kopie") completely untouched.
        self.assertEqual(_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.admin_repo).stdout.strip(), admin_branch_before)
        self.assertEqual(_run(["git", "rev-parse", "HEAD"], self.admin_repo).stdout.strip(), admin_head_before)
        self.assertEqual(_run(["git", "status", "--porcelain"], self.admin_repo).stdout, admin_status_before)

        # The commit on wo/wo-12345 (branch survives worktree removal,
        # visible from the admin repo) touched ONLY a.txt.
        changed_files = _run(
            ["git", "show", "--name-only", "--format=", "wo/wo-12345"], self.admin_repo,
        ).stdout.split()
        self.assertEqual(changed_files, ["a.txt"])

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

    def test_main_copy_unaffected_even_on_feature_branch_with_dirty_changes(self):
        # Criterion 4's explicit "auch wenn sie auf einem Feature-Branch
        # steht und ungespeicherte Änderungen hat" — put the admin repo on
        # an unrelated branch with its own uncommitted edit BEFORE
        # publishing, and verify neither is touched.
        worktree = self._make_worktree("wo-1")
        self.assertIsNotNone(worktree)
        (worktree / "a.txt").write_text("executor change\n", encoding="utf-8")

        _run(["git", "switch", "-c", "feature/serkans-own-work"], self.admin_repo)
        (self.admin_repo / "a.txt").write_text("Serkan's own uncommitted WIP\n", encoding="utf-8")
        admin_status_before = _run(["git", "status", "--porcelain"], self.admin_repo).stdout
        self.assertIn("a.txt", admin_status_before)

        detail = _detail("wo-1", files_changed=["a.txt"])

        def fake_call_api(api_url, session, method, path, payload=None):
            return detail if method == "GET" else {}

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_gh", return_value=MagicMock(
                 returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr="")):
            daemon.publish_work_order(
                _args(), _session(), "wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root,
            )

        self.assertEqual(
            _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.admin_repo).stdout.strip(),
            "feature/serkans-own-work",
        )
        admin_status_after = _run(["git", "status", "--porcelain"], self.admin_repo).stdout
        self.assertEqual(admin_status_before, admin_status_after)
        self.assertEqual((self.admin_repo / "a.txt").read_text(encoding="utf-8"), "Serkan's own uncommitted WIP\n")


class PublishNoChangesTests(unittest.TestCase):
    """Empty files_changed returns before any worktree/git involvement at
    all — no worktree needs to exist for this path."""

    def test_no_files_changed_posts_no_change_artifact_without_touching_git(self):
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
            daemon.publish_work_order(_args(), _session(), "wo-empty")

        mock_git.assert_not_called()
        mock_gh.assert_not_called()
        artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
        self.assertEqual(artifact_posts[0]["content"], "keine Änderungen")
        log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
        self.assertIn("nichts zu veröffentlichen", log_posts[0]["message"])


class PublishIdempotencyTests(unittest.TestCase):
    """Criterion 2 (K3): a second poll must not republish."""

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
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)
            _fake_worktree_dir(worktree_root, "wo-1")
            state = {"published": False}

            def fake_call_api(api_url, session, method, path, payload=None):
                if method == "GET":
                    artifacts = [{"type": "summary", "title": "Pull Request", "content": "x"}] if state["published"] else []
                    return _detail("wo-1", files_changed=["a.txt"], artifacts=artifacts)
                if path.endswith("/artifacts"):
                    state["published"] = True
                return {}

            def fake_run_git(git_args, repo_root, timeout=30):
                if git_args[:2] == ["status", "--porcelain"]:
                    return MagicMock(returncode=0, stdout=" M a.txt\n", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "get_current_branch", return_value="wo/wo-1"), \
                 patch.object(daemon, "_run_git", side_effect=fake_run_git), \
                 patch.object(daemon, "_run_gh", return_value=MagicMock(returncode=0, stdout="https://x/pull/1\n", stderr="")) as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)  # 1st: publishes
                # Recreate the worktree dir — a real publish would have
                # removed it via _run_git (mocked here), so the 2nd call's
                # Path.exists() guard still needs it present.
                _fake_worktree_dir(worktree_root, "wo-1")
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)  # 2nd: must no-op

        mock_gh.assert_called_once()


class PublishWorktreeGuardTests(unittest.TestCase):
    """K4: replaces K3b's "must be on main" guard — the order's own
    worktree must exist and still be checked out on its own 'wo/<id8>'
    branch."""

    def test_missing_worktree_is_skipped_without_an_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)  # no wo-1 subdirectory created
            detail = _detail("wo-1", files_changed=["a.txt"])
            calls = []

            def fake_call_api(api_url, session, method, path, payload=None):
                calls.append((method, path))
                if method == "GET":
                    return detail
                return {}

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "_run_git") as mock_git, \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)

        mock_git.assert_not_called()
        mock_gh.assert_not_called()
        self.assertEqual(calls, [("GET", "/api/work-orders/wo-1")])  # no POST

    def test_worktree_on_wrong_branch_is_skipped_without_an_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)
            _fake_worktree_dir(worktree_root, "wo-1")
            detail = _detail("wo-1", files_changed=["a.txt"])
            calls = []

            def fake_call_api(api_url, session, method, path, payload=None):
                calls.append((method, path))
                if method == "GET":
                    return detail
                return {}

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "get_current_branch", return_value="some-other-branch"), \
                 patch.object(daemon, "_run_git") as mock_git, \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)

        mock_git.assert_not_called()  # get_current_branch is checked, no further git calls
        mock_gh.assert_not_called()
        self.assertEqual(calls, [("GET", "/api/work-orders/wo-1")])

    def test_worktree_on_its_own_branch_is_not_blocked_by_this_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)
            _fake_worktree_dir(worktree_root, "wo-1")
            detail = _detail("wo-1", files_changed=["a.txt"])

            def fake_call_api(api_url, session, method, path, payload=None):
                return detail if method == "GET" else {}

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "get_current_branch", return_value="wo/wo-1"), \
                 patch.object(daemon, "_run_git", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_git:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)

        mock_git.assert_called()  # proceeded past the worktree guard


class PublishPathSafetyGuardTests(_AdminRepoTestCase):
    """Criterion 3+4 (K3b, still enforced by K4): every files_changed entry
    must match allowed_paths AND actually be dirty — checked with real git,
    before any stage/commit."""

    def test_file_outside_allowed_paths_fails_before_any_commit(self):
        worktree = self._make_worktree("wo-1")
        (worktree / "secret.txt").write_text("changed\n", encoding="utf-8")  # dirty, but not allowed
        detail = _detail("wo-1", files_changed=["secret.txt"], allowed_paths=["frontend/**", "backend/**"])
        posted = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            posted.append((method, path, payload))
            return {}

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(
                _args(), _session(), "wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root,
            )

        mock_gh.assert_not_called()
        self.assertTrue(worktree.exists())  # never removed — nothing was ever committed
        commits = _run(["git", "log", "--oneline"], worktree).stdout.strip().splitlines()
        self.assertEqual(len(commits), 1)  # only the initial commit, no new one
        log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
        self.assertEqual(log_posts[0]["level"], "error")
        self.assertIn("allowed_paths", log_posts[0]["message"])
        artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
        self.assertTrue(artifact_posts[0]["content"].startswith("fehlgeschlagen:"))

    def test_listed_but_unchanged_file_fails_with_reason_and_no_commit(self):
        worktree = self._make_worktree("wo-1")
        # a.txt is tracked and clean inside the worktree — never modified,
        # even though the order claims it as a changed file.
        detail = _detail("wo-1", files_changed=["a.txt"])
        posted = []

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            posted.append((method, path, payload))
            return {}

        commits_before = _run(["git", "log", "--oneline"], worktree).stdout.strip().splitlines()

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(
                _args(), _session(), "wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root,
            )

        mock_gh.assert_not_called()
        self.assertTrue(worktree.exists())
        commits_after = _run(["git", "log", "--oneline"], worktree).stdout.strip().splitlines()
        self.assertEqual(commits_before, commits_after)
        log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
        self.assertEqual(log_posts[0]["level"], "error")
        self.assertIn("nicht tatsächlich geändert", log_posts[0]["message"])
        artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
        self.assertTrue(artifact_posts[0]["content"].startswith("fehlgeschlagen:"))

    def test_empty_allowed_paths_fails_every_file(self):
        worktree = self._make_worktree("wo-1")
        (worktree / "a.txt").write_text("changed\n", encoding="utf-8")
        detail = _detail("wo-1", files_changed=["a.txt"], allowed_paths=[])

        def fake_call_api(api_url, session, method, path, payload=None):
            return detail if method == "GET" else {}

        with patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(
                _args(), _session(), "wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root,
            )

        mock_gh.assert_not_called()
        self.assertTrue(worktree.exists())


class PublishErrorPathTests(unittest.TestCase):
    """Criterion 5 (K4): a publish failure leaves the worktree in place
    (never removed), logs an error, and never uses force/reset/branch -D."""

    def _assert_no_destructive_git_flags(self, mock_git):
        for call in mock_git.call_args_list:
            git_args = call.args[0]
            joined = " ".join(git_args)
            self.assertNotIn("--force", joined)
            self.assertNotIn(" -f", f" {joined}")
            self.assertNotIn("reset", joined)
            self.assertNotIn("--hard", joined)
            self.assertNotIn("-D", git_args)
            if git_args and git_args[0] == "push":
                self.assertNotIn("main", git_args)

    def test_push_failure_logs_error_and_names_the_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)
            worktree_path = _fake_worktree_dir(worktree_root, "wo-1")
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
                if git_args[:2] == ["status", "--porcelain"]:
                    return MagicMock(returncode=0, stdout=" M a.txt\n", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "get_current_branch", return_value="wo/wo-1"), \
                 patch.object(daemon, "_run_git", side_effect=fake_run_git) as mock_git, \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)

            mock_gh.assert_not_called()  # never reached — push failed first
            # No 'worktree remove' attempted on a failure path.
            for call in mock_git.call_args_list:
                self.assertNotEqual(call.args[0][:2], ["worktree", "remove"])
            self._assert_no_destructive_git_flags(mock_git)
            self.assertTrue(worktree_path.exists())  # left in place

            log_posts = [p for m, path, p in posted if path.endswith("/activity-log")]
            self.assertEqual(log_posts[0]["level"], "error")
            artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
            self.assertTrue(artifact_posts[0]["content"].startswith("fehlgeschlagen:"))
            self.assertIn("wo/wo-1", artifact_posts[0]["content"])
            self.assertIn("Änderung liegt auf lokalem Branch", artifact_posts[0]["content"])

    def test_gh_failure_also_names_the_branch_and_keeps_the_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)
            worktree_path = _fake_worktree_dir(worktree_root, "wo-12345678")
            detail = _detail("wo-12345678", files_changed=["a.txt"])
            posted = []

            def fake_call_api(api_url, session, method, path, payload=None):
                if method == "GET":
                    return detail
                posted.append((method, path, payload))
                return {}

            def fake_run_git(git_args, repo_root, timeout=30):
                if git_args[:2] == ["status", "--porcelain"]:
                    return MagicMock(returncode=0, stdout=" M a.txt\n", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "get_current_branch", return_value="wo/wo-12345"), \
                 patch.object(daemon, "_run_git", side_effect=fake_run_git), \
                 patch.object(daemon, "_run_gh", return_value=MagicMock(
                     returncode=1, stdout="", stderr="gh: not authenticated")):
                daemon.publish_work_order(_args(), _session(), "wo-12345678", worktree_root=worktree_root)

            self.assertTrue(worktree_path.exists())
            artifact_posts = [p for m, path, p in posted if path.endswith("/artifacts")]
            self.assertIn("wo/wo-12345", artifact_posts[0]["content"])
            self.assertIn("Änderung liegt auf lokalem Branch", artifact_posts[0]["content"])


class PublishOnAcceptEnvGateTests(unittest.TestCase):
    """PUBLISH_ON_ACCEPT=0 disables the feature entirely."""

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


class PublishCutoffGuardTests(unittest.TestCase):
    """K3b criterion 1: an order accepted before PUBLISH_SINCE is skipped
    silently — no git/gh call, no artifact."""

    def test_order_accepted_before_default_cutoff_is_skipped_silently(self):
        detail = _detail("wo-1", files_changed=["a.txt"], accepted_at="2026-09-01T00:00:00+00:00")
        calls = []

        def fake_call_api(api_url, session, method, path, payload=None):
            calls.append((method, path))
            if method == "GET":
                return detail
            return {}

        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("PUBLISH_SINCE", None)
            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "_run_git") as mock_git, \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1")

        mock_git.assert_not_called()
        mock_gh.assert_not_called()
        self.assertEqual(calls, [("GET", "/api/work-orders/wo-1")])  # no POST at all

    def test_order_accepted_after_cutoff_is_not_skipped_by_this_guard(self):
        # Sanity check the inverse: a recent acceptance must NOT be rejected
        # by the cutoff guard (it proceeds to the worktree-existence guard
        # instead and is skipped there, proving the cutoff guard itself let
        # it through).
        detail = _detail("wo-1", files_changed=["a.txt"], accepted_at="2026-10-02T14:00:00+02:00")

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "_run_git") as mock_git, \
                 patch.object(daemon, "_run_gh") as mock_gh:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=Path(tmp))

        mock_git.assert_not_called()  # no worktree dir exists -> guard skips before any git call
        mock_gh.assert_not_called()

    def test_publish_since_env_var_moves_the_cutoff(self):
        # An order that would pass the default cutoff is skipped once
        # PUBLISH_SINCE is set to something later than its acceptance time.
        detail = _detail("wo-1", files_changed=["a.txt"], accepted_at="2026-10-02T14:00:00+02:00")

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            return {}

        with patch.dict("os.environ", {"PUBLISH_SINCE": "2026-12-01T00:00:00+00:00"}), \
             patch.object(daemon, "call_api", side_effect=fake_call_api), \
             patch.object(daemon, "_run_git") as mock_git, \
             patch.object(daemon, "_run_gh") as mock_gh:
            daemon.publish_work_order(_args(), _session(), "wo-1")

        mock_git.assert_not_called()
        mock_gh.assert_not_called()

    def test_unparseable_timestamp_does_not_block_publishing(self):
        # Unknown/garbled age must never silently suppress a real order.
        detail = _detail("wo-1", files_changed=["a.txt"], accepted_at="not-a-date")

        def fake_call_api(api_url, session, method, path, payload=None):
            if method == "GET":
                return detail
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)
            _fake_worktree_dir(worktree_root, "wo-1")
            with patch.object(daemon, "call_api", side_effect=fake_call_api), \
                 patch.object(daemon, "get_current_branch", return_value="wo/wo-1"), \
                 patch.object(daemon, "_run_git", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_git:
                daemon.publish_work_order(_args(), _session(), "wo-1", worktree_root=worktree_root)

        mock_git.assert_called()  # proceeded past the cutoff guard


if __name__ == "__main__":
    unittest.main()
