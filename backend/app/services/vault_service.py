"""
CommandPilot — Second-Brain Vault Retrieval

Reads the user's Obsidian vault (flat Markdown notes + YAML frontmatter on
entity notes) and surfaces the sections most relevant to a query, each tagged
with its source. Surface-agnostic: no knowledge of chat vs. daily-plan
callers. Read-only — never writes to the vault.

Keyword/frontmatter matching, no embeddings, no vector DB. Token counts are
estimated as len(text) // 4 — no tiktoken dependency.

Two layers, combined by get_context_for_query():
  - base context:  00-Index.md in full, plus title/frontmatter/first-line for
                    every entity note. Always included so open-ended queries
                    that share no vocabulary with the vault still get the
                    map of the user's projects/goals/people.
  - hit context:    keyword-scored section matches for the specific query.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
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
    "mit", "mein", "meine", "ich", "was", "wie", "welche", "es", "ein",
    "eine", "einen",
}

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


def _cap_to_budget(matches: list[VaultMatch], token_budget: int) -> list[VaultMatch]:
    budget_chars = max(token_budget, 0) * _CHARS_PER_TOKEN
    capped: list[VaultMatch] = []
    used = 0
    for m in matches:
        remaining = budget_chars - used
        if remaining <= 0:
            break
        if len(m.text) > remaining:
            capped.append(VaultMatch(m.text[:remaining] + "…", m.source_file, m.source_heading, m.score))
            break
        capped.append(m)
        used += len(m.text)
    return capped


def get_base_context(token_budget: int, vault_path: str | None = None) -> list[VaultMatch]:
    """
    00-Index.md in full, then one summary line per entity note (title/first
    line + type/status/priority/updated), capped to token_budget.
    Missing/unreadable vault → []. Never raises.
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
                matches.append(VaultMatch(text, _BASE_INDEX_FILE, "", score=0))
        except OSError as exc:
            logger.warning("vault_service: could not read %s | %s", index_path, exc)

    for dirname in _ENTITY_DIRS:
        dir_path = root / dirname
        if not dir_path.is_dir():
            continue
        for file_path in sorted(dir_path.glob("*.md")):
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError as exc:
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
    Keyword/frontmatter-weighted section matches for query, capped to
    token_budget. Headings and filenames are weighted higher than body text.
    Zero-score sections are excluded. Missing vault or empty query → [].
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
        except OSError as exc:
            logger.warning("vault_service: could not read %s | %s", file_path, exc)
            continue
        _, body = _parse_frontmatter(content)
        rel_name = file_path.relative_to(root).as_posix()
        for heading, section_text in _split_sections(body):
            score = _score_section(query_tokens, heading, file_path.stem, section_text)
            if score > 0:
                scored.append(VaultMatch(section_text, rel_name, heading, score))

    scored.sort(key=lambda m: m.score, reverse=True)
    return _cap_to_budget(scored, token_budget)


def format_context_block(matches: list[VaultMatch]) -> str:
    """Render matches as a clearly delimited block, each entry tagged with its source."""
    if not matches:
        return ""
    parts = []
    for m in matches:
        label = m.source_file if not m.source_heading else f"{m.source_file} — {m.source_heading}"
        parts.append(f"### Quelle: {label}\n{m.text}")
    return "\n\n".join(parts)


def get_context_for_query(
    query: str,
    user_id: str | None = None,
    total_token_budget: int = 2200,
    base_token_budget: int = 1200,
    vault_path: str | None = None,
) -> tuple[str, list[dict]]:
    """
    Combine base context (always present) with hit context (query-specific)
    into one formatted block plus a deduplicated source list
    ([{"file": ..., "heading": ...}, ...]).
    Empty/unreadable vault → ("", []). Never raises.

    Ownership gate (JARVIS-A1, Aufgabe 2): if settings.VAULT_OWNER_USER_ID is
    set and user_id doesn't match it, returns ("", []) without touching the
    filesystem — the caller must pass the requesting user's id through here,
    not assume the vault is theirs. An empty/unset VAULT_OWNER_USER_ID
    disables the gate entirely (pre-existing behavior).
    """
    owner_id = settings.VAULT_OWNER_USER_ID
    if owner_id and user_id != owner_id:
        logger.warning(
            "vault_service: user_id does not match VAULT_OWNER_USER_ID — returning empty context | user_id=%r",
            user_id,
        )
        return "", []

    base_matches = get_base_context(base_token_budget, vault_path)
    hits_budget = max(total_token_budget - base_token_budget, 0)
    hit_matches = retrieve_context(query, hits_budget, vault_path)

    all_matches = base_matches + hit_matches
    block = format_context_block(all_matches)

    seen: set[tuple[str, str]] = set()
    sources: list[dict] = []
    for m in all_matches:
        key = (m.source_file, m.source_heading)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"file": m.source_file, "heading": m.source_heading})

    return block, sources
