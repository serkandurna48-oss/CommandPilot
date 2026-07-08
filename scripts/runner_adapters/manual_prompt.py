"""The manual_prompt RunnerAdapter — today's default, fully-working path.

Writes a prompt for a human to paste into Claude Code/Codex by hand, and
reads back a result.json a human saved after the session. No auto-execute
of its own (safety_level="manual" — a human is in the loop for every
single action this adapter is involved in); `--mode execute
--runner-command "..."` still works with this adapter, but that's
run_work_order.py's generic, adapter-agnostic escape hatch, not this
class's own execute() method.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .base import (
    AdapterInfo,
    RunnerAdapter,
    RESULT_JSON_SCHEMA,
    build_result_example,
    build_runner_prompt,
    parse_and_validate_result,
)


class ManualPromptAdapter(RunnerAdapter):
    info = AdapterInfo(
        name="manual_prompt",
        capabilities=["read_repo", "write_local_files"],
        safety_level="manual",
        supports_live_events=False,
        supports_auto_execute="no",
        # This adapter never calls a paid API itself — it only writes local
        # files. Whatever the human later pastes the prompt into is on
        # their own account/session, outside this adapter's control.
        consumes_paid_credits=False,
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

    def collect_result(self, session_path: Path, result_file: str | None) -> dict:
        path_arg = result_file or str(session_path / "result.json")
        if path_arg == "-":
            return parse_and_validate_result(sys.stdin.read(), "stdin")
        path = Path(path_arg)
        if not path.exists():
            raise FileNotFoundError(
                f"result file not found: {path} "
                f"(default expected: {session_path / 'result.json'} — or pass --result-file)"
            )
        return parse_and_validate_result(path.read_text(encoding="utf-8"), str(path))
