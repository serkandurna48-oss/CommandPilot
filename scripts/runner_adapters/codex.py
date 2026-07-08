"""Placeholder RunnerAdapter for OpenAI Codex CLI as an auto-executing
runtime. Not implemented — see docs/runner-adapter-contract.md and
claude_code.py's docstring for the same rationale (this file mirrors it).
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import AdapterInfo, RunnerAdapter, RESULT_JSON_SCHEMA, build_result_example, build_runner_prompt


class CodexAdapter(RunnerAdapter):
    info = AdapterInfo(
        name="codex",
        capabilities=["read_repo", "write_local_files", "execute_shell", "modify_files"],
        safety_level="supervised",
        supports_live_events=False,
        supports_auto_execute="semi_auto",  # command_template is a guess — Codex CLI not researched yet
        consumes_paid_credits=True,  # would call a paid model API if ever implemented for real
        command_template="codex exec --prompt-file {prompt_file}",
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

    def execute(self, order: dict, session_path: Path, runner_command: str | None, max_budget_usd: float | None = None):
        raise NotImplementedError(
            "codex adapter is architecturally prepared but not implemented. "
            "Use --adapter manual_prompt, or --mode execute --runner-command \"...\" with an explicit "
            "command. See docs/runner-adapter-contract.md."
        )

    def collect_result(self, session_path: Path, result_file: str | None) -> dict:
        raise NotImplementedError(
            "codex adapter is not implemented. The result file format is identical to "
            "manual_prompt's — use --adapter manual_prompt for --mode import-result today."
        )
