"""
CommandPilot — OneDrive Vault Source (via Composio)

Fetches the second-brain vault's *allow-listed* files live from OneDrive, for
deployments (Render) where the local vault folder from VAULT_PATH does not
exist. Used by vault_service when VAULT_SOURCE="onedrive"; the scoring/budget/
sources retrieval logic in vault_service is unchanged — only the file source
switches here.

Two Composio tools are used (slugs/params verified against the live Composio
tool schema, 01.10.2026):
  - ONE_DRIVE_LIST_FOLDER_CHILDREN — enumerate a folder's direct children
    (non-recursive), args `folder_path` (drive-root-relative, leading slash)
    + `use_me_drive=true`; paginated via `next_page_token`.
  - ONE_DRIVE_DOWNLOAD_FILE_BY_PATH — args `item_path` (drive-root-relative,
    NO leading slash) + `file_name`; returns `data.content.s3url`, a
    pre-authenticated URL we then GET for the raw bytes.

**Allow-list / deny-list live in this code, never read from the cloud.** The
deny-list is hard and beats the allow-list, and anything not explicitly
allowed is denied (default-deny). Denied folders (Menschen/Daily/Inbox) are
never even listed, and denied files are never downloaded — so sensitive notes
never leave OneDrive, even if a future allow-list change or a stray file would
otherwise expose them.

**Fail-closed** (same never-raises contract as vault_service / composio_client):
missing COMPOSIO_API_KEY/COMPOSIO_USER_ID, no connected OneDrive account, or any
fetch error → empty files + a status reason, one log line, never an exception
into the chat.
"""
from __future__ import annotations

import logging
import time
import urllib.request
from dataclasses import dataclass

from app.core.config import settings
from app.services.composio_client import get_client

logger = logging.getLogger(__name__)

_LIST_TOOL = "ONE_DRIVE_LIST_FOLDER_CHILDREN"
_DOWNLOAD_TOOL = "ONE_DRIVE_DOWNLOAD_FILE_BY_PATH"
_LIST_PAGE_SIZE = 200
_HTTP_TIMEOUT_SECONDS = 30

# Status values returned alongside the files dict.
STATUS_OK = "ok"
STATUS_NOT_CONNECTED = "not_connected"
STATUS_ERROR = "error"

# ── Allow-list (in code, never from the cloud) ──────────────────────────────
# Exact flat files at the vault root that may be read.
_ALLOWED_FLAT_FILES = {
    "00-Jetzt.md",
    "00-Index.md",
    "20-Ziele.md",
    "30-Projekte.md",
    "70-Entscheidungen.md",
}
# Whole subfolders whose *.md files may be read.
_ALLOWED_DIRS = ("Projekte", "Entscheidungen")

# ── Deny-list (hard — beats the allow-list) ─────────────────────────────────
_DENIED_DIRS = ("Menschen", "Daily", "Inbox")
_DENIED_EXACT = {"Projekte/Privat.md"}
# Flat-root filename prefixes that are always denied (e.g. "40-Gesundheit.md",
# "50-Menschen.md" and any sibling like "40-Gesundheit-Reha.md").
_DENIED_FLAT_PREFIXES = ("40-Gesundheit", "50-Menschen")


@dataclass(frozen=True)
class OneDriveLoad:
    """Result of a load attempt. `files` maps vault-relative posix paths
    (e.g. "00-Jetzt.md", "Projekte/CommandPilot.md") to file content; it is
    empty unless `status == STATUS_OK`."""
    files: dict[str, str]
    status: str


# ── In-memory TTL cache (single-tenant: one vault, one owner) ───────────────
_cache: tuple[float, OneDriveLoad] | None = None


def reset_cache() -> None:
    """Drop the cached snapshot — used by tests, and harmless in production."""
    global _cache
    _cache = None


def is_allowed(rel_path: str) -> bool:
    """True iff a vault-relative posix path may be read. Deny-list is checked
    first and wins; anything not explicitly allowed is denied."""
    parts = rel_path.split("/")
    top = parts[0]

    # Deny-list first — beats the allow-list.
    if rel_path in _DENIED_EXACT:
        return False
    if len(parts) == 1:
        if any(top.startswith(prefix) for prefix in _DENIED_FLAT_PREFIXES):
            return False
        return top in _ALLOWED_FLAT_FILES
    if top in _DENIED_DIRS:
        return False

    # Allow-list: a .md file directly inside an allowed subfolder.
    return len(parts) == 2 and top in _ALLOWED_DIRS and rel_path.endswith(".md")


def _normalized_root() -> str:
    """Vault root as a drive-root-relative path with a single leading slash,
    no trailing slash. "" / "/" → "/"."""
    stripped = settings.VAULT_ONEDRIVE_ROOT.strip("/")
    return f"/{stripped}" if stripped else "/"


def _drive_relative(rel_path: str) -> str:
    """Drive-root-relative path (no leading slash) that
    ONE_DRIVE_DOWNLOAD_FILE_BY_PATH expects for a vault-relative file."""
    base = settings.VAULT_ONEDRIVE_ROOT.strip("/")
    return f"{base}/{rel_path}" if base else rel_path


class _OneDriveFetchError(Exception):
    """Internal — a Composio call reported failure. Carries the raw message so
    load_files can classify it as not_connected vs. a generic error."""


def _execute(client, slug: str, arguments: dict) -> dict:
    result = client.tools.execute(
        slug,
        user_id=settings.COMPOSIO_USER_ID,
        arguments=arguments,
        # Same per-call version opt-out as notion_tasks_service (composio==0.22.0).
        version="latest",
        dangerously_skip_version_check=True,
    )
    result = result or {}
    if result.get("successful") is False:
        raise _OneDriveFetchError(str(result.get("error") or "")[:200])
    return result


def _http_get_text(url: str) -> str:
    """GET a pre-authenticated download URL and decode as UTF-8. Isolated so
    tests can monkeypatch it without real network access."""
    with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310 (trusted Composio/MS URL)
        return resp.read().decode("utf-8")


def _list_children(client, folder_path: str) -> list[dict]:
    items: list[dict] = []
    page_token: str | None = None
    while True:
        arguments: dict = {
            "folder_path": folder_path,
            "use_me_drive": True,
            "top": _LIST_PAGE_SIZE,
        }
        if page_token:
            arguments["page_token"] = page_token
        data = _execute(client, _LIST_TOOL, arguments).get("data") or {}
        items.extend(data.get("value") or [])
        page_token = data.get("next_page_token")
        if not page_token:
            break
    return items


def _download_text(client, rel_path: str) -> str | None:
    """Download one allowed file's content, or None if it can't be read
    (missing url / fetch or decode failure) — a single unreadable file is
    skipped, mirroring vault_service's local behavior, not failing the load."""
    try:
        data = _execute(
            client,
            _DOWNLOAD_TOOL,
            {"item_path": _drive_relative(rel_path), "file_name": rel_path.rsplit("/", 1)[-1]},
        ).get("data") or {}
        s3url = ((data.get("content") or {}).get("s3url"))
        if not s3url:
            logger.warning("onedrive_vault_service: no download url for %s — skipping", rel_path)
            return None
        return _http_get_text(s3url)
    except _OneDriveFetchError:
        raise
    except Exception as exc:  # decode / network error on a single file
        logger.warning(
            "onedrive_vault_service: could not download %s | %s: %s — skipping",
            rel_path, type(exc).__name__, str(exc)[:200],
        )
        return None


def _fetch_snapshot(client) -> dict[str, str]:
    files: dict[str, str] = {}
    root = _normalized_root()

    allowed_subdirs: list[str] = []
    for item in _list_children(client, root):
        name = item.get("name")
        if not name:
            continue
        if item.get("folder") is not None:
            # Only descend into allowed subfolders — denied dirs
            # (Menschen/Daily/Inbox) are never even listed.
            if name in _ALLOWED_DIRS:
                allowed_subdirs.append(name)
            continue
        if is_allowed(name):
            content = _download_text(client, name)
            if content is not None:
                files[name] = content

    for dirname in allowed_subdirs:
        subdir_path = f"{root.rstrip('/')}/{dirname}"
        for item in _list_children(client, subdir_path):
            name = item.get("name")
            if not name or item.get("folder") is not None:
                continue
            rel = f"{dirname}/{name}"
            if is_allowed(rel):
                content = _download_text(client, rel)
                if content is not None:
                    files[rel] = content

    return files


def _classify_error(message: str) -> str:
    """Best-effort split between "OneDrive not connected" and a generic error,
    so get_vault_status can report the more specific reason. Defaults to
    STATUS_ERROR when the message is not clearly a connection problem."""
    lowered = message.lower()
    if "connect" in lowered or "no active" in lowered or "no connected account" in lowered:
        return STATUS_NOT_CONNECTED
    return STATUS_ERROR


def load_files(force_refresh: bool = False) -> OneDriveLoad:
    """Allow-listed vault files from OneDrive, with an in-memory TTL cache.
    Never raises. Returns empty files with STATUS_NOT_CONNECTED (missing
    config / no connected account) or STATUS_ERROR (any fetch failure)."""
    global _cache

    if not settings.COMPOSIO_API_KEY or not settings.COMPOSIO_USER_ID:
        return OneDriveLoad({}, STATUS_NOT_CONNECTED)

    client = get_client()
    if client is None:
        return OneDriveLoad({}, STATUS_NOT_CONNECTED)

    now = time.monotonic()
    if not force_refresh and _cache is not None:
        cached_at, cached_load = _cache
        if now - cached_at < settings.VAULT_ONEDRIVE_CACHE_TTL_SECONDS:
            return cached_load

    try:
        files = _fetch_snapshot(client)
    except _OneDriveFetchError as exc:
        logger.warning("onedrive_vault_service: Composio reported failure | %s", str(exc)[:200])
        return OneDriveLoad({}, _classify_error(str(exc)))
    except Exception as exc:
        logger.warning(
            "onedrive_vault_service: fetch failed | %s: %s",
            type(exc).__name__, str(exc)[:200],
        )
        return OneDriveLoad({}, _classify_error(f"{type(exc).__name__}: {exc}"))

    load = OneDriveLoad(files, STATUS_OK)
    _cache = (now, load)
    return load
