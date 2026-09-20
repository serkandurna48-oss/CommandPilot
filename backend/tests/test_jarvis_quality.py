"""
JARVIS-Q1 — Jarvis answer-quality safety net.

Ten deterministic cases guarding retrieval, the built context block, sources,
prompt instructions, user separation and the proposal/write boundary — this
is the safety net for the Command Layer, not a model-output test. Real model
behavior is flaky and is checked manually in the browser (see
docs/manual-e2e-checklist.md), never asserted here — no OpenAI call is made.

Cases 1-8 are bound to the real vault configured via VAULT_PATH (the user's
actual Obsidian vault — 40-Gesundheit.md, Menschen/Enis.md,
Projekte/CampPilot.md, 20-Ziele.md, 80-Begriffe.md must exist with real
content for them to mean anything). If VAULT_PATH is unset or unreadable,
they SKIP, not fail. Cases 9-10 exercise mechanics that don't depend on real
vault content (the ownership gate, the proposal/write boundary) and always
run.

Fall 10 (JARVIS-C1, Phase 7): updated from its original Q1 shape. Before C1,
a goal-oriented message could never produce suggested_actions at all. Since
C1, it may — but the chat endpoint itself must still never write a work
order; that only happens via the explicit POST .../suggested-actions/confirm
endpoint (see test_suggested_action_service.py for confirm/reject/idempotency
coverage). The invariant this guards is PROPOSAL != EXECUTION, not "no
suggestions ever."

Run:
    python -m pytest backend/tests/test_jarvis_quality.py -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# app.core.config.Settings resolves its "env_file=.env" relative to the
# process CWD, not to this file — when pytest runs from the repo root (as
# scripts/check.ps1 does), backend/.env is silently never found. Load it
# explicitly by absolute path so VAULT_PATH is picked up regardless of CWD;
# real env vars still win (load_dotenv default: does not override existing).
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_ROOT / ".env")

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services import vault_service  # noqa: E402
from app.prompts.jarvis_chat import SYSTEM_PROMPT  # noqa: E402


def _real_vault_path() -> str | None:
    """Path to the real configured vault (VAULT_PATH), or None if unset/unreadable."""
    raw = settings.VAULT_PATH
    if not raw or not Path(raw).is_dir():
        return None
    return raw


_VAULT_PATH = _real_vault_path()
requires_real_vault = pytest.mark.skipif(
    _VAULT_PATH is None,
    reason="VAULT_PATH not configured or not a readable directory — vault-bound quality case skipped, not failed",
)


def _query_real_vault(query: str) -> tuple[set[str], set[str]]:
    """(hit files, base files) for query against the real configured vault."""
    # If VAULT_OWNER_USER_ID is set locally, pass it through so the ownership
    # gate (see vault_service.get_context_for_query) doesn't swallow these
    # cases; if unset the gate is disabled and the value passed is moot.
    user_id = settings.VAULT_OWNER_USER_ID or None
    _, hit_sources, base_sources = vault_service.get_context_for_query(
        query, user_id=user_id, vault_path=_VAULT_PATH
    )
    return {s["file"] for s in hit_sources}, {s["file"] for s in base_sources}


# ── Wissensfälle 1-6: erwartete Quelle muss unter den Treffern sein ─────────────

@requires_real_vault
def test_case_01_reha_stand():
    hit_files, _ = _query_real_vault("Wie ist mein Reha-Stand?")
    assert "40-Gesundheit.md" in hit_files


@requires_real_vault
def test_case_02_wer_ist_enis():
    hit_files, _ = _query_real_vault("Wer ist Enis?")
    assert "Menschen/Enis.md" in hit_files


@requires_real_vault
def test_case_03_camppilot_kunden():
    hit_files, _ = _query_real_vault("Was ist CampPilot und wer sind die Kunden?")
    assert "Projekte/CampPilot.md" in hit_files


@requires_real_vault
def test_case_04_ziele_dieses_jahr():
    hit_files, _ = _query_real_vault("Was sind meine Ziele für dieses Jahr?")
    assert "20-Ziele.md" in hit_files


@requires_real_vault
def test_case_05_cp_s308_begriff():
    hit_files, _ = _query_real_vault("Was bedeutet CP-S308?")
    assert "80-Begriffe.md" in hit_files


@requires_real_vault
def test_case_06_offene_frage_faellt_auf_basiskontext_zurueck():
    # No vocabulary overlap with any note — the base context (00-Index.md +
    # at least one project note) must still carry the map of the vault.
    _, base_files = _query_real_vault("Woran sollte ich diese Woche arbeiten?")
    assert "00-Index.md" in base_files
    assert any(f.startswith("Projekte/") for f in base_files)


# ── Fehlendes Wissen 7-8: kein erfundener Treffer, Systemprompt zwingt Ehrlichkeit ──

@requires_real_vault
def test_case_07_stromverbrauch_keine_erfundene_quelle():
    hit_files, _ = _query_real_vault("Wie hoch war mein Stromverbrauch im August?")
    assert hit_files == set()
    assert "Erfinde nichts" in SYSTEM_PROMPT
    assert "offen und ehrlich" in SYSTEM_PROMPT


@requires_real_vault
def test_case_08_kontostand_keine_erfundene_quelle():
    hit_files, _ = _query_real_vault("Wie viel Geld ist auf meinem Konto?")
    assert hit_files == set()
    assert "Erfinde nichts" in SYSTEM_PROMPT
    assert "offen und ehrlich" in SYSTEM_PROMPT


# ── Fall 9: Benutzertrennung ─────────────────────────────────────────────────────
# Doesn't depend on real vault content — the ownership gate short-circuits
# before any file is read (see vault_service.get_context_for_query), so a
# synthetic fixture vault exercises it just as well. Always runs.

def test_case_09_user_id_mismatch_returns_empty_context(tmp_path, monkeypatch):
    (tmp_path / "00-Index.md").write_text("# Index\n", encoding="utf-8")
    monkeypatch.setattr(vault_service.settings, "VAULT_OWNER_USER_ID", "owner-1")

    block, hit_sources, base_sources = vault_service.get_context_for_query(
        "Wie ist mein Reha-Stand?", user_id="someone-else", vault_path=str(tmp_path)
    )

    assert block == ""
    assert hit_sources == []
    assert base_sources == []


# ── Fall 10: Aktionen ohne Bestätigung (Regressionsbasis für C1) ─────────────────

_FAKE_USER_ID = "user-1"


class Case10ProposalNeverWritesWithoutConfirmation(unittest.TestCase):
    """
    "Leg mir dafür zwei Work Orders an" — JARVIS-C1, Phase 7 update: the
    message MAY now produce suggested_actions (Phase 2 explicitly allows
    exactly two for a goal-oriented message). What Fall 10 actually guards,
    both before and after C1, is that the chat endpoint itself never writes
    a work order — confirmation is a separate, explicit call
    (POST /suggested-actions/confirm, see test_suggested_action_service.py).
    PROPOSAL != EXECUTION.
    """

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.auth import CurrentUser, get_current_user

        self.app = app
        self.get_current_user = get_current_user
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=_FAKE_USER_ID, email="test@example.com", workspace_id="ws-1"
        )

    def tearDown(self):
        self.app.dependency_overrides.pop(self.get_current_user, None)

    def test_chat_may_suggest_actions_but_never_writes_a_work_order(self):
        import app.routers.jarvis as jarvis_router
        from app.models.jarvis import JarvisChatAI, SuggestedAction
        from app.services import work_order_service

        two_suggestions = [
            SuggestedAction(
                title="CampPilot Onboarding-Flow für JK vorbereiten",
                description="Onboarding-Schritte für den Kunden JK dokumentieren und in CampPilot abbilden.",
                risk="medium",
                requires_approval=True,
            ),
            SuggestedAction(
                title="CampPilot Demo-Daten für JK anlegen",
                description="Beispieldaten für eine JK-Demo in CampPilot vorbereiten.",
                risk="low",
                requires_approval=False,
            ),
        ]

        with patch.object(jarvis_router, "ensure_user_workspace", return_value={"workspace_id": "ws-1", "profile": {}}), \
             patch.object(jarvis_router, "check_daily_cap", return_value=None), \
             patch.object(jarvis_router.vault_service, "get_context_for_query", return_value=("", [], [])), \
             patch.object(
                 jarvis_router, "generate_chat_reply",
                 return_value=(
                     JarvisChatAI(reply="Hier zwei Vorschläge zur Bestätigung.", suggested_actions=two_suggestions),
                     50, 20,
                 ),
             ), \
             patch.object(jarvis_router, "log_ai_usage", return_value=None), \
             patch.object(work_order_service, "create_work_order") as mock_create_work_order, \
             patch.object(work_order_service, "append_activity_log") as mock_append_activity_log:
            resp = self.client.post(
                "/api/jarvis/chat",
                json={"message": "Leg mir dafür zwei Work Orders an", "history": []},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["suggested_actions"]), 2)
        # The chat response can carry proposals — it must never itself be
        # the thing that creates a work order or logs its activity.
        mock_create_work_order.assert_not_called()
        mock_append_activity_log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
