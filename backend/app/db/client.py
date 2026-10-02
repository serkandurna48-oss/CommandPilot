import time

import httpx
from supabase import create_client, Client, ClientOptions
from app.core.config import settings

_client: Client | None = None

# httpx errors that indicate a transient connection/protocol glitch — safe to
# retry for read-only (select) calls. NOT used for insert/update/rpc (those
# are never passed to retry_read).
_RETRY_ERRORS = (httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError)
_RETRY_MAX = 2
_RETRY_DELAY = 0.1


def get_db() -> Client:
    global _client
    if _client is None:
        # h2 is installed as a transitive dep, so postgrest-py's default
        # httpx.Client(http2=True) triggered HTTP/2 multiplexing — one
        # shared TCP connection for all concurrent FastAPI worker threads,
        # which is not thread-safe and caused sporadic ReadError/EAGAIN (11)
        # on Render (live 02.10.2026, httpcore/_sync/http2.py). Fix:
        # pass our own httpx.Client(http2=False) via ClientOptions so every
        # sub-client (auth, postgrest, storage) uses HTTP/1.1 with a
        # thread-safe connection pool instead of a shared HTTP/2 stream.
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            options=ClientOptions(httpx_client=httpx.Client(http2=False)),
        )
    return _client


def retry_read(fn):
    """Execute a supabase .select()...execute() callable with up to
    _RETRY_MAX retries on transient httpx network errors.

    Only pass read (select) callables — never insert/update/rpc.
    Those are mutable operations where a retry could cause double writes."""
    last_exc: Exception | None = None
    for attempt in range(_RETRY_MAX + 1):
        try:
            return fn()
        except _RETRY_ERRORS as exc:
            last_exc = exc
            if attempt < _RETRY_MAX:
                time.sleep(_RETRY_DELAY)
    raise last_exc  # type: ignore[misc]
