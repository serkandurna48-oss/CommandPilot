"""
CommandPilot — Second-Brain Vault Retrieval

Reads the user's Obsidian vault (flat Markdown notes + YAML frontmatter on
entity notes) and surfaces the sections most relevant to a query, each tagged
with its source. Surface-agnostic: no knowledge of chat vs. daily-plan
callers. Read-only — never writes to the vault.

Keyword matching only, no embeddings, no vector DB. Frontmatter contract
(JARVIS-A1, Aufgabe 6 — precise on purpose, this was previously ambiguous):
frontmatter (type, status, priority, updated) is surfaced as plain text in
the base layer's per-entity summary line (see get_base_context) — it is NOT
a signal in hit-context scoring. retrieve_context/_score_section never reads
frontmatter; a query mentioning "active" scores no higher against a note
with status: active than against one without. Token counts are estimated as
len(text) // 4 — no tiktoken dependency.

Two layers, combined by get_context_for_query():
  - base context:  00-Index.md in full, plus title/frontmatter/first-line for
                    every entity note. Always included so open-ended queries
                    that share no vocabulary with the vault still get the
                    map of the user's projects/goals/people.
  - hit context:    keyword-scored section matches for the specific query,
                    scored on heading/filename/body tokens only (see
                    _score_section) — frontmatter plays no role here.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_ENTITY_DIRS = ("Projekte", "Menschen")
_BASE_INDEX_FILE = "00-Index.md"
_EXCLUDED_FILES = {"CLAUDE.md"}
_FRONTMATTER_KEYS = ("type", "status", "priority", "updated")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "this", "that", "with", "my", "i", "what", "how",
    "which", "it", "you", "your",
    "der", "die", "das", "und", "oder", "von", "zu", "in", "auf", "für",
    "ist", "sind", "war", "waren", "sein", "dieser", "diese", "dieses",
    "mit", "mein", "meine", "meinem", "ich", "was", "wie", "welche", "es",
    "ein", "eine", "einen",
    # "im" = "in dem" (JARVIS-Q1, Fall 7/8 finding): as common as "in", which
    # is already listed above — omitting it let it collide with nearly every
    # section in a real vault, drowning out genuine matches with noise.
    "im",
}

# A single incidental body-token match (score 1 — one shared word, no
# heading/filename hit, no repetition) is coincidence, not a real hit — a
# generic word like "hoch" or "Konto" appearing once in an unrelated note
# must not surface that note as if it answered the query (JARVIS-Q1, Fall
# 7/8). Genuine matches observed against the real vault score >= 2 (either a
# heading/filename hit, worth 3, or >= 2 body occurrences/tokens).
_MIN_HIT_SCORE = 2

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]+")


@dataclass(frozen=True)
class VaultMatch:
    text: str
    source_file: str
    source_heading: str
    score: float


def _vault_root(vault_path: str | None) -> Path | None:
    raw = vault_path if vault_path is not None else settings.VAULT_PATH
    if not raw:
        logger.info("vault_service: VAULT_PATH not configured — returning empty context")
        return None
    path = Path(raw)
    if not path.is_dir():
        logger.warning("vault_service: VAULT_PATH %r is not a readable directory", raw)
        return None
    return path


def _tokenize(text: str) -> list[str]:
    return [
        w for w in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
        if len(w) > 1 and w not in _STOPWORDS
    ]


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    frontmatter: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("-") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key in _FRONTMATTER_KEYS and value:
            frontmatter[key] = value
    return frontmatter, content[match.end():]


def _split_sections(body: str) -> list[tuple[str, str]]:
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        stripped = body.strip()
        return [("", stripped)] if stripped else []

    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        preamble = body[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        if text:
            sections.append((heading, text))
    return sections


def _score_section(query_tokens: set[str], heading: str, filename: str, body: str) -> float:
    heading_tokens = set(_tokenize(heading))
    filename_tokens = set(_tokenize(filename))
    body_counts = Counter(_tokenize(body))

    score = 0.0
    for token in query_tokens:
        if token in heading_tokens:
            score += 3
        if token in filename_tokens:
            score += 3
        score += body_counts.get(token, 0)
    return score


def _iter_content_files(root: Path):
    for file_path in sorted(root.glob("*.md")):
        if file_path.name not in _EXCLUDED_FILES:
            yield file_path
    for dirname in _ENTITY_DIRS:
        dir_path = root / dirname
        if dir_path.is_dir():
            yield from sorted(dir_path.glob("*.md"))


def _match_header(m: VaultMatch) -> str:
    """The "### Quelle: ..." line format_context_block prefixes each match with."""
    label = m.source_file if not m.source_heading else f"{m.source_file} — {m.source_heading}"
    return f"### Quelle: {label}\n"


def _cap_to_budget(matches: list[VaultMatch], token_budget: int) -> list[VaultMatch]:
    """
    Cap matches to token_budget, accounting for the fully formatted output —
    each match's "### Quelle: ..." header (see format_context_block) plus the
    "\\n\\n" separator between entries — not just the raw match text. Budgets
    are meant to bound what actually gets sent to the model, not an
    approximation of it (JARVIS-A1, Aufgabe 4).
    """
    budget_chars = max(token_budget, 0) * _CHARS_PER_TOKEN
    capped: list[VaultMatch] = []
    used = 0
    for m in matches:
        separator_len = 2 if capped else 0  # "\n\n" between entries, none before the first
        overhead = separator_len + len(_match_header(m))
        remaining = budget_chars - used - overhead
        if remaining <= 0:
            break
        if len(m.text) > remaining:
            truncated = VaultMatch(m.text[:remaining] + "…", m.source_file, m.source_heading, m.score)
            capped.append(truncated)
            used += overhead + len(truncated.text)
            break
        capped.append(m)
        used += overhead + len(m.text)
    return capped


_MAX_INDEX_BUDGET_SHARE = 0.5


def get_base_context(token_budget: int, vault_path: str | None = None) -> list[VaultMatch]:
    """
    00-Index.md (truncated to at most half of token_budget — see below),
    then one summary line per entity note (title/first line + type/status/
    priority/updated), capped to token_budget.
    Missing/unreadable vault → []. Never raises.

    00-Index.md's own text is pre-truncated to at most
    _MAX_INDEX_BUDGET_SHARE of the budget BEFORE the combined list goes
    through _cap_to_budget. Found live 24.09.2026
    (test_case_06_offene_frage_faellt_auf_basiskontext_zurueck): the real
    vault's index has grown to ~5.9KB, already bigger than the entire
    default base_token_budget (1200 tokens = 4800 chars) — _cap_to_budget
    alone would truncate the index to fill 100% of the budget and never
    even look at a single entity note, silently defeating this function's
    whole purpose ("map of the user's projects/goals/people", per the
    module docstring) as the index keeps growing. Reserving half the
    budget guarantees room for entity notes regardless of index size.
    """
    root = _vault_root(vault_path)
    if root is None:
        return []

    matches: list[VaultMatch] = []

    index_path = root / _BASE_INDEX_FILE
    if index_path.is_file():
        try:
            text = index_path.read_text(encoding="utf-8").strip()
            if text:
                max_index_chars = int(max(token_budget, 0) * _CHARS_PER_TOKEN * _MAX_INDEX_BUDGET_SHARE)
                if len(text) > max_index_chars:
                    text = text[:max_index_chars] + "…"
                matches.append(VaultMatch(text, _BASE_INDEX_FILE, "", score=0))
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("vault_service: could not read %s | %s", index_path, exc)

    for dirname in _ENTITY_DIRS:
        dir_path = root / dirname
        if not dir_path.is_dir():
            continue
        for file_path in sorted(dir_path.glob("*.md")):
            try:
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("vault_service: could not read %s | %s", file_path, exc)
                continue
            frontmatter, rest = _parse_frontmatter(content)
            first_line = next((l.strip() for l in rest.splitlines() if l.strip()), "")
            fm_str = ", ".join(f"{k}: {v}" for k, v in frontmatter.items())
            summary = first_line + (f" ({fm_str})" if fm_str else "")
            if summary:
                matches.append(VaultMatch(summary, f"{dirname}/{file_path.name}", "", score=0))

    return _cap_to_budget(matches, token_budget)


def retrieve_context(
    query: str, token_budget: int, vault_path: str | None = None
) -> list[VaultMatch]:
    """
    Keyword-scored section matches for query, capped to token_budget.
    Headings and filenames are weighted higher than body text (see
    _score_section). Frontmatter is stripped before scoring and plays no
    role in the score — it is not a query-weighting signal, only a
    base-context display field (see module docstring, JARVIS-A1, Aufgabe 6).
    Sections scoring below _MIN_HIT_SCORE are excluded — a lone incidental
    body-word match is coincidence, not a hit (JARVIS-Q1, Fall 7/8). Missing
    vault or empty query → [].
    Never raises.
    """
    root = _vault_root(vault_path)
    if root is None:
        return []

    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return []

    scored: list[VaultMatch] = []
    for file_path in _iter_content_files(root):
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("vault_service: could not read %s | %s", file_path, exc)
            continue
        _, body = _parse_frontmatter(content)
        rel_name = file_path.relative_to(root).as_posix()
        for heading, section_text in _split_sections(body):
            score = _score_section(query_tokens, heading, file_path.stem, section_text)
            if score >= _MIN_HIT_SCORE:
                scored.append(VaultMatch(section_text, rel_name, heading, score))

    scored.sort(key=lambda m: m.score, reverse=True)
    return _cap_to_budget(scored, token_budget)


def format_context_block(matches: list[VaultMatch]) -> str:
    """Render matches as a clearly delimited block, each entry tagged with its source."""
    if not matches:
        return ""
    return "\n\n".join(f"{_match_header(m)}{m.text}" for m in matches)


def _dedupe_sources(matches: list[VaultMatch]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    sources: list[dict] = []
    for m in matches:
        key = (m.source_file, m.source_heading)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"file": m.source_file, "heading": m.source_heading})
    return sources


def get_context_for_query(
    query: str,
    user_id: str | None = None,
    total_token_budget: int = 2200,
    base_token_budget: int = 1200,
    vault_path: str | None = None,
) -> tuple[str, list[dict], list[dict]]:
    """
    Combine base context (always present) with hit context (query-specific)
    into one formatted block sent to the model, plus two separate,
    deduplicated source lists: (hit_sources, base_sources), each shaped
    [{"file": ..., "heading": ...}, ...].

    hit_sources are the query-scored sections that actually carried the
    answer; base_sources are the always-present map-of-the-vault entries
    (00-Index.md + one line per entity note). Kept apart (JARVIS-A1,
    Aufgabe 5) because base context is large by design (14+ entries in a
    typical vault) and showing all of it as "sources" alongside the handful
    of sections that actually fed the answer is noise, not provenance — a
    caller building a user-facing sources list should default to showing
    only hit_sources. Both are still folded into the single formatted block,
    since the model needs the map-of-the-vault context regardless of what
    the UI chooses to surface.

    Empty/unreadable vault → ("", [], []). Never raises.

    base_token_budget is capped to total_token_budget (JARVIS-A1, Aufgabe 4)
    — a caller passing a small total_token_budget with the default
    base_token_budget=1200 gets a context block bounded by total_token_budget,
    not one that silently balloons to the base default regardless of what was
    asked for.

    Ownership gate (JARVIS-A1, Aufgabe 2; fail-closed since the same fix as
    is_personal_integrations_owner, app/core/config.py): user_id must match
    settings.VAULT_OWNER_USER_ID or this returns ("", [], []) without
    touching the filesystem — the caller must pass the requesting user's id
    through here, not assume the vault is theirs. An empty/unset
    VAULT_OWNER_USER_ID now means nobody passes, not everybody — an unset
    env var must never be the thing that makes a per-owner gate a no-op.
    """
    owner_id = settings.VAULT_OWNER_USER_ID
    if not owner_id or user_id != owner_id:
        logger.warning(
            "vault_service: user_id does not match VAULT_OWNER_USER_ID (or it is unset) — returning empty context | user_id=%r",
            user_id,
        )
        return "", [], []

    effective_base_budget = min(base_token_budget, total_token_budget)
    base_matches = get_base_context(effective_base_budget, vault_path)
    hits_budget = max(total_token_budget - base_token_budget, 0)
    hit_matches = retrieve_context(query, hits_budget, vault_path)

    block = format_context_block(base_matches + hit_matches)

    return block, _dedupe_sources(hit_matches), _dedupe_sources(base_matches)


def get_vault_status(user_id: str) -> dict:
    """Health check for the Home dashboard's data-source indicator — not
    context, no query. Deliberately does NOT reuse get_base_context/
    _cap_to_budget: those exist to build a bounded prompt block and, by
    design, (a) silently skip a file that fails to read (a status check
    must not report "ok" over a real read failure — reviewed 24.09.2026:
    the previous version did exactly that, since get_base_context()
    swallows per-file errors the same way it's supposed to for retrieval),
    and (b) can silently drop files once a token budget is exceeded (a
    status check's note count must be the real count, not "however many
    fit in a budget nobody asked for here").

    This function reads every note directly, counts every real success,
    and treats even one per-file read failure as ok=False — reason=
    "read_error" — while still reporting notes_found as the count that DID
    read cleanly, so a partial failure is visible as partial, not total.

    Same fail-closed ownership gate as get_context_for_query — a non-owner
    (or an unset VAULT_OWNER_USER_ID) gets reason="not_owner", never a
    filesystem check, exactly like the real read path would.

    Returns {ok, reason, notes_found, checked_at} — reason is one of
    "not_owner" | "not_configured" | "read_error" | None (ok=True has no
    reason).
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    owner_id = settings.VAULT_OWNER_USER_ID
    if not owner_id or user_id != owner_id:
        return {"ok": False, "reason": "not_owner", "notes_found": 0, "checked_at": checked_at}

    root = _vault_root(None)
    if root is None:
        return {"ok": False, "reason": "not_configured", "notes_found": 0, "checked_at": checked_at}

    notes_found = 0
    read_errors = 0

    index_path = root / _BASE_INDEX_FILE
    if index_path.is_file():
        try:
            index_path.read_text(encoding="utf-8")
            notes_found += 1
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("vault_service: status check could not read %s | %s", index_path, exc)
            read_errors += 1

    for dirname in _ENTITY_DIRS:
        dir_path = root / dirname
        if not dir_path.is_dir():
            continue
        for file_path in dir_path.glob("*.md"):
            try:
                file_path.read_text(encoding="utf-8")
                notes_found += 1
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("vault_service: status check could not read %s | %s", file_path, exc)
                read_errors += 1

    if read_errors > 0:
        return {"ok": False, "reason": "read_error", "notes_found": notes_found, "checked_at": checked_at}

    return {"ok": True, "reason": None, "notes_found": notes_found, "checked_at": checked_at}
