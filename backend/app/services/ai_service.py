import json
import logging
from openai import AsyncOpenAI
from pydantic import ValidationError
from app.core.config import settings
from app.prompts.daily_plan import SYSTEM_PROMPT, JSON_SCHEMA, build_user_prompt
from app.models.plan import DailyPlanAI

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)


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
    """
    user_prompt, review_context_used = build_user_prompt(checkin, rules, language, review)

    if settings.DEBUG_AI_PROMPT:
        review_date = review.get("review_date") if review else None
        logger.info(
            "AI prompt built | review_context_used=%s | review_date=%s",
            review_context_used,
            review_date,
        )

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

    raw_json = response.choices[0].message.content
    if not raw_json:
        raise ValueError("OpenAI returned an empty response")

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI returned invalid JSON: {exc}") from exc

    try:
        plan = DailyPlanAI(**data)
    except ValidationError as exc:
        raise ValueError(f"AI response did not match expected schema: {exc}") from exc

    return plan, raw_json, review_context_used
