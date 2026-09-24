from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": found 23.09.2026 the hard way — a stray, unrelated
    # variable in backend/.env (COMMANDPILOT_API_TOKEN, meant for
    # scripts/run_work_order_daemon.py's shell environment, not this file)
    # made pydantic's strict default (extra="forbid") crash the ENTIRE
    # backend on startup with a validation error, not just fail to read
    # that one value. A config file with one unrelated line in it is a
    # completely ordinary user mistake — it must never take the whole API
    # down. Unknown keys are silently ignored, exactly like an unset key
    # already is for every Optional/defaulted field below.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    OPENAI_API_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"
    OPENAI_MODEL: str = "gpt-4o"
    # Set to true in .env to log review context metadata (never logs user content)
    DEBUG_AI_PROMPT: bool = False
    # Optional: set a secret value to enable the /api/health/ai?ping=true probe.
    # If empty (default), the ping probe is disabled and returns 403.
    DEBUG_HEALTH_TOKEN: str = ""
    # Absolute path to the second-brain Obsidian vault (read-only). Empty/unset
    # or unreadable → vault_service returns empty context, never raises.
    VAULT_PATH: str = ""
    # Single-tenant ownership gate (JARVIS-A1, Aufgabe 2): if set, the vault
    # is only readable for requests where CurrentUser.id equals this value —
    # a request from any other user_id gets an empty context, not the vault
    # owner's notes. Empty/unset (default) → no gate, behaves as before this
    # was introduced. Not a per-user vault system — one vault, one owner.
    VAULT_OWNER_USER_ID: str = ""
    # Composio-managed access to external context sources (Google Calendar,
    # Outlook, Notion) for Jarvis chat — see app/services/google_calendar_service.py,
    # outlook_calendar_service.py, and notion_tasks_service.py. Empty/unset
    # (default) -> all return empty context, no network calls, chat behaves
    # exactly as before this existed.
    COMPOSIO_API_KEY: str = ""
    # The Composio user_id whose Google Calendar / Notion accounts are
    # connected. Single-tenant, mirrors VAULT_OWNER_USER_ID: one set of
    # external accounts, one owner — not a per-Supabase-user mapping.
    COMPOSIO_USER_ID: str = ""
    # Notion database id of the "My Tasks" database queried by
    # notion_tasks_service. Empty -> notion_tasks_service returns empty context.
    NOTION_TASKS_DATABASE_ID: str = ""


settings = Settings()


def is_personal_integrations_owner(user_id: str) -> bool:
    """Gate for the three globally-single-tenant external context sources
    (Google Calendar, Outlook, Notion) — reuses VAULT_OWNER_USER_ID as the
    one CommandPilot/Supabase user_id allowed to see them, exactly like
    vault_service's own internal gate already does for the vault itself.
    These three services (unlike vault_service) take no user_id parameter
    at all — they're one Composio-connected identity for the whole backend
    process — so the gate has to live at the call site (routers/jarvis.py,
    routers/plans.py) instead of inside each service.

    Found live 23.09.2026 via a real second test account: with
    VAULT_OWNER_USER_ID unset (the actual state of backend/.env at the
    time), a completely unrelated authenticated user's Jarvis chat returned
    the vault owner's real Outlook calendar event and real personal Notion
    tasks (medical/insurance/tax items) verbatim — a live, reproducible
    multi-tenant data leak, not a theoretical one. Same fail-open shape as
    vault_service's own comment already warned about for the vault alone;
    VAULT_OWNER_USER_ID being unset silently disabled that gate too.

    Empty/unset VAULT_OWNER_USER_ID (default) -> returns False for
    everyone, i.e. these sources are now off for all users until it's set
    — matches "fail closed" rather than the previous fail-open behavior.
    This is a stopgap for single-tenant beta (CLAUDE.md's open decision:
    "Vault/Kalender/Notion: Single-Tenant beibehalten (Beta = nur Serkan)
    oder pro Nutzer machen?"), not a real per-user integration system.
    """
    return bool(settings.VAULT_OWNER_USER_ID) and user_id == settings.VAULT_OWNER_USER_ID
