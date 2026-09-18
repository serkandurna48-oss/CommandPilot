import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user
from app.core.config import settings
from app.models.jarvis import JarvisChatRequest, JarvisChatResponse, SourceRef
from app.services import vault_service
from app.services.ai_service import AIGenerationError, generate_chat_reply
from app.services.usage_service import (
    DailyCapExceededError,
    calculate_cost_usd,
    check_daily_cap,
    log_ai_usage,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_AI_ERROR_MESSAGES: dict[str, str] = {
    "OPENAI_AUTH_FAILED": "Jarvis ist nicht verfügbar: API-Key-Problem.",
    "OPENAI_CONNECTION_ERROR": "Antwort fehlgeschlagen: KI-Dienst nicht erreichbar. Bitte gleich nochmal versuchen.",
    "OPENAI_RATE_LIMITED": "Jarvis ist gerade stark ausgelastet. Bitte gleich nochmal versuchen.",
    "OPENAI_QUOTA_EXCEEDED": "Jarvis ist nicht verfügbar: API-Kontingent aufgebraucht.",
    "AI_JSON_INVALID": "Antwort fehlgeschlagen: unerwartetes Format. Bitte nochmal versuchen.",
    "AI_SCHEMA_INVALID": "Antwort fehlgeschlagen: unerwartete Struktur. Bitte nochmal versuchen.",
    "UNKNOWN_AI_ERROR": "Antwort fehlgeschlagen. Bitte nochmal versuchen.",
}


@router.post("/chat", response_model=JarvisChatResponse)
async def chat(
    req: JarvisChatRequest,
    user: CurrentUser = Depends(get_current_user),
):
    # Mirrors routers/plans.py: bootstraps profile/workspace, resolves a
    # verified workspace_id for usage logging.
    try:
        setup = ensure_user_workspace(user)
        effective_workspace_id = setup.get("workspace_id")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "ensure_user_workspace failed unexpectedly | %s: %s",
            type(exc).__name__,
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "USER_SETUP_FAILED",
                "message": "Account setup ist unvollständig. Bitte Seite neu laden und nochmal versuchen.",
            },
        )

    # Same soft daily spending cap as daily-plan generation — chat is called
    # far more often than the once-a-day plan generation, so without this
    # check it is an unbounded cost path.
    request_date = datetime.now(timezone.utc).date()
    try:
        check_daily_cap(user.id, request_date)
    except DailyCapExceededError as exc:
        logger.warning(
            "Daily cap reached — aborting chat before AI call | user_id=%s | spend=%s | cap=%s",
            user.id, exc.current_spend, exc.cap,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "code": "DAILY_SPEND_CAP_REACHED",
                "current_spend": str(exc.current_spend),
                "cap": str(exc.cap),
                "resets_at": exc.resets_at,
                "message": "Tageslimit erreicht. Bitte morgen wieder versuchen.",
            },
        )

    # ── Retrieve second-brain context (non-fatal) ────────────────────────────
    context_block = ""
    vault_sources: list[dict] = []
    try:
        context_block, vault_sources = vault_service.get_context_for_query(req.message)
        logger.info("Vault context retrieved | sources=%d", len(vault_sources))
    except Exception as exc:
        logger.warning(
            "Vault context fetch failed | %s: %s — continuing without vault context",
            type(exc).__name__,
            str(exc)[:100],
        )

    # ── Generate reply via AI ─────────────────────────────────────────────────
    history = [turn.model_dump() for turn in req.history]
    try:
        reply_text, input_tokens, output_tokens = await generate_chat_reply(
            req.message, history, context_block
        )
    except AIGenerationError as exc:
        logger.error("Jarvis chat generation failed | code=%s | %s", exc.code, str(exc))
        if exc.input_tokens or exc.output_tokens:
            try:
                _fail_cost = calculate_cost_usd(settings.OPENAI_MODEL, exc.input_tokens, exc.output_tokens)
                log_ai_usage(
                    user_id=user.id,
                    model=settings.OPENAI_MODEL,
                    input_tokens=exc.input_tokens,
                    output_tokens=exc.output_tokens,
                    cost_usd=_fail_cost,
                    request_date=request_date,
                    workspace_id=effective_workspace_id,
                    plan_id=None,
                )
            except Exception as log_exc:
                logger.error(
                    "Failed to log AI usage on error path | %s: %s",
                    type(log_exc).__name__, str(log_exc)[:200],
                )
        raise HTTPException(
            status_code=502,
            detail={
                "code": exc.code,
                "message": _AI_ERROR_MESSAGES.get(exc.code, "Antwort fehlgeschlagen. Bitte nochmal versuchen."),
            },
        )
    except Exception as exc:
        logger.error(
            "Unexpected error during chat generation | %s: %s",
            type(exc).__name__,
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "UNKNOWN_AI_ERROR",
                "message": "Antwort fehlgeschlagen. Bitte nochmal versuchen.",
            },
        )

    # ── Log AI usage ──────────────────────────────────────────────────────────
    try:
        cost_usd = calculate_cost_usd(settings.OPENAI_MODEL, input_tokens, output_tokens)
    except ValueError as exc:
        logger.error(
            "Pricing not configured for model %r — cannot log usage or enforce cap | %s",
            settings.OPENAI_MODEL, exc,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PRICING_NOT_CONFIGURED",
                "message": "Antwort fehlgeschlagen: Server-Konfigurationsfehler.",
            },
        ) from exc
    logger.info(
        "AI usage | model=%s | input=%d | output=%d | cost_usd=%s",
        settings.OPENAI_MODEL, input_tokens, output_tokens, cost_usd,
    )
    log_ai_usage(
        user_id=user.id,
        model=settings.OPENAI_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        request_date=request_date,
        workspace_id=effective_workspace_id,
        plan_id=None,
    )

    return JarvisChatResponse(
        reply=reply_text,
        sources=[SourceRef(source_file=s["file"], source_heading=s["heading"]) for s in vault_sources],
        suggested_actions=[],  # v1: always empty — see app/models/jarvis.py
    )
