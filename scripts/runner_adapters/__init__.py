"""Registry of available RunnerAdapters. See base.py for the contract."""

from __future__ import annotations

from .base import AdapterInfo, ExecuteOutcome, RunnerAdapter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .manual_prompt import ManualPromptAdapter
from .openclaw import OpenClawAdapter

ADAPTERS: dict[str, type[RunnerAdapter]] = {
    "manual_prompt": ManualPromptAdapter,
    "claude_code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "openclaw": OpenClawAdapter,
}


def get_adapter(name: str) -> RunnerAdapter:
    cls = ADAPTERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown adapter '{name}'. Available: {', '.join(ADAPTERS)}")
    return cls()


__all__ = ["AdapterInfo", "ExecuteOutcome", "RunnerAdapter", "ADAPTERS", "get_adapter"]
