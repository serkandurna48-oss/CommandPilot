#!/usr/bin/env python3
"""Tests for the independent Judge stage (scripts/judge_review.py, R2).

Stdlib-only (unittest + unittest.mock), consistent with the sibling
scripts/test_*.py standalone tests — the `claude` subprocess and every API
call are faked; nothing here runs a real judge, spends money, or touches a
real backend.

Run:
    python scripts/test_judge_review.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import judge_review  # noqa: E402


class FakeApi:
    """Records every _call_api call and returns a canned work order for GET."""

    def __init__(self, order: dict):
        self.order = order
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, api_url, token, method, path, payload=None, timeout=30):
        self.calls.append((method, path, payload))
        if method == "GET":
            return self.order
        return {}

    def posts_to(self, suffix: str) -> list[dict]:
        return [c[2] for c in self.calls if c[0] == "POST" and c[1].endswith(suffix)]

    def patches(self) -> list[dict]:
        return [c[2] for c in self.calls if c[0] == "PATCH"]

    def activity_logs(self) -> list[dict]:
        return [c[2] for c in self.calls if c[0] == "POST" and c[1].endswith("/activity-log")]


def _order(**overrides) -> dict:
    base = {
        "id": "wo-1",
        "status": "review_ready",
        "goal": "Baue Feature X",
        "acceptance_criteria": ["Kriterium A", "Kriterium B", "Kriterium C"],
        "artifacts": [],
    }
    base.update(overrides)
    return base


def _verdict(a="pass", b="pass", c="pass") -> dict:
    return {
        "criteria": [
            {"criterion": "Kriterium A", "verdict": a, "evidence": "Beleg A"},
            {"criterion": "Kriterium B", "verdict": b, "evidence": "Beleg B"},
            {"criterion": "Kriterium C", "verdict": c, "evidence": "Beleg C"},
        ],
        "overall": "pass",  # intentionally wrong sometimes — run_judge recomputes
    }


class ReadOnlyCliArgsTests(unittest.TestCase):
    """Criterion 6: the judge call uses only Read/Grep/Glob and JUDGE_MODEL —
    never Bash/Edit, never --dangerously-skip-permissions."""

    def test_cli_args_are_read_only_with_model(self):
        args = judge_review.build_judge_cli_args("opus", "claude")
        self.assertIn("--allowedTools", args)
        self.assertEqual(args[args.index("--allowedTools") + 1], "Read,Grep,Glob")
        self.assertIn("--model", args)
        self.assertEqual(args[args.index("--model") + 1], "opus")
        joined = " ".join(args)
        self.assertNotIn("Bash", joined)
        self.assertNotIn("Edit", joined)
        self.assertNotIn("Write", joined)
        self.assertNotIn("--dangerously-skip-permissions", joined)

    def test_run_claude_judge_invokes_subprocess_with_exact_args(self):
        captured: dict = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured["input"] = kwargs.get("input")
            return SimpleNamespace(returncode=0, stdout=json.dumps({"result": json.dumps(_verdict())}), stderr="")

        with patch.object(judge_review.subprocess, "run", side_effect=fake_run):
            judge_review.run_claude_judge("the prompt", "opus", 600, "claude", cwd=".")

        self.assertEqual(captured["args"], judge_review.build_judge_cli_args("opus", "claude"))
        self.assertEqual(captured["input"], "the prompt")

    def test_run_judge_honors_judge_model_env(self):
        fake = FakeApi(_order())
        with patch.dict(os.environ, {"JUDGE_MODEL": "sonnet"}), \
             patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          return_value=judge_review._validate_and_normalize(_verdict())) as mock_judge:
            judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")
        # run_claude_judge(prompt, model, timeout_s, claude_path, cwd=...)
        self.assertEqual(mock_judge.call_args.args[1], "sonnet")


class NormalizeTests(unittest.TestCase):
    def test_overall_recomputed_pass_only_if_all_pass(self):
        self.assertEqual(judge_review._validate_and_normalize(_verdict("pass", "pass", "pass"))["overall"], "pass")

    def test_unclear_only_gives_needs_human(self):
        # pass + unclear but NO fail → needs_human (not fail).
        self.assertEqual(judge_review._validate_and_normalize(_verdict("pass", "pass", "unclear"))["overall"], "needs_human")

    def test_fail_overrides_unclear_to_fail(self):
        # When there is at least one "fail", overall must be "fail" even if
        # there are also "unclear" criteria.
        self.assertEqual(judge_review._validate_and_normalize(_verdict("pass", "fail", "unclear"))["overall"], "fail")

    def test_fail_makes_overall_fail(self):
        self.assertEqual(judge_review._validate_and_normalize(_verdict("fail", "pass", "pass"))["overall"], "fail")

    def test_all_unclear_gives_needs_human(self):
        self.assertEqual(judge_review._validate_and_normalize(_verdict("unclear", "unclear", "unclear"))["overall"], "needs_human")

    def test_empty_criteria_rejected(self):
        with self.assertRaises(judge_review.JudgeError):
            judge_review._validate_and_normalize({"criteria": [], "overall": "pass"})

    def test_bad_verdict_value_rejected(self):
        with self.assertRaises(judge_review.JudgeError):
            judge_review._validate_and_normalize(
                {"criteria": [{"criterion": "A", "verdict": "maybe", "evidence": ""}], "overall": "pass"}
            )


class PassCaseTests(unittest.TestCase):
    """Criterion 3: all pass → review artifact written, order stays review_ready."""

    def test_pass_writes_artifact_and_does_not_transition(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          return_value=judge_review._validate_and_normalize(_verdict("pass", "pass", "pass"))):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")

        self.assertEqual(result["status"], "pass")
        artifacts = fake.posts_to("/artifacts")
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["type"], "review")
        self.assertEqual(artifacts[0]["title"], "Judge-Urteil")
        stored = json.loads(artifacts[0]["content"])
        self.assertEqual(stored["overall"], "pass")
        # No transition at all — stays review_ready for the human to accept.
        self.assertEqual(fake.patches(), [])


class NeedsHumanCaseTests(unittest.TestCase):
    """K2 criterion 1: pass/pass/unclear → needs_human.
    Order stays review_ready, no transition, warning log names the unclear criteria."""

    def test_pass_pass_unclear_no_transition_warning_log(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          return_value=judge_review._validate_and_normalize(_verdict("pass", "pass", "unclear"))):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")

        # status is needs_human, unclear_criteria lists the problematic one
        self.assertEqual(result["status"], "needs_human")
        self.assertIn("Kriterium C", result["unclear_criteria"])
        self.assertNotIn("Kriterium A", result["unclear_criteria"])
        self.assertNotIn("Kriterium B", result["unclear_criteria"])

        # Verdict artifact is still written (same as pass/fail)
        artifacts = fake.posts_to("/artifacts")
        self.assertEqual(len(artifacts), 1)
        stored = json.loads(artifacts[0]["content"])
        self.assertEqual(stored["overall"], "needs_human")

        # NO status transition — order stays review_ready
        self.assertEqual(fake.patches(), [])

        # A warning log entry names the unclear criterion
        warnings = [log for log in fake.activity_logs() if log.get("level") == "warning"]
        self.assertTrue(warnings, "expected a warning activity-log line")
        self.assertIn("Kriterium C", warnings[-1]["message"])
        self.assertIn("manuell", warnings[-1]["message"])

    def test_needs_human_verdict_stored_in_artifact(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          return_value=judge_review._validate_and_normalize(_verdict("unclear", "unclear", "unclear"))):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")

        self.assertEqual(result["status"], "needs_human")
        self.assertEqual(len(result["unclear_criteria"]), 3)
        stored = json.loads(fake.posts_to("/artifacts")[0]["content"])
        self.assertEqual(stored["overall"], "needs_human")


class FailWithUnclearTests(unittest.TestCase):
    """K2 criterion 2: pass/fail/unclear → fail (rework_requested), same as before."""

    def test_pass_fail_unclear_transitions_to_rework_requested(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          return_value=judge_review._validate_and_normalize(_verdict("pass", "fail", "unclear"))):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")

        self.assertEqual(result["status"], "fail")
        # Kriterium B (fail) and Kriterium C (unclear) both count as "not pass"
        self.assertIn("Kriterium B", result["failed_criteria"])
        self.assertIn("Kriterium C", result["failed_criteria"])

        patches = fake.patches()
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["status"], "rework_requested")
        self.assertIn("Kriterium B", patches[0]["reason"])


class FailCaseTests(unittest.TestCase):
    """Criterion 4: fail → rework_requested with the failed criteria as reason."""

    def test_fail_transitions_to_rework_requested_with_reason(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          return_value=judge_review._validate_and_normalize(_verdict("pass", "fail", "pass"))):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["failed_criteria"], ["Kriterium B"])
        # Artifact still written.
        self.assertEqual(len(fake.posts_to("/artifacts")), 1)
        # Transition to rework_requested, reason names the failed criterion.
        patches = fake.patches()
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["status"], "rework_requested")
        self.assertEqual(patches[0]["source"], "harness")
        self.assertIn("Kriterium B", patches[0]["reason"])


class FailClosedTests(unittest.TestCase):
    """Criterion 5: a judge problem (timeout, broken JSON) leaves the order
    review_ready and logs a warning — never a transition, never an artifact."""

    def _assert_fail_closed(self, fake: FakeApi, result: dict):
        self.assertEqual(result["status"], "judge_error")
        self.assertEqual(fake.posts_to("/artifacts"), [])  # no verdict artifact
        self.assertEqual(fake.patches(), [])               # order untouched
        warnings = [log for log in fake.activity_logs() if log.get("level") == "warning"]
        self.assertTrue(warnings, "expected a warning activity-log line")
        self.assertIn("manuell prüfen", warnings[-1]["message"])

    def test_timeout_is_fail_closed(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          side_effect=judge_review.JudgeError("Judge-Timeout nach 600s")):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")
        self._assert_fail_closed(fake, result)

    def test_broken_json_is_fail_closed(self):
        fake = FakeApi(_order())
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge",
                          side_effect=judge_review.JudgeError("Judge-Ausgabe ist kein gültiges JSON")):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")
        self._assert_fail_closed(fake, result)

    def test_run_claude_judge_timeout_raises_judge_error(self):
        def fake_run(args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=1)

        with patch.object(judge_review.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(judge_review.JudgeError):
                judge_review.run_claude_judge("p", "opus", 1, "claude")

    def test_run_claude_judge_unparseable_output_raises_judge_error(self):
        def fake_run(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "ganz sicher kein json {{{"}), stderr="")

        with patch.object(judge_review.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(judge_review.JudgeError):
                judge_review.run_claude_judge("p", "opus", 600, "claude")

    def test_no_criteria_is_fail_closed(self):
        fake = FakeApi(_order(acceptance_criteria=[]))
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge", return_value=judge_review._validate_and_normalize(_verdict())):
            result = judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", diff_fetcher=lambda _r, _s=None: "diff")
        self._assert_fail_closed(fake, result)


def _git(cwd: str, *args: str):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


class GatherDiffTests(unittest.TestCase):
    """R2b: gather_diff diffs against base_sha with --ignore-cr-at-eol, so pure
    CRLF churn is excluded and committed-after-base work is included. Uses a
    real throwaway git repo (git is already required by the runner)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        _git(self.repo, "init")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")
        # Pin line-ending behavior so the test is deterministic regardless of
        # the machine's global core.autocrlf.
        _git(self.repo, "config", "core.autocrlf", "false")
        (Path(self.repo) / "file.txt").write_bytes(b"line1\nline2\nline3\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "base")
        self.base_sha = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def tearDown(self):
        self.tmp.cleanup()

    def test_crlf_only_change_not_in_diff(self):
        # Criterion 1: same content, only LF -> CRLF. Must produce no diff.
        (Path(self.repo) / "file.txt").write_bytes(b"line1\r\nline2\r\nline3\r\n")
        diff = judge_review.gather_diff(self.repo, self.base_sha)
        self.assertEqual(diff.strip(), "")

    def test_committed_change_after_base_appears(self):
        # Criterion 2: a real change committed AFTER base_sha must appear.
        (Path(self.repo) / "file.txt").write_bytes(b"line1\nECHTE_AENDERUNG\nline3\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "executor work")
        diff = judge_review.gather_diff(self.repo, self.base_sha)
        self.assertIn("ECHTE_AENDERUNG", diff)

    def test_real_change_survives_alongside_crlf_noise(self):
        # Belt-and-braces: one real content line change PLUS CRLF churn on the
        # other lines — only the real change may show.
        (Path(self.repo) / "file.txt").write_bytes(b"line1\r\nECHTE_AENDERUNG\r\nline3\r\n")
        diff = judge_review.gather_diff(self.repo, self.base_sha)
        self.assertIn("+ECHTE_AENDERUNG", diff)
        # line1/line3 only changed by CRLF -> never emitted as +/- change lines
        # (they may still appear as unchanged context lines prefixed with a space).
        self.assertNotIn("-line1", diff)
        self.assertNotIn("+line1", diff)
        self.assertNotIn("-line3", diff)
        self.assertNotIn("+line3", diff)

    def test_no_base_sha_returns_empty(self):
        (Path(self.repo) / "file.txt").write_bytes(b"line1\nWHATEVER\nline3\n")
        self.assertEqual(judge_review.gather_diff(self.repo, None), "")


class DiffArtifactFallbackTests(unittest.TestCase):
    """Criterion 3: without base_sha, run_judge uses ONLY the executor's diff
    artifact (gather_diff returns "" with no baseline), never a live diff."""

    def test_without_base_sha_only_diff_artifact_is_used(self):
        order = _order(artifacts=[{"id": "a1", "type": "diff", "content": "ARTIFACT_DIFF_MARKER"}])
        fake = FakeApi(order)
        captured: dict = {}

        def fake_judge(prompt, model, timeout_s, claude_path, cwd=None):
            captured["prompt"] = prompt
            return judge_review._validate_and_normalize(_verdict())

        # Note: real gather_diff (default diff_fetcher), base_sha=None -> "".
        with patch.object(judge_review, "_call_api", fake), \
             patch.object(judge_review, "run_claude_judge", side_effect=fake_judge):
            judge_review.run_judge("http://x", "tok", "wo-1", claude_path="claude", base_sha=None)

        self.assertIn("ARTIFACT_DIFF_MARKER", captured["prompt"])


class ToggleTests(unittest.TestCase):
    def test_judge_enabled_default_on(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JUDGE_ENABLED", None)
            self.assertTrue(judge_review.judge_enabled())

    def test_judge_disabled_values(self):
        for val in ("0", "false", "no", "off", "OFF"):
            with patch.dict(os.environ, {"JUDGE_ENABLED": val}):
                self.assertFalse(judge_review.judge_enabled())


if __name__ == "__main__":
    unittest.main()
