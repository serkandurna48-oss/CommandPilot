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
