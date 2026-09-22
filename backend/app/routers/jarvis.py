import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user
from app.core.config import settings
from app.models.jarvis import (
    JarvisChatRequest,
    JarvisChatResponse,
    SourceRef,
    SuggestedActionDecisionListItem,
    SuggestedActionDecisionListResponse,
    SuggestedActionDecisionRequest,
    SuggestedActionDecisionResponse,
)
from app.services import (
    google_calendar_service,
    notion_tasks_service,
    outlook_calendar_service,
    suggested_action_service,
    vault_service,
    work_orders_context_service,
)
from app.services.ai_service import AIGenerationError, generate_chat_reply
from app.services.suggested_action_service import AlreadyDecidedError
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

    # Same rule as routers/plans.py: language is always taken from the user's
    # profile, never the request body — profile.language is the single
    # source of truth. Previously missing here entirely, which is why
    # switching the UI language left Jarvis chat replies stuck in German.
    _profile_lang = (setup.get("profile") or {}).get("language") or "en"
    effective_language = _profile_lang if _profile_lang in ("en", "de") else "en"

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
    hit_sources: list[dict] = []
    base_sources: list[dict] = []
    try:
        context_block, hit_sources, base_sources = vault_service.get_context_for_query(req.message, user.id)
        logger.info(
            "Vault context retrieved | hit_sources=%d | base_sources=%d",
            len(hit_sources), len(base_sources),
        )
    except Exception as exc:
        logger.warning(
            "Vault context fetch failed | %s: %s — continuing without vault context",
            type(exc).__name__,
            str(exc)[:100],
        )

    # ── Retrieve external context: calendars + tasks (non-fatal) ─────────────
    # Same "never raises" contract as vault_service above — all services
    # already return "" on missing Composio config, so this try/except only
    # guards against an unexpected failure inside them (defense in depth, not
    # the primary empty-on-missing-config path). Google and Outlook are two
    # independent calendar sources (CLAUDE.md § Jarvis) — either, both, or
    # neither may have a connected account; each is fetched and merged
    # regardless of whether the other succeeded.
    google_calendar_block = ""
    google_calendar_sources: list[dict] = []
    try:
        google_calendar_block, google_calendar_sources = google_calendar_service.get_context()
    except Exception as exc:
        logger.warning(
            "Google Calendar context fetch failed | %s: %s — continuing without it",
            type(exc).__name__,
            str(exc)[:100],
        )

    outlook_calendar_block = ""
    outlook_calendar_sources: list[dict] = []
    try:
        outlook_calendar_block, outlook_calendar_sources = outlook_calendar_service.get_context()
    except Exception as exc:
        logger.warning(
            "Outlook Calendar context fetch failed | %s: %s — continuing without it",
            type(exc).__name__,
            str(exc)[:100],
        )

    calendar_block = "\n\n".join(b for b in (google_calendar_block, outlook_calendar_block) if b)
    calendar_sources = google_calendar_sources + outlook_calendar_sources

    tasks_block = ""
    task_sources: list[dict] = []
    try:
        tasks_block, task_sources = notion_tasks_service.get_context()
    except Exception as exc:
        logger.warning(
            "Notion tasks context fetch failed | %s: %s — continuing without task context",
            type(exc).__name__,
            str(exc)[:100],
        )

    # ── Retrieve work orders: CommandPilot's own DB, not an external source
    # (non-fatal) ──────────────────────────────────────────────────────────
    # Without this, Jarvis had no way to know about real Work Orders at all
    # and would answer "work order" questions from whatever happened to be
    # worded similarly in the vault/Notion tasks — wrong source, wrong
    # answer (see CLAUDE.md § Jarvis, "KSV Baunatal" mix-up, 22.09.2026).
    work_orders_block = ""
    work_order_sources: list[dict] = []
    try:
        work_orders_block, work_order_sources = work_orders_context_service.get_context(user.id)
    except Exception as exc:
        logger.warning(
            "Work orders context fetch failed | %s: %s — continuing without it",
            type(exc).__name__,
            str(exc)[:100],
        )

    context_block = "\n\n".join(b for b in (context_block, calendar_block, tasks_block, work_orders_block) if b)

    # ── Generate reply via AI ─────────────────────────────────────────────────
    history = [turn.model_dump() for turn in req.history]
    try:
        chat_ai, input_tokens, output_tokens = await generate_chat_reply(
            req.message, history, context_block, effective_language
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
        reply=chat_ai.reply,
        sources=[SourceRef(source_file=s["file"], source_heading=s["heading"]) for s in hit_sources],
        base_sources=[SourceRef(source_file=s["file"], source_heading=s["heading"]) for s in base_sources],
        calendar_sources=[SourceRef(source_file=s["file"], source_heading=s["heading"]) for s in calendar_sources],
        task_sources=[SourceRef(source_file=s["file"], source_heading=s["heading"]) for s in task_sources],
        work_order_sources=[SourceRef(source_file=s["file"], source_heading=s["heading"]) for s in work_order_sources],
        # Proposals only — nothing is written here. See suggested_action_service
        # and the confirm/reject endpoints below for the only place a
        # suggestion can become a real work order (JARVIS-C1).
        suggested_actions=chat_ai.suggested_actions,
    )


@router.get("/suggested-actions/decisions", response_model=SuggestedActionDecisionListResponse)
async def list_suggested_action_decisions(
    user: CurrentUser = Depends(get_current_user),
):
    rows = suggested_action_service.list_decisions(user.id)
    return SuggestedActionDecisionListResponse(
        decisions=[
            SuggestedActionDecisionListItem(
                id=row["id"],
                decision=row["decision"],
                title=row["title"],
                team_type=row.get("team_type"),
                target_repo_name=row.get("target_repo_name"),
                risk=row.get("risk"),
                requires_approval=row.get("requires_approval"),
                sources=[SourceRef(**s) for s in (row.get("sources") or [])],
                work_order_id=row.get("work_order_id"),
                created_at=row["created_at"],
            )
            for row in rows
        ]
    )


@router.post("/suggested-actions/confirm", response_model=SuggestedActionDecisionResponse)
async def confirm_suggested_action(
    req: SuggestedActionDecisionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        setup = ensure_user_workspace(user)
        effective_workspace_id = setup.get("workspace_id")
        profile = setup.get("profile") or {}
        created_by = profile.get("display_name") or user.email or user.id
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

    try:
        result = suggested_action_service.confirm_suggested_action(
            user.id, effective_workspace_id, created_by, req.action, req.request_id
        )
    except AlreadyDecidedError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ALREADY_DECIDED",
                "message": "Dieser Vorschlag wurde bereits entschieden.",
                "decision": exc.existing_decision,
                "work_order_id": exc.work_order_id,
            },
        )
    except Exception as exc:
        logger.error(
            "Confirm suggested action failed | %s: %s",
            type(exc).__name__, str(exc)[:200],
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CONFIRM_FAILED",
                "message": "Bestätigen fehlgeschlagen. Bitte nochmal versuchen.",
            },
        )

    return SuggestedActionDecisionResponse(**result)


@router.post("/suggested-actions/reject", response_model=SuggestedActionDecisionResponse)
async def reject_suggested_action(
    req: SuggestedActionDecisionRequest,
    user: CurrentUser = Depends(get_current_user),
):
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

    try:
        result = suggested_action_service.reject_suggested_action(
            user.id, effective_workspace_id, req.action, req.request_id
        )
    except AlreadyDecidedError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ALREADY_DECIDED",
                "message": "Dieser Vorschlag wurde bereits entschieden.",
                "decision": exc.existing_decision,
                "work_order_id": exc.work_order_id,
            },
        )
    except Exception as exc:
        logger.error(
            "Reject suggested action failed | %s: %s",
            type(exc).__name__, str(exc)[:200],
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "REJECT_FAILED",
                "message": "Ablehnen fehlgeschlagen. Bitte nochmal versuchen.",
            },
        )

    return SuggestedActionDecisionResponse(**result)
