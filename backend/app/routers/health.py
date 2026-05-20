from datetime import datetime

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "commandpilot-api",
    }


@router.get("/health/ai")
def ai_health_check():
    """
    Safe debug endpoint: confirms AI configuration is present.
    Never exposes key values.
    """
    return {
        "openai_key_present": bool(settings.OPENAI_API_KEY),
        "openai_model": settings.OPENAI_MODEL,
        "debug_ai_prompt": settings.DEBUG_AI_PROMPT,
    }
