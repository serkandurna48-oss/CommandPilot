from supabase import create_client, Client
from app.core.config import settings

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _client
