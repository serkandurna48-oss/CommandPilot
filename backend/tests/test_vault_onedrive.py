"""
Tests for the OneDrive vault source (VAULT_SOURCE="onedrive").

Covers the V2 acceptance criteria that aren't about local behavior (that's
test_vault_service.py, still green and unchanged):
  2. OneDrive returns a hit from 00-Jetzt.md with a source.
  3. Deny-listed files (Projekte/Privat.md, 40-Gesundheit.md, Daily/x.md) are
     never loaded, even when OneDrive lists them.
  4. A Composio error → empty context, no exception, a status reason is set.
  5. Cache: a second call within the TTL does not call Composio again.

Composio is fully mocked — no network. The fake client records every tool
call so the deny-list / cache assertions can inspect exactly what was fetched.

Run:
    python -m pytest backend/tests/test_vault_onedrive.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.services import onedrive_vault_service as od  # noqa: E402
from app.services import vault_service  # noqa: E402

OWNER = "owner-1"

# Vault-relative path -> markdown content. Deny-listed files are present here
# on purpose, to prove they're filtered even though OneDrive "has" them.
_VAULT_CONTENT = {
    "00-Jetzt.md": "# 00-Jetzt\n\n## Fokus\n\nImmobilien in Baunatal kaufen, Immobilien-Cockpit bauen.\n",
    "00-Index.md": "# Index\n\nÜbersicht.\n",
    "20-Ziele.md": "# Ziele\n\nUni-Abschluss.\n",
    "40-Gesundheit.md": "# Gesundheit\n\nReha-Status: sensibel.\n",
    "05-Inbox.md": "# Inbox\n\nnot allow-listed flat file.\n",
    "Projekte/CommandPilot.md": "---\ntype: project\nstatus: active\n---\n\n# CommandPilot\n\nAI-Operator.\n",
    "Projekte/Privat.md": "---\ntype: project\n---\n\n# Privat\n\nSensible Privatnotiz.\n",
    "Entscheidungen/Vault-Cloud.md": "---\ntype: decision\n---\n\n# Vault Cloud\n\nSupabase Storage.\n",
    "Menschen/Enis.md": "---\ntype: person\n---\n\n# Enis\n\nSensibel.\n",
    "Daily/2026-09-25.md": "# Tagesabschluss\n\nSensibles Tageslog.\n",
}

# How the fake drive is laid out per folder listing (name -> is_folder).
_ROOT_CHILDREN = [
    ("00-Jetzt.md", False),
    ("00-Index.md", False),
    ("20-Ziele.md", False),
    ("40-Gesundheit.md", False),   # deny-listed (prefix)
    ("05-Inbox.md", False),        # not allow-listed
    ("Projekte", True),            # allowed subdir
    ("Entscheidungen", True),      # allowed subdir
    ("Menschen", True),            # deny-listed subdir — must never be listed
    ("Daily", True),               # deny-listed subdir — must never be listed
]
_SUBDIR_CHILDREN = {
    "/secondbrain/Projekte": [("CommandPilot.md", False), ("Privat.md", False)],  # Privat deny-listed
    "/secondbrain/Entscheidungen": [("Vault-Cloud.md", False)],
    "/secondbrain/Menschen": [("Enis.md", False)],
    "/secondbrain/Daily": [("2026-09-25.md", False)],
}


class _FakeTools:
    def __init__(self, calls, fail=False):
        self._calls = calls
        self._fail = fail

    def execute(self, slug, user_id, arguments, version, dangerously_skip_version_check):
        self._calls.append((slug, arguments))
        if self._fail:
            raise RuntimeError("Composio boom")

        if slug == od._LIST_TOOL:
            folder = arguments["folder_path"]
            children = _ROOT_CHILDREN if folder == "/secondbrain" else _SUBDIR_CHILDREN.get(folder, [])
            value = [
                ({"name": name, "folder": {}} if is_dir else {"name": name, "file": {}})
                for name, is_dir in children
            ]
            return {"data": {"value": value, "next_page_token": None}, "successful": True}

        if slug == od._DOWNLOAD_TOOL:
            # item_path is drive-root-relative, no leading slash: "secondbrain/<rel>"
            rel = arguments["item_path"].split("secondbrain/", 1)[-1]
            return {"data": {"content": {"name": rel, "mimetype": "text/markdown",
                                         "s3url": f"https://s3.test/{rel}"}}, "successful": True}

        raise AssertionError(f"unexpected tool slug {slug}")


class _FakeClient:
    def __init__(self, calls, fail=False):
        self.tools = _FakeTools(calls, fail=fail)


@pytest.fixture
def onedrive_env(monkeypatch):
    """VAULT_SOURCE=onedrive with Composio configured and the fake client +
    fake URL fetch wired in. Returns the list that records Composio calls."""
    calls: list = []
    monkeypatch.setattr(vault_service.settings, "VAULT_SOURCE", "onedrive")
    monkeypatch.setattr(od.settings, "VAULT_SOURCE", "onedrive")
    monkeypatch.setattr(od.settings, "VAULT_ONEDRIVE_ROOT", "/secondbrain")
    monkeypatch.setattr(od.settings, "VAULT_ONEDRIVE_CACHE_TTL_SECONDS", 600)
    monkeypatch.setattr(od.settings, "COMPOSIO_API_KEY", "test-key")
    monkeypatch.setattr(od.settings, "COMPOSIO_USER_ID", "composio-user")
    monkeypatch.setattr(od, "get_client", lambda: _FakeClient(calls))
    # Resolve the fake s3url back to the markdown content, no real network.
    monkeypatch.setattr(od, "_http_get_text", lambda url: _VAULT_CONTENT[url.split("https://s3.test/", 1)[-1]])
    od.reset_cache()
    yield calls
    od.reset_cache()


# ── Criterion 2: a hit from 00-Jetzt.md with a source ────────────────────────
def test_onedrive_query_hits_jetzt_with_source(onedrive_env, monkeypatch):
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", OWNER)
    block, hit_sources, _base = vault_service.get_context_for_query(
        "Immobilien", user_id=OWNER
    )
    assert "Immobilien in Baunatal" in block
    assert "00-Jetzt.md" in {s["file"] for s in hit_sources}


def test_onedrive_retrieve_returns_match_from_jetzt(onedrive_env):
    matches = vault_service.retrieve_context("Immobilien", token_budget=1000)
    assert any(m.source_file == "00-Jetzt.md" for m in matches)


# ── Criterion 3: deny-listed files never loaded ──────────────────────────────
def test_denied_files_never_loaded(onedrive_env):
    load = od.load_files()
    assert load.status == od.STATUS_OK
    # Allowed files are present...
    assert "00-Jetzt.md" in load.files
    assert "Projekte/CommandPilot.md" in load.files
    assert "Entscheidungen/Vault-Cloud.md" in load.files
    # ...deny-listed / non-allow-listed ones are absent even though the fake
    # drive lists them.
    for forbidden in ("Projekte/Privat.md", "40-Gesundheit.md", "05-Inbox.md",
                      "Menschen/Enis.md", "Daily/2026-09-25.md"):
        assert forbidden not in load.files


def test_denied_folders_are_never_even_listed_or_downloaded(onedrive_env):
    calls = onedrive_env
    od.load_files()
    listed_folders = {args["folder_path"] for slug, args in calls if slug == od._LIST_TOOL}
    assert "/secondbrain/Menschen" not in listed_folders
    assert "/secondbrain/Daily" not in listed_folders
    downloaded = {args["item_path"] for slug, args in calls if slug == od._DOWNLOAD_TOOL}
    assert not any("Privat.md" in p or "40-Gesundheit" in p or "Menschen" in p or "Daily" in p
                   for p in downloaded)


def test_denied_file_not_served_even_if_query_matches(onedrive_env, monkeypatch):
    # A query whose keyword only appears in a deny-listed note must surface nothing.
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", OWNER)
    matches = vault_service.retrieve_context("Reha-Status sensibel", token_budget=1000)
    assert all(m.source_file != "40-Gesundheit.md" for m in matches)


# ── Criterion 4: Composio error → empty context, no exception, reason set ────
def test_composio_error_yields_empty_context_and_status_reason(monkeypatch):
    calls: list = []
    monkeypatch.setattr(vault_service.settings, "VAULT_SOURCE", "onedrive")
    monkeypatch.setattr(od.settings, "VAULT_SOURCE", "onedrive")
    monkeypatch.setattr(od.settings, "COMPOSIO_API_KEY", "test-key")
    monkeypatch.setattr(od.settings, "COMPOSIO_USER_ID", "composio-user")
    monkeypatch.setattr(od.settings, "VAULT_ONEDRIVE_ROOT", "/secondbrain")
    monkeypatch.setattr(od, "get_client", lambda: _FakeClient(calls, fail=True))
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", OWNER)
    od.reset_cache()

    # No exception bubbles up, context is empty.
    block, hit_sources, base_sources = vault_service.get_context_for_query("Immobilien", user_id=OWNER)
    assert (block, hit_sources, base_sources) == ("", [], [])

    # Status carries a reason.
    status = vault_service.get_vault_status(OWNER)
    assert status["ok"] is False
    assert status["reason"] == "onedrive_error"
    od.reset_cache()


def test_not_connected_when_composio_unconfigured(monkeypatch):
    monkeypatch.setattr(vault_service.settings, "VAULT_SOURCE", "onedrive")
    monkeypatch.setattr(od.settings, "VAULT_SOURCE", "onedrive")
    monkeypatch.setattr(od.settings, "COMPOSIO_API_KEY", "")
    monkeypatch.setattr(od.settings, "COMPOSIO_USER_ID", "")
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", OWNER)
    od.reset_cache()

    assert vault_service.retrieve_context("Immobilien", token_budget=1000) == []
    status = vault_service.get_vault_status(OWNER)
    assert status["reason"] == "onedrive_not_connected"
    od.reset_cache()


# ── Criterion 5: cache — second call within TTL doesn't re-hit Composio ──────
def test_second_call_within_ttl_does_not_call_composio_again(onedrive_env):
    calls = onedrive_env
    first = od.load_files()
    calls_after_first = len(calls)
    assert calls_after_first > 0
    assert first.status == od.STATUS_OK

    second = od.load_files()
    assert len(calls) == calls_after_first  # no new Composio calls
    assert second.files == first.files


def test_expired_ttl_refetches(onedrive_env, monkeypatch):
    calls = onedrive_env
    od.load_files()
    calls_after_first = len(calls)
    monkeypatch.setattr(od.settings, "VAULT_ONEDRIVE_CACHE_TTL_SECONDS", 0)
    od.load_files()
    assert len(calls) > calls_after_first  # TTL=0 forces a refetch


# ── Allow-/deny-list unit coverage ───────────────────────────────────────────
@pytest.mark.parametrize("rel,expected", [
    ("00-Jetzt.md", True),
    ("00-Index.md", True),
    ("20-Ziele.md", True),
    ("30-Projekte.md", True),
    ("70-Entscheidungen.md", True),
    ("Projekte/CommandPilot.md", True),
    ("Entscheidungen/Vault-Cloud.md", True),
    ("Projekte/Privat.md", False),       # deny exact
    ("40-Gesundheit.md", False),         # deny prefix
    ("40-Gesundheit-Reha.md", False),    # deny prefix sibling
    ("50-Menschen.md", False),           # deny prefix
    ("05-Inbox.md", False),              # not allow-listed
    ("Menschen/Enis.md", False),         # deny dir
    ("Daily/2026-09-25.md", False),      # deny dir
    ("Inbox/draft.md", False),           # deny dir
    ("Projekte/sub/Deep.md", False),     # nested beyond one level — not allowed
    ("Projekte/notes.txt", False),       # non-md
])
def test_is_allowed(rel, expected):
    assert od.is_allowed(rel) is expected
