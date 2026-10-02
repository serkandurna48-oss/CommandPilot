#!/usr/bin/env python3
"""Tests for scripts/runner_adapters/claude_code.py's --allowedTools mapping
(_map_allowed_tools()) — specifically the K3 fix for a live-found gap: the
generic "Bash(npm run *)" wildcard alone did not keep the executor from
being prompted for `npm run lint`/`npm run type-check` in frontend/.

Run:
    python scripts/test_claude_code_adapter.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runner_adapters.claude_code as claude_code  # noqa: E402


class MapAllowedToolsLintTypecheckTests(unittest.TestCase):
    def test_test_lint_typecheck_scope_grants_npm_run_lint_and_type_check(self):
        tools = claude_code._map_allowed_tools({"allowed_actions": ["test_lint_typecheck"]})
        self.assertIn("Bash(npm run lint*)", tools)
        self.assertIn("Bash(npm run type-check*)", tools)
        # The pre-existing blanket wildcard must still be present — additive,
        # not a replacement.
        self.assertIn("Bash(npm run *)", tools)

    def test_cd_prefixed_frontend_invocation_also_granted(self):
        tools = claude_code._map_allowed_tools({"allowed_actions": ["test_lint_typecheck"]})
        self.assertIn("Bash(cd frontend && npm run lint*)", tools)
        self.assertIn("Bash(cd frontend && npm run type-check*)", tools)

    def test_scope_without_test_lint_typecheck_does_not_grant_npm(self):
        tools = claude_code._map_allowed_tools({"allowed_actions": ["code_edit_within_scope"]})
        self.assertNotIn("Bash(npm run lint*)", tools)
        self.assertNotIn("Bash(npm run type-check*)", tools)

    def test_base_read_tools_always_present(self):
        tools = claude_code._map_allowed_tools({"allowed_actions": []})
        for base in ("Read", "Glob", "Grep"):
            self.assertIn(base, tools)


if __name__ == "__main__":
    unittest.main()
