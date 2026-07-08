"""Placeholder RunnerAdapter for OpenClaw as a possible future runtime.

Explicitly out of scope for evaluation or integration right now (per
OP-Runner-002 §13 and OP-Runner-003's mission) — this file exists purely
so "OpenClaw" has a named slot in the adapter registry, matching the
architectural principle that CommandPilot orchestrates interchangeable
adapters rather than being rebuilt around any one of them. Nothing about
OpenClaw's actual capabilities has been researched or verified; the
`capabilities`/`command_template` below are placeholders, not claims.
Do not wire this up without first evaluating OpenClaw for real.
"""

from __future__ import annotations

from pathlib import Path

from .base import AdapterInfo, RunnerAdapter


class OpenClawAdapter(RunnerAdapter):
    info = AdapterInfo(
        name="openclaw",
        capabilities=["read_repo", "write_local_files", "execute_shell", "modify_files"],
        safety_level="supervised",
        supports_live_events=False,
        supports_auto_execute="no",  # nothing about OpenClaw has been evaluated — "no" is the honest default
        consumes_paid_credits=True,  # conservative assumption — treat as credit-consuming until proven otherwise
        command_template=None,  # unknown — not evaluated
    )

    def prepare(self, order: dict, session_path: Path) -> Path:
        raise NotImplementedError(
            "openclaw adapter is a named placeholder only — OpenClaw has not been evaluated as a "
            "RunnerAdapter yet. Use --adapter manual_prompt. See docs/runner-adapter-contract.md."
        )

    def execute(self, order: dict, session_path: Path, runner_command: str | None, max_budget_usd: float | None = None):
        raise NotImplementedError(
            "openclaw adapter is a named placeholder only — not implemented, not evaluated."
        )

    def collect_result(self, session_path: Path, result_file: str | None) -> dict:
        raise NotImplementedError(
            "openclaw adapter is a named placeholder only — not implemented, not evaluated."
        )
