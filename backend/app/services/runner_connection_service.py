"""
CommandPilot — Runner Connections (guided pairing, 23.09.2026)

Replaces "copy a Supabase session token out of browser DevTools" for
scripts/run_work_order_daemon.py with a device-flow-shaped pairing: the
runner gets a token immediately but it authorizes nothing until a human,
already logged into the web app, approves the matching short user_code.
See supabase/migrations/017_runner_connections.sql's header comment for the
full flow and the reasoning behind each design choice below.

Token hashing uses stdlib hashlib.sha256 — no bespoke cryptography, matching
CLAUDE.md's general "don't invent, use established primitives" stance. The
raw token is generated with secrets.token_urlsafe (cryptographically strong,
stdlib) and returned to the caller exactly once, at creation time; only its
hash is ever persisted.
"""
from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone

from app.db.client import get_db

# Prefix lets app.auth.get_current_user() recognize a runner token with a
# plain string comparison BEFORE touching the database — a real Supabase
# JWT never starts with this, so the fast path costs normal frontend
# requests nothing extra.
RUNNER_TOKEN_PREFIX = "cprun_"

_PAIRING_TTL = timedelta(minutes=10)
# Excludes visually ambiguous characters (0/O, 1/I/L) — this code is read
# off a terminal and typed into a browser by a human under mild time
# pressure (10-minute window), not entered by a machine.
_USER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_user_code() -> str:
    half = lambda: "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(4))
    return f"{half()}-{half()}"


def create_pairing_request(label: str | None) -> dict:
    """Step 1 of the pairing flow — called by the runner itself, no auth.
    Generates and returns the actual runner_token right away; the row it's
    hashed into starts with user_id/workspace_id NULL, so possessing this
    token is not yet enough to do anything (every consuming lookup requires
    user_id IS NOT NULL — see app.auth._resolve_runner_token)."""
    db = get_db()
    raw_token = RUNNER_TOKEN_PREFIX + secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    connection = (
        db.table("runner_connections")
        .insert({"label": label or "Lokaler Runner", "token_hash": token_hash})
        .execute()
        .data[0]
    )

    user_code = _generate_user_code()
    expires_at = _now() + _PAIRING_TTL
    db.table("runner_pairing_requests").insert({
        "connection_id": connection["id"],
        "user_code": user_code,
        "status": "pending",
        "expires_at": expires_at.isoformat(),
    }).execute()

    return {
        "user_code": user_code,
        "runner_token": raw_token,
        "expires_in_seconds": int(_PAIRING_TTL.total_seconds()),
        "poll_interval_seconds": 3,
    }


def _find_pending_request(user_code: str) -> dict | None:
    db = get_db()
    # maybe_single().execute() returns None outright (not a response object
    # with .data=None) when zero rows match — postgrest-py 2.30.0 behavior.
    # An unmatched/unknown code is the expected common case here (typo,
    # already-approved, expired-and-cleaned-up), not an error.
    response = (
        db.table("runner_pairing_requests")
        .select("*")
        .eq("user_code", user_code.strip().upper())
        .eq("status", "pending")
        .maybe_single()
        .execute()
    )
    row = response.data if response else None
    if not row:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if _now() >= expires_at:
        db.table("runner_pairing_requests").update({"status": "expired"}).eq("id", row["id"]).execute()
        return None
    return row


def approve_pairing(user_id: str, workspace_id: str | None, user_code: str, label: str | None) -> dict | None:
    """Step 2 — called from an authenticated browser session only (the
    router depends on get_current_browser_user for this endpoint — a runner
    token is explicitly rejected there, see that dependency's docstring).
    Binds the already-issued token to this real account. Returns None if
    user_code is unknown/already resolved/expired, so the router can 404
    rather than imply something was approved when nothing was.

    Two concurrent approvals of the same code both pass the pending check
    above before either has written anything — _find_pending_request alone
    is not enough to pick a single winner. The actual binding below is an
    atomic compare-and-set: `WHERE id = ... AND user_id IS NULL` only
    matches (and only returns a row) for whichever caller's UPDATE commits
    first; Postgres's row-level locking serializes the two, so the second
    one's WHERE re-evaluates against the now-non-NULL user_id and matches
    zero rows. That caller gets None back here, same as an unknown code.
    """
    db = get_db()
    pending = _find_pending_request(user_code)
    if not pending:
        return None

    update: dict = {"user_id": user_id, "workspace_id": workspace_id}
    if label:
        update["label"] = label
    connection = (
        db.table("runner_connections")
        .update(update)
        .eq("id", pending["connection_id"])
        .is_("user_id", "null")
        .execute()
        .data
    )
    if not connection:
        return None
    db.table("runner_pairing_requests").update({"status": "approved"}).eq("id", pending["id"]).execute()
    return connection[0]


def poll_pairing_status(user_code: str) -> str:
    """Step 3 — called by the runner, no auth (it doesn't have a real
    session; that's the entire point). Only ever reveals a coarse status
    string, never any row contents."""
    db = get_db()
    response = (
        db.table("runner_pairing_requests")
        .select("status, expires_at")
        .eq("user_code", user_code.strip().upper())
        .maybe_single()
        .execute()
    )
    row = response.data if response else None
    if not row:
        return "not_found"
    if row["status"] == "pending" and _now() >= datetime.fromisoformat(row["expires_at"]):
        db.table("runner_pairing_requests").update({"status": "expired"}).eq(
            "user_code", user_code.strip().upper()
        ).execute()
        return "expired"
    return row["status"]


def list_connections_for_user(user_id: str) -> list[dict]:
    db = get_db()
    return (
        db.table("runner_connections")
        .select("id, label, created_at, last_used_at, revoked_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def revoke_connection(user_id: str, connection_id: str) -> bool:
    """Ownership-checked in the same query, not as a separate lookup — a
    connection_id belonging to a different user_id matches zero rows and
    silently updates nothing, exactly like require_owned_record's 404
    pattern does for work_orders elsewhere in this codebase."""
    db = get_db()
    result = (
        db.table("runner_connections")
        .update({"revoked_at": _now().isoformat()})
        .eq("id", connection_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)
