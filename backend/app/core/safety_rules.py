"""Backend-side safety rule enforcement for the Background Dev Team.

frontend/lib/safetyRules.ts is the *display* copy shown to Serkan in the UI
and baked into the generated runner prompt. This module is what actually
gets checked server-side when an ApprovalScope is created — the two are
intentionally separate files (display text vs. enforcement keywords) but
must stay conceptually in sync; see
docs/background-dev-team-system-design.md §5/§11 for the rationale and the
known limits of this approach (keyword matching on free-text fields is a
best-effort net, not a formal grammar — it catches the obvious cases, not
every possible phrasing).
"""

BLOCKED_ACTION_KEYWORDS: list[str] = [
    "deploy",
    "production data",
    "prod data",
    "secret",
    "send email",
    "e-mail senden",
    "email senden",
    "payment",
    "zahlung",
    "stripe",
    "reset --hard",
    "force push",
    "force-push",
    "clean -f",
    "direct to main",
    "direkt auf main",
    "push to main",
    "export user data",
    "userdaten exportieren",
]


def find_blocked_keyword(text: str) -> str | None:
    lowered = text.lower()
    for keyword in BLOCKED_ACTION_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def validate_approval_scope(allowed_actions: list[str], requires_approval: list[str]) -> None:
    """Raises ValueError if a repo-wide-blocked action was written into
    allowed_actions or requires_approval instead of blocked_actions.

    A scope may narrow the repo-wide defaults further; it may never smuggle
    a blocked action back in under a different list. This is checked at
    ApprovalScope creation time (see models/work_order.py), so a bad scope
    is rejected with a 422 before a work order can ever reference it.
    """
    for action in allowed_actions:
        hit = find_blocked_keyword(action)
        if hit:
            raise ValueError(
                f"'{action}' looks like a blocked action (matched keyword '{hit}') "
                "and cannot be placed in allowed_actions."
            )
    for action in requires_approval:
        hit = find_blocked_keyword(action)
        if hit:
            raise ValueError(
                f"'{action}' looks like a blocked action (matched keyword '{hit}') "
                "and cannot be placed in requires_approval — it belongs in "
                "blocked_actions and can never be approved within this system."
            )
