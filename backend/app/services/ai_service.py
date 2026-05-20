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
from app.models.plan import DailyPlanAI

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
    """Raised when AI plan generation fails with a structured error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


async def generate_daily_plan(
    checkin: dict,
    rules: list[dict],
    language: str = "en",
    review: dict | None = None,
) -> tuple[DailyPlanAI, str, bool]:
    """
    Call OpenAI and return (parsed plan, raw JSON string, review_context_used).
    Uses structured outputs (strict JSON schema) to guarantee valid output.
    review_context_used reflects whether non-empty review context was injected.
    Raises AIGenerationError with a specific code on any failure.
    """
    logger.info("AI plan generation started | model=%s", settings.OPENAI_MODEL)

    # ── Step 1: Build prompt ─────────────────────────────────────────────────
    user_prompt, review_context_used = build_user_prompt(checkin, rules, language, review)

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

    # ── Step 3: Parse JSON response ──────────────────────────────────────────
    raw_json = response.choices[0].message.content
    if not raw_json:
        logger.error("OpenAI returned empty response content")
        raise AIGenerationError("UNKNOWN_AI_ERROR", "OpenAI returned an empty response.")

    tokens_used = response.usage.total_tokens if response.usage else "unknown"
    logger.info("OpenAI response received | tokens_used=%s", tokens_used)

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.error("AI JSON parse failed | exc=%s | internal_code=AI_JSON_INVALID", type(exc).__name__)
        raise AIGenerationError("AI_JSON_INVALID", "OpenAI returned invalid JSON.") from exc

    # ── Step 4: Validate Pydantic schema ─────────────────────────────────────
    try:
        plan = DailyPlanAI(**data)
    except ValidationError as exc:
        # Log field/type summary only — no user content
        error_summary = [(e["loc"], e["type"]) for e in exc.errors()]
        logger.error("AI schema validation failed | field_errors=%s", error_summary)
        raise AIGenerationError(
            "AI_SCHEMA_INVALID",
            "AI response did not match the expected schema.",
        ) from exc

    logger.info("AI plan generation succeeded")
    return plan, raw_json, review_context_used
