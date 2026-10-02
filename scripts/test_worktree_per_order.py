#!/usr/bin/env python3
"""Tests for scripts/run_work_order_daemon.py's K4 feature: one git worktree
per work order, so the executor/Judge/Publish-on-Accept never touch REPO_ROOT
(the daemon's own checkout) — see ensure_order_worktree(),
_order_worktree_path(), _worktree_root(), _remove_order_worktree().

Real git against a throwaway admin repo + local bare remote (same style as
test_publish_on_accept.py's git-integration tests) — nothing here hits a
real GitHub remote or spawns a real `claude`/`run_work_order.py` process.

Run:
    python scripts/test_worktree_per_order.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_work_order_daemon as daemon  # noqa: E402


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30)


class _AdminRepoTestCase(unittest.TestCase):
    """A real admin repo (stand-in for REPO_ROOT) with a local bare 'origin'
    remote, so `git fetch origin main`/`git worktree add ... origin/main`
    work for real without network access."""

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
        _run(["git", "add", "."], self.admin_repo)
        _run(["git", "commit", "-m", "initial"], self.admin_repo)
        _run(["git", "remote", "add", "origin", str(self.bare_remote)], self.admin_repo)
        _run(["git", "push", "-u", "origin", "main"], self.admin_repo)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_worktree(self, order_id):
        return daemon.ensure_order_worktree(order_id, repo_root=self.admin_repo, worktree_root=self.worktree_root)


class EnsureOrderWorktreeTests(_AdminRepoTestCase):
    """Criterion 1: claim-time worktree creation, and the admin repo must be
    completely unaffected (git status/HEAD identical before and after)."""

    def test_creates_worktree_on_wo_branch_from_origin_main(self):
        worktree = daemon.ensure_order_worktree(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890", repo_root=self.admin_repo, worktree_root=self.worktree_root,
        )

        self.assertIsNotNone(worktree)
        self.assertEqual(worktree, self.worktree_root / "wo-a1b2c3d4")
        self.assertTrue(worktree.exists())

        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], worktree).stdout.strip()
        self.assertEqual(branch, "wo/a1b2c3d4")
        # Created from origin/main's commit, not some other ref.
        worktree_head = _run(["git", "rev-parse", "HEAD"], worktree).stdout.strip()
        origin_main_head = _run(["git", "rev-parse", "origin/main"], self.admin_repo).stdout.strip()
        self.assertEqual(worktree_head, origin_main_head)

    def test_admin_repo_git_status_and_head_unchanged_before_and_after(self):
        head_before = _run(["git", "rev-parse", "HEAD"], self.admin_repo).stdout.strip()
        branch_before = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.admin_repo).stdout.strip()
        status_before = _run(["git", "status", "--porcelain"], self.admin_repo).stdout

        daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)

        head_after = _run(["git", "rev-parse", "HEAD"], self.admin_repo).stdout.strip()
        branch_after = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.admin_repo).stdout.strip()
        status_after = _run(["git", "status", "--porcelain"], self.admin_repo).stdout

        self.assertEqual(head_before, head_after)
        self.assertEqual(branch_before, branch_after)
        self.assertEqual(status_before, status_after)

    def test_admin_repo_unaffected_even_with_its_own_dirty_uncommitted_changes(self):
        # Serkan's own in-progress edit on the admin checkout — must survive
        # untouched by claim-time worktree creation for an unrelated order.
        (self.admin_repo / "a.txt").write_text("Serkan's own WIP edit\n", encoding="utf-8")
        status_before = _run(["git", "status", "--porcelain"], self.admin_repo).stdout
        self.assertIn("a.txt", status_before)

        daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)

        status_after = _run(["git", "status", "--porcelain"], self.admin_repo).stdout
        self.assertEqual(status_before, status_after)
        self.assertEqual((self.admin_repo / "a.txt").read_text(encoding="utf-8"), "Serkan's own WIP edit\n")


class EnsureOrderWorktreeReuseTests(_AdminRepoTestCase):
    """Criterion 3: a second claim for the same order (rework after
    rework_requested/failed) reuses the existing worktree, no error."""

    def test_second_call_reuses_the_same_worktree_without_error(self):
        first = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        (first / "a.txt").write_text("partial rework attempt\n", encoding="utf-8")

        second = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)

        self.assertEqual(first, second)
        # The previous attempt's uncommitted edit is still there — reuse
        # does not reset/clean anything.
        self.assertEqual((second / "a.txt").read_text(encoding="utf-8"), "partial rework attempt\n")

    def test_reuse_does_not_attempt_fetch_or_worktree_add_again(self):
        daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)

        with patch.object(daemon, "_run_git") as mock_git:
            daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        # get_current_branch (to verify the reused worktree) is the only
        # _run_git-backed call reuse makes — no fetch, no worktree add.
        for call in mock_git.call_args_list:
            git_args = call.args[0]
            self.assertNotEqual(git_args[:2], ["fetch", "origin"])
            self.assertNotEqual(git_args[:2], ["worktree", "add"])

    def test_existing_directory_on_the_wrong_branch_is_rejected_not_reused(self):
        # Simulates a manually tampered worktree — defensive, not something
        # the daemon itself would ever produce.
        worktree = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        _run(["git", "switch", "-c", "something-else"], worktree)

        result = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        self.assertIsNone(result)


class EnsureOrderWorktreeFailureTests(_AdminRepoTestCase):
    def test_fetch_failure_returns_none_and_creates_no_worktree(self):
        with patch.object(daemon, "_run_git") as mock_git:
            mock_git.return_value.returncode = 1
            mock_git.return_value.stderr = "network unreachable"
            result = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        self.assertIsNone(result)
        self.assertFalse((self.worktree_root / "wo-1").exists())

    def test_branch_name_collision_without_existing_worktree_dir_fails_cleanly(self):
        # The branch already exists (e.g. a prior worktree was manually
        # deleted without removing its branch), but the worktree directory
        # does not — `git worktree add -b` refuses to recreate the branch.
        _run(["git", "branch", "wo/wo-1"], self.admin_repo)

        result = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)

        self.assertIsNone(result)
        self.assertFalse((self.worktree_root / "wo-1").exists())
        # The pre-existing branch itself is untouched (no force/delete).
        branches = _run(["git", "branch"], self.admin_repo).stdout
        self.assertIn("wo/wo-1", branches)


class WorktreePathWindowsSafetyTests(_AdminRepoTestCase):
    """K4 point 7: all paths must survive spaces/backslashes on Windows."""

    def test_worktree_root_with_a_space_in_the_path(self):
        spaced_root = Path(self._tmp.name) / "command pilot orders"
        worktree = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=spaced_root)
        self.assertIsNotNone(worktree)
        self.assertTrue(worktree.exists())
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], worktree).stdout.strip()
        self.assertEqual(branch, "wo/wo-1")

    def test_removal_works_with_a_space_in_the_path(self):
        spaced_root = Path(self._tmp.name) / "command pilot orders"
        worktree = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=spaced_root)
        ok = daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)
        self.assertTrue(ok)
        self.assertFalse(worktree.exists())


class LinkFrontendNodeModulesTests(_AdminRepoTestCase):
    """K4 point 6: frontend/node_modules doesn't exist in a fresh worktree
    (gitignored) — linked via an NTFS junction to the main checkout's
    already-installed copy, never copied, never built fresh unless the
    order actually needs it."""

    def _add_fake_node_modules(self):
        node_modules = self.admin_repo / "frontend" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "marker.txt").write_text("installed package data\n", encoding="utf-8")
        return node_modules

    def test_junction_makes_node_modules_visible_inside_the_worktree(self):
        self._add_fake_node_modules()
        worktree = self._make_worktree("wo-1")

        linked = worktree / "frontend" / "node_modules"
        self.assertTrue(linked.exists())
        self.assertEqual((linked / "marker.txt").read_text(encoding="utf-8"), "installed package data\n")

    def test_no_copy_only_a_link_changes_in_admin_are_visible_live(self):
        node_modules = self._add_fake_node_modules()
        worktree = self._make_worktree("wo-1")

        # A change to the admin copy's node_modules shows up through the
        # junction immediately — proof it's a link, not a copy.
        (node_modules / "new-package.txt").write_text("added later\n", encoding="utf-8")
        linked = worktree / "frontend" / "node_modules"
        self.assertTrue((linked / "new-package.txt").exists())

    def test_missing_source_node_modules_is_a_silent_no_op(self):
        # Main checkout never ran npm install — no node_modules to link.
        worktree = self._make_worktree("wo-1")
        self.assertFalse((worktree / "frontend" / "node_modules").exists())
        # No warning-worthy failure either — just nothing to do.

    def test_existing_target_is_never_overwritten(self):
        self._add_fake_node_modules()
        worktree = self._make_worktree("wo-1")  # creates the junction once
        linked = worktree / "frontend" / "node_modules"
        self.assertTrue(linked.exists())

        # Calling again (e.g. rework reuse path) must not error or re-link.
        daemon._link_frontend_node_modules(worktree, repo_root=self.admin_repo)
        self.assertTrue((linked / "marker.txt").exists())

    def test_never_touches_env_files(self):
        self._add_fake_node_modules()
        (self.admin_repo / "frontend").mkdir(exist_ok=True)
        (self.admin_repo / "frontend" / ".env.local").write_text("SECRET=shh\n", encoding="utf-8")

        worktree = self._make_worktree("wo-1")

        self.assertFalse((worktree / "frontend" / ".env.local").exists())


class WorktreeRootResolutionTests(unittest.TestCase):
    def test_default_is_sibling_of_repo_root(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WORKTREE_ROOT", None)
            root = daemon._worktree_root()
        self.assertEqual(root, daemon.REPO_ROOT.parent / "commandpilot-orders")

    def test_env_var_overrides_default(self):
        with patch.dict(os.environ, {"WORKTREE_ROOT": r"C:\custom\orders root"}):
            root = daemon._worktree_root()
        self.assertEqual(root, Path(r"C:\custom\orders root"))

    def test_order_worktree_path_uses_first_8_chars_of_id(self):
        path = daemon._order_worktree_path("a1b2c3d4-e5f6-7890-abcd-ef1234567890", worktree_root=Path("/orders"))
        self.assertEqual(path, Path("/orders/wo-a1b2c3d4"))


class RemoveOrderWorktreeTests(_AdminRepoTestCase):
    def test_clean_worktree_is_removed_and_branch_survives(self):
        worktree = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)

        ok = daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)

        self.assertTrue(ok)
        self.assertFalse(worktree.exists())
        branches = _run(["git", "branch"], self.admin_repo).stdout
        self.assertIn("wo/wo-1", branches)  # local branch survives removal

    def test_removal_never_uses_force(self):
        worktree = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        with patch.object(daemon, "_run_git", wraps=daemon._run_git) as mock_git:
            daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)
        for call in mock_git.call_args_list:
            self.assertNotIn("--force", call.args[0])

    def test_dirty_worktree_is_left_behind_not_force_removed(self):
        worktree = daemon.ensure_order_worktree("wo-1", repo_root=self.admin_repo, worktree_root=self.worktree_root)
        (worktree / "untracked.txt").write_text("leftover\n", encoding="utf-8")

        ok = daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)

        self.assertFalse(ok)
        self.assertTrue(worktree.exists())  # left behind, not force-deleted


class RemoveOrderWorktreeJunctionCleanupTests(_AdminRepoTestCase):
    """K4b: without unlinking the frontend/node_modules junction first,
    `git worktree remove` refuses outright — it treats everything behind
    the junction as untracked content OF the worktree (live-verified: same
    'contains modified or untracked files' error as any other leftover
    file, even though nothing was ever actually touched there). Fixed by
    unlinking just the reparse point (os.rmdir on a junction — never
    recurses into/deletes the target) before calling `git worktree
    remove`."""

    def _add_source_node_modules(self):
        node_modules = self.admin_repo / "frontend" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "marker.txt").write_text("real installed package data\n", encoding="utf-8")
        return node_modules

    def test_worktree_removed_and_source_node_modules_survives_unchanged(self):
        # Criterion 1.
        source = self._add_source_node_modules()
        worktree = self._make_worktree("wo-1")  # also creates the junction
        self.assertTrue((worktree / "frontend" / "node_modules").is_junction())

        ok = daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)

        self.assertTrue(ok)
        self.assertFalse(worktree.exists())
        self.assertTrue(source.exists())
        self.assertEqual((source / "marker.txt").read_text(encoding="utf-8"), "real installed package data\n")

    def test_real_directory_node_modules_is_left_alone_remove_behaves_as_before(self):
        # Criterion 2: a REAL directory (not a junction) at that path must
        # never be touched by the new unlink step — git worktree remove
        # alone decides its fate, exactly like any other untracked content
        # (see RemoveOrderWorktreeTests.test_dirty_worktree_is_left_behind_not_force_removed).
        worktree = self._make_worktree("wo-1")  # no source node_modules -> no junction created
        real_nm = worktree / "frontend" / "node_modules"
        real_nm.mkdir(parents=True)
        (real_nm / "untracked.txt").write_text("not a junction\n", encoding="utf-8")
        self.assertFalse(real_nm.is_junction())

        ok = daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)

        self.assertFalse(ok)  # git refuses, same as any other untracked content
        self.assertTrue(worktree.exists())
        self.assertTrue(real_nm.exists())
        self.assertEqual((real_nm / "untracked.txt").read_text(encoding="utf-8"), "not a junction\n")

    def test_no_rmtree_or_recursive_delete_is_ever_used(self):
        # Criterion 3.
        self._add_source_node_modules()
        worktree = self._make_worktree("wo-1")
        junction = worktree / "frontend" / "node_modules"

        with patch("shutil.rmtree") as mock_rmtree, \
             patch.object(os, "rmdir", wraps=os.rmdir) as mock_rmdir:
            daemon._remove_order_worktree(worktree, repo_root=self.admin_repo)

        mock_rmtree.assert_not_called()
        mock_rmdir.assert_called_once()
        # The single os.rmdir call targeted exactly the junction — nothing
        # inside the real source, nothing else in the worktree.
        called_path = Path(mock_rmdir.call_args.args[0])
        self.assertEqual(called_path, junction)

    def test_unlink_helper_no_ops_when_target_is_not_a_junction(self):
        worktree = self._make_worktree("wo-1")
        real_nm = worktree / "frontend" / "node_modules"
        real_nm.mkdir(parents=True)
        (real_nm / "x.txt").write_text("x\n", encoding="utf-8")

        with patch("os.rmdir") as mock_rmdir:
            daemon._unlink_frontend_node_modules_junction(worktree)

        mock_rmdir.assert_not_called()
        self.assertTrue(real_nm.exists())


if __name__ == "__main__":
    unittest.main()
