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
    block, hit_sources, base_sources = vault_service.get_context_for_query("irgendwas", vault_path=str(missing))
    assert block == ""
    assert hit_sources == []
    assert base_sources == []


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
    # Query shares no vocabulary with any note body — only base context should surface,
    # and it must show up as base_sources, not hit_sources (nothing actually matched).
    block, hit_sources, base_sources = vault_service.get_context_for_query(
        "Woran sollte ich diese Woche arbeiten und warum?", vault_path=str(tmp_path)
    )
    assert hit_sources == []
    assert "00-Index.md" in {s["file"] for s in base_sources}
    assert "Projekte/CommandPilot.md" in {s["file"] for s in base_sources}
    assert "active" in block  # frontmatter status surfaced via base context


# ── Sources noise reduction (JARVIS-A1, Aufgabe 5) ───────────────────────────────
def test_hit_sources_and_base_sources_are_kept_separate(tmp_path):
    _make_vault(tmp_path)
    block, hit_sources, base_sources = vault_service.get_context_for_query(
        "Was ist die Next Action für CommandPilot?", vault_path=str(tmp_path)
    )
    # base_sources: always-present map-of-the-vault entries, one per file, no heading.
    assert {s["file"] for s in base_sources} == {"00-Index.md", "Projekte/CommandPilot.md", "Menschen/Volkan.md"}
    assert all(s["heading"] == "" for s in base_sources)

    # hit_sources: files whose content actually matched the query keywords, with real
    # section headings. Volkan.md shares no vocabulary with the query and must not
    # show up here, even though it's present in base_sources.
    assert hit_sources
    hit_files = {s["file"] for s in hit_sources}
    assert "Projekte/CommandPilot.md" in hit_files
    assert "Menschen/Volkan.md" not in hit_files
    assert all(s["heading"] != "" for s in hit_sources)


# ── Ownership gate (JARVIS-A1, Aufgabe 2) ────────────────────────────────────────
def test_mismatched_user_id_returns_empty_context(tmp_path, monkeypatch):
    _make_vault(tmp_path)
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", "owner-1")
    block, hit_sources, base_sources = vault_service.get_context_for_query(
        "Was ist die Next Action für CommandPilot?", user_id="someone-else", vault_path=str(tmp_path)
    )
    assert block == ""
    assert hit_sources == []
    assert base_sources == []


def test_matching_user_id_returns_normal_context(tmp_path, monkeypatch):
    _make_vault(tmp_path)
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", "owner-1")
    block, hit_sources, base_sources = vault_service.get_context_for_query(
        "Was ist die Next Action für CommandPilot?", user_id="owner-1", vault_path=str(tmp_path)
    )
    assert block != ""
    assert hit_sources != []


def test_empty_vault_owner_user_id_behaves_as_before(tmp_path, monkeypatch):
    _make_vault(tmp_path)
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", "")
    block, hit_sources, base_sources = vault_service.get_context_for_query(
        "Was ist die Next Action für CommandPilot?", user_id="anyone-at-all", vault_path=str(tmp_path)
    )
    assert block != ""
    assert hit_sources != []


# ── Invalid UTF-8 handling (JARVIS-A1, Aufgabe 3) ────────────────────────────────
def test_invalid_utf8_file_is_skipped_other_files_still_found(tmp_path):
    _make_vault(tmp_path)
    # Invalid UTF-8 byte sequence (a lone continuation byte) — read_text(encoding="utf-8")
    # raises UnicodeDecodeError, not OSError, on this.
    (tmp_path / "Projekte" / "Broken.md").write_bytes(b"# Broken\n\xff\xfe invalid utf-8 bytes here")

    matches = vault_service.retrieve_context(
        "Was ist die Next Action für CommandPilot?", token_budget=1000, vault_path=str(tmp_path)
    )
    files = {m.source_file for m in matches}
    assert "Projekte/CommandPilot.md" in files
    assert "Projekte/Broken.md" not in files


def test_invalid_utf8_in_base_context_entity_note_is_skipped(tmp_path):
    _make_vault(tmp_path)
    (tmp_path / "Projekte" / "Broken.md").write_bytes(b"# Broken\n\xff\xfe invalid utf-8 bytes here")

    matches = vault_service.get_base_context(token_budget=1000, vault_path=str(tmp_path))
    files = {m.source_file for m in matches}
    assert "Projekte/CommandPilot.md" in files
    assert "Projekte/Broken.md" not in files


# ── Budget capping (JARVIS-A1, Aufgabe 4) ────────────────────────────────────────
def test_base_budget_capped_to_total_budget_codex_repro(tmp_path):
    # Reproduction from the Codex finding: a 10,000-char 00-Index.md with the
    # default base_token_budget (1200, i.e. 4800 chars) must not be allowed
    # to blow past a much smaller total_token_budget. Before the fix,
    # get_base_context() ignored total_token_budget entirely.
    (tmp_path / "Projekte").mkdir()
    (tmp_path / "Menschen").mkdir()
    (tmp_path / "00-Index.md").write_text("Index " * 1700, encoding="utf-8")  # ~10,200 chars

    total_token_budget = 50  # 200 chars
    block, _, _ = vault_service.get_context_for_query(
        "irrelevant query", total_token_budget=total_token_budget, vault_path=str(tmp_path)
    )
    # +len(header) for the "### Quelle: 00-Index.md\n" prefix, +1 for the "…" truncation marker.
    max_expected = total_token_budget * vault_service._CHARS_PER_TOKEN + len("### Quelle: 00-Index.md\n") + 1
    assert len(block) <= max_expected


def test_formatted_header_counts_against_budget(tmp_path):
    # A match whose source label is long relative to its budget must not let
    # the header push the total formatted output over budget — the header
    # itself has to count, not just the raw match text.
    (tmp_path / "Projekte").mkdir()
    (tmp_path / "Menschen").mkdir()
    (tmp_path / "00-Index.md").write_text("x", encoding="utf-8")
    long_name = "A" * 100
    (tmp_path / "Projekte" / f"{long_name}.md").write_text(
        f"# {long_name}\n\n## Section\n\n{'word ' * 500}", encoding="utf-8"
    )

    token_budget = 30  # 120 chars — smaller than the header itself would be uncapped
    matches = vault_service.retrieve_context("word", token_budget=token_budget, vault_path=str(tmp_path))
    formatted = vault_service.format_context_block(matches)
    assert len(formatted) <= token_budget * vault_service._CHARS_PER_TOKEN + 1  # +1 for "…"
