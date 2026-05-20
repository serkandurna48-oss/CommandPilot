import logging
from datetime import datetime

from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.services.ai_service import client as openai_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "commandpilot-api",
    }


@router.get("/health/ai")
async def ai_health_check(
    request: Request,
    ping: bool = Query(default=False),
):
    """
    Safe debug endpoint: confirms AI configuration is present.
    Never exposes key values.

    With ?ping=true: performs a real OpenAI models.list() call to verify network
    reachability. Requires the X-Debug-Token header to match the DEBUG_HEALTH_TOKEN
    env var (which must be non-empty). Returns 403 otherwise — the ping is never
    reachable from public/unauthenticated requests.
    """
    result: dict = {
        "openai_key_present": bool(settings.OPENAI_API_KEY),
        "openai_model": settings.OPENAI_MODEL,
        "debug_ai_prompt": settings.DEBUG_AI_PROMPT,
    }

    if ping:
        token = settings.DEBUG_HEALTH_TOKEN
        provided = request.headers.get("X-Debug-Token", "")
        if not token or not provided or provided != token:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        try:
            await openai_client.models.list()
            result["openai_reachable"] = True
        except Exception as exc:
            logger.warning(
                "Health ping: OpenAI unreachable | exc=%s | model=%s",
                type(exc).__name__,
                settings.OPENAI_MODEL,
            )
            result["openai_reachable"] = False
            result["openai_error_type"] = type(exc).__name__

    return result
