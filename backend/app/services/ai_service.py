import json
import logging

import httpx
from openai import (
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
)
from pydantic import ValidationError

from app.core.config import settings
from app.prompts.daily_plan import SYSTEM_PROMPT, JSON_SCHEMA, build_user_prompt
from app.prompts.jarvis_chat import (
    JSON_SCHEMA as JARVIS_JSON_SCHEMA,
    build_chat_prompt,
    build_system_prompt as build_jarvis_system_prompt,
)
from app.models.plan import DailyPlanAI
from app.models.jarvis import JarvisChatAI

logger = logging.getLogger(__name__)

# Separate connect timeout (fail fast on network issues) from read timeout
# (OpenAI may take up to ~60s to stream a structured output response).
# max_retries=2 is the SDK default but we set it explicitly for clarity.
_OPENAI_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=_OPENAI_TIMEOUT,
    max_retries=2,
)


class AIGenerationError(Exception):
    """Raised when AI plan generation fails with a structured error code.

    input_tokens / output_tokens carry the token counts from response.usage when
    the OpenAI call succeeded but downstream parsing/validation failed. They are 0
    for network-level failures (auth, rate-limit, connection) where no tokens were
    consumed. The router uses these to log usage even on failure paths.
    """

    def __init__(
        self,
        code: str,
        message: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        super().__init__(message)
        self.code = code
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


async def generate_daily_plan(
    checkin: dict,
    rules: list[dict],
    language: str = "en",
    review: dict | None = None,
    projects: list[dict] | None = None,
    vault_context: str = "",
) -> tuple[DailyPlanAI, str, bool, int, int]:
    """
    Call OpenAI and return (parsed plan, raw JSON string, review_context_used,
    input_tokens, output_tokens).
    Uses structured outputs (strict JSON schema) to guarantee valid output.
    review_context_used reflects whether non-empty review context was injected.
    vault_context is passed straight through to build_user_prompt — empty
    string means the plan generates exactly as it did before the vault layer.
    input_tokens / output_tokens are 0 if response.usage is unavailable.
    Raises AIGenerationError with a specific code on any failure.
    """
    logger.info("AI plan generation started | model=%s", settings.OPENAI_MODEL)

    # ── Step 1: Build prompt ─────────────────────────────────────────────────
    user_prompt, review_context_used = build_user_prompt(
        checkin, rules, language, review, projects, vault_context
    )

    if settings.DEBUG_AI_PROMPT:
        review_date = review.get("review_date") if review else None
        logger.info(
            "AI prompt built | review_context_used=%s | review_date=%s",
            review_context_used,
            review_date,
        )

    # ── Step 2: Call OpenAI ──────────────────────────────────────────────────
    logger.info(
        "Calling OpenAI API | model=%s | review_context_used=%s",
        settings.OPENAI_MODEL,
        review_context_used,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "daily_plan",
                    "strict": True,
                    "schema": JSON_SCHEMA,
                },
            },
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
    except AuthenticationError as exc:
        logger.error(
            "OpenAI authentication failed | exc=%s | status=%s | model=%s | internal_code=OPENAI_AUTH_FAILED",
            type(exc).__name__,
            getattr(exc, "status_code", "unknown"),
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "OPENAI_AUTH_FAILED",
            "OpenAI authentication failed. Check the API key.",
        ) from exc
    except RateLimitError as exc:
        # Use exc.code (extracted from structured API body) — never str(exc)
        provider_code: str = getattr(exc, "code", None) or ""
        if "quota" in provider_code:
            logger.error(
                "OpenAI quota exceeded | exc=%s | status=%s | provider_code=%s | model=%s | internal_code=OPENAI_QUOTA_EXCEEDED",
                type(exc).__name__,
                getattr(exc, "status_code", "unknown"),
                provider_code,
                settings.OPENAI_MODEL,
            )
            raise AIGenerationError(
                "OPENAI_QUOTA_EXCEEDED",
                "OpenAI API quota exceeded.",
            ) from exc
        logger.warning(
            "OpenAI rate limited | exc=%s | status=%s | provider_code=%s | model=%s | internal_code=OPENAI_RATE_LIMITED",
            type(exc).__name__,
            getattr(exc, "status_code", "unknown"),
            provider_code,
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "OPENAI_RATE_LIMITED",
            "OpenAI request rate limited. Please try again shortly.",
        ) from exc
    except (APIConnectionError, APITimeoutError) as exc:
        logger.error(
            "OpenAI connection/timeout error | exc=%s | model=%s | internal_code=OPENAI_CONNECTION_ERROR",
            type(exc).__name__,
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "OPENAI_CONNECTION_ERROR",
            "Could not reach OpenAI. Please try again.",
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected OpenAI error | exc=%s | model=%s | internal_code=UNKNOWN_AI_ERROR",
            type(exc).__name__,
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "UNKNOWN_AI_ERROR",
            "Unexpected error during OpenAI request.",
        ) from exc

    # ── Step 3: Extract token counts BEFORE any validation ───────────────────
    # Tokens are extracted here so they can be attached to AIGenerationError if
    # JSON parsing or Pydantic validation fails. The cost was already incurred
    # the moment OpenAI responded — callers must log it regardless of outcome.
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0
    logger.info(
        "OpenAI response received | input_tokens=%s | output_tokens=%s",
        input_tokens, output_tokens,
    )

    try:
        raw_json = response.choices[0].message.content
        if not raw_json:
            logger.error("OpenAI returned empty response content")
            raise AIGenerationError(
                "UNKNOWN_AI_ERROR", "OpenAI returned an empty response.",
                input_tokens=input_tokens, output_tokens=output_tokens,
            )

        # ── Step 4: Parse JSON response ──────────────────────────────────────
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.error("AI JSON parse failed | exc=%s | internal_code=AI_JSON_INVALID", type(exc).__name__)
            raise AIGenerationError(
                "AI_JSON_INVALID", "OpenAI returned invalid JSON.",
                input_tokens=input_tokens, output_tokens=output_tokens,
            ) from exc

        # ── Step 5: Validate Pydantic schema ─────────────────────────────────
        try:
            plan = DailyPlanAI(**data)
        except ValidationError as exc:
            # Log field/type summary only — no user content
            error_summary = [(e["loc"], e["type"]) for e in exc.errors()]
            logger.error("AI schema validation failed | field_errors=%s", error_summary)
            raise AIGenerationError(
                "AI_SCHEMA_INVALID",
                "AI response did not match the expected schema.",
                input_tokens=input_tokens, output_tokens=output_tokens,
            ) from exc

        logger.info("AI plan generation succeeded")
        return plan, raw_json, review_context_used, input_tokens, output_tokens

    except AIGenerationError:
        raise  # already structured — let it through with its tokens attached
    except Exception as exc:
        # Catches malformed choices (IndexError, AttributeError, etc.) that
        # escape the specific handlers above. Tokens are known at this point,
        # so we wrap rather than losing them.
        logger.error(
            "Unexpected error processing OpenAI response | exc=%s | internal_code=AI_RESPONSE_MALFORMED",
            type(exc).__name__,
        )
        raise AIGenerationError(
            "AI_RESPONSE_MALFORMED",
            f"Unexpected error processing OpenAI response: {type(exc).__name__}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ) from exc


async def generate_chat_reply(
    message: str,
    history: list[dict],
    context_block: str,
    language: str = "de",
) -> tuple[JarvisChatAI, int, int]:
    """
    Call OpenAI for a Jarvis chat reply. Structured JSON output (reply +
    suggested_actions) via the same strict json_schema pattern as
    generate_daily_plan (JARVIS-C1, Phase 3) — not a second AI pipeline, the
    existing one extended. Returns (parsed response, input_tokens,
    output_tokens). Raises AIGenerationError with the same error-code
    taxonomy as generate_daily_plan on any failure, including the JSON-parse
    and schema-validation failure modes structured output can newly produce.

    language is the caller's resolved profile.language ("en"/"de") — same
    contract as generate_daily_plan's language param below. Previously this
    was hardcoded to German regardless of the caller's language, unlike the
    daily-plan path; that mismatch is why switching the UI language left
    Jarvis chat replies stuck in German.
    """
    logger.info("AI chat reply started | model=%s | language=%s", settings.OPENAI_MODEL, language)

    user_prompt = build_chat_prompt(message, history, context_block, language)
    system_prompt = build_jarvis_system_prompt(language)

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "jarvis_chat_reply",
                    "strict": True,
                    "schema": JARVIS_JSON_SCHEMA,
                },
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=1536,
        )
    except AuthenticationError as exc:
        logger.error(
            "OpenAI authentication failed | exc=%s | status=%s | model=%s | internal_code=OPENAI_AUTH_FAILED",
            type(exc).__name__,
            getattr(exc, "status_code", "unknown"),
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "OPENAI_AUTH_FAILED",
            "OpenAI authentication failed. Check the API key.",
        ) from exc
    except RateLimitError as exc:
        provider_code: str = getattr(exc, "code", None) or ""
        if "quota" in provider_code:
            logger.error(
                "OpenAI quota exceeded | exc=%s | status=%s | provider_code=%s | model=%s | internal_code=OPENAI_QUOTA_EXCEEDED",
                type(exc).__name__,
                getattr(exc, "status_code", "unknown"),
                provider_code,
                settings.OPENAI_MODEL,
            )
            raise AIGenerationError(
                "OPENAI_QUOTA_EXCEEDED",
                "OpenAI API quota exceeded.",
            ) from exc
        logger.warning(
            "OpenAI rate limited | exc=%s | status=%s | provider_code=%s | model=%s | internal_code=OPENAI_RATE_LIMITED",
            type(exc).__name__,
            getattr(exc, "status_code", "unknown"),
            provider_code,
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "OPENAI_RATE_LIMITED",
            "OpenAI request rate limited. Please try again shortly.",
        ) from exc
    except (APIConnectionError, APITimeoutError) as exc:
        logger.error(
            "OpenAI connection/timeout error | exc=%s | model=%s | internal_code=OPENAI_CONNECTION_ERROR",
            type(exc).__name__,
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "OPENAI_CONNECTION_ERROR",
            "Could not reach OpenAI. Please try again.",
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected OpenAI error | exc=%s | model=%s | internal_code=UNKNOWN_AI_ERROR",
            type(exc).__name__,
            settings.OPENAI_MODEL,
        )
        raise AIGenerationError(
            "UNKNOWN_AI_ERROR",
            "Unexpected error during OpenAI request.",
        ) from exc

    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0
    logger.info(
        "OpenAI response received | input_tokens=%s | output_tokens=%s",
        input_tokens, output_tokens,
    )

    try:
        raw_json = response.choices[0].message.content
        if not raw_json:
            logger.error("OpenAI returned empty response content")
            raise AIGenerationError(
                "UNKNOWN_AI_ERROR", "OpenAI returned an empty response.",
                input_tokens=input_tokens, output_tokens=output_tokens,
            )

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.error("AI JSON parse failed | exc=%s | internal_code=AI_JSON_INVALID", type(exc).__name__)
            raise AIGenerationError(
                "AI_JSON_INVALID", "OpenAI returned invalid JSON.",
                input_tokens=input_tokens, output_tokens=output_tokens,
            ) from exc

        try:
            chat_ai = JarvisChatAI(**data)
        except ValidationError as exc:
            error_summary = [(e["loc"], e["type"]) for e in exc.errors()]
            logger.error("AI schema validation failed | field_errors=%s", error_summary)
            raise AIGenerationError(
                "AI_SCHEMA_INVALID",
                "AI response did not match the expected schema.",
                input_tokens=input_tokens, output_tokens=output_tokens,
            ) from exc

        logger.info("AI chat reply succeeded | suggested_actions=%d", len(chat_ai.suggested_actions))
        return chat_ai, input_tokens, output_tokens

    except AIGenerationError:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error processing OpenAI response | exc=%s | internal_code=AI_RESPONSE_MALFORMED",
            type(exc).__name__,
        )
        raise AIGenerationError(
            "AI_RESPONSE_MALFORMED",
            f"Unexpected error processing OpenAI response: {type(exc).__name__}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ) from exc
