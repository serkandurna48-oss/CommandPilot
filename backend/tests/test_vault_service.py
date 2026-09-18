"""
Tests for vault_service.py (Jarvis v1 — second-brain retrieval).

Pytest-native (uses tmp_path), unlike the unittest-style suites elsewhere in
this directory — the fixture-vault requirement makes pytest's tmp_path the
natural fit here.

Run:
    python -m pytest backend/tests/test_vault_service.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.services import vault_service  # noqa: E402


def _make_vault(root: Path) -> None:
    (root / "Projekte").mkdir()
    (root / "Menschen").mkdir()

    (root / "00-Index.md").write_text(
        "# Index\n\nÜbersicht: [[Projekte/CommandPilot]], [[Menschen/Volkan]].\n",
        encoding="utf-8",
    )

    (root / "Projekte" / "CommandPilot.md").write_text(
        "---\n"
        "type: project\n"
        "status: active\n"
        "priority: P3\n"
        "updated: 2026-09-18\n"
        "---\n\n"
        "# CommandPilot\n\n"
        "Persönliches AI-Operator-System.\n\n"
        "## Next Action\n\n"
        "Work-Order-Loop-CLI-Lauf abschließen, danach Jarvis Schritt 1.\n",
        encoding="utf-8",
    )

    (root / "Menschen" / "Volkan.md").write_text(
        "---\n"
        "type: person\n"
        "status: active\n"
        "---\n\n"
        "# Volkan\n\n"
        "Trainingspartner, trifft sich dienstags zum Bouldern.\n",
        encoding="utf-8",
    )

    (root / "CLAUDE.md").write_text(
        "Anweisungen fürs Vault. CommandPilot Next Action geheim.\n",
        encoding="utf-8",
    )


def test_relevant_file_is_found(tmp_path):
    _make_vault(tmp_path)
    matches = vault_service.retrieve_context(
        "Was ist die Next Action für CommandPilot?", token_budget=1000, vault_path=str(tmp_path)
    )
    files = {m.source_file for m in matches}
    assert "Projekte/CommandPilot.md" in files


def test_irrelevant_file_not_included(tmp_path):
    _make_vault(tmp_path)
    matches = vault_service.retrieve_context(
        "Was ist die Next Action für CommandPilot?", token_budget=1000, vault_path=str(tmp_path)
    )
    files = {m.source_file for m in matches}
    assert "Menschen/Volkan.md" not in files


def test_excluded_vault_claude_md_never_retrieved(tmp_path):
    _make_vault(tmp_path)
    matches = vault_service.retrieve_context(
        "CommandPilot Next Action geheim", token_budget=1000, vault_path=str(tmp_path)
    )
    files = {m.source_file for m in matches}
    assert "CLAUDE.md" not in files


def test_missing_vault_path_returns_empty(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert vault_service.retrieve_context("irgendwas", token_budget=1000, vault_path=str(missing)) == []
    assert vault_service.get_base_context(token_budget=500, vault_path=str(missing)) == []
    block, sources = vault_service.get_context_for_query("irgendwas", vault_path=str(missing))
    assert block == ""
    assert sources == []


def test_empty_vault_path_returns_empty():
    assert vault_service.retrieve_context("irgendwas", token_budget=1000, vault_path="") == []
    assert vault_service.get_base_context(token_budget=500, vault_path="") == []


def test_token_budget_is_respected(tmp_path):
    (tmp_path / "Projekte").mkdir()
    (tmp_path / "Menschen").mkdir()
    (tmp_path / "00-Index.md").write_text("# Index\n", encoding="utf-8")

    long_body = "Budget " * 2000  # ~14000 chars, well over any small budget
    (tmp_path / "Projekte" / "Big.md").write_text(
        f"# Big\n\n## Notes\n\n{long_body}\n", encoding="utf-8"
    )

    token_budget = 50  # ~200 chars
    matches = vault_service.retrieve_context("Budget", token_budget=token_budget, vault_path=str(tmp_path))
    total_chars = sum(len(m.text) for m in matches)
    assert total_chars <= token_budget * vault_service._CHARS_PER_TOKEN + 1  # +1 for the truncation marker


def test_get_context_for_query_always_includes_base_context(tmp_path):
    _make_vault(tmp_path)
    # Query shares no vocabulary with any note body — only base context should surface.
    block, sources = vault_service.get_context_for_query(
        "Woran sollte ich diese Woche arbeiten und warum?", vault_path=str(tmp_path)
    )
    assert "00-Index.md" in {s["file"] for s in sources}
    assert "Projekte/CommandPilot.md" in {s["file"] for s in sources}
    assert "active" in block  # frontmatter status surfaced via base context
