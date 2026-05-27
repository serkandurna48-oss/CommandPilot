import logging
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

from app.db.client import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing (hardcoded, CP-203 scope — no external API, no env-var)
# gpt-4o as of 2025: $2.50/1M input tokens, $10.00/1M output tokens
# ---------------------------------------------------------------------------
_MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    "gpt-4o": {
        "input_per_1m":  Decimal("2.50"),
        "output_per_1m": Decimal("10.00"),
    },
}

DAILY_CAP_USD = Decimal("0.50")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class DailyCapExceededError(Exception):
    """Raised by check_daily_cap when the user's UTC-day spend >= DAILY_CAP_USD."""

    def __init__(self, current_spend: Decimal, cap: Decimal, resets_at: str):
        self.current_spend = current_spend
        self.cap = cap
        self.resets_at = resets_at  # ISO 8601 string — tomorrow 00:00:00+00:00
        super().__init__(
            f"Daily cap of ${cap} reached (current: ${current_spend}). "
            f"Resets at {resets_at}."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _next_utc_midnight() -> str:
    """Return tomorrow 00:00:00+00:00 as ISO 8601 string."""
    tomorrow = _utc_today() + timedelta(days=1)
    return datetime.combine(
        tomorrow,
        datetime.min.time(),
        tzinfo=timezone.utc,
    ).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """
    Return cost in USD as Decimal.
    Raises ValueError for unknown models — no silent fallback. If the model
    changes (e.g. gpt-4o → gpt-5), the cap logic must not silently use wrong
    pricing. Update _MODEL_PRICING in this file when switching models.
    """
    pricing = _MODEL_PRICING.get(model)
    if pricing is None:
        raise ValueError(
            f"No pricing defined for model {model!r}. "
            "Add an entry to _MODEL_PRICING in usage_service.py."
        )
    return (
        Decimal(input_tokens)  / Decimal("1000000") * pricing["input_per_1m"]
        + Decimal(output_tokens) / Decimal("1000000") * pricing["output_per_1m"]
    )


def get_daily_spend_usd(user_id: str, request_date: date) -> Decimal:
    """
    Return the sum of cost_usd for user on the given UTC date.
    Fetches all rows for that date and sums in Python (expected: < 20 rows/user/day).
    Returns Decimal("0") if no rows exist.

    request_date must be computed once by the caller and passed in — never call
    datetime.now() independently here to avoid a midnight-crossing race where
    the cap check and the log write use different dates.
    """
    today_str = str(request_date)
    db = get_db()
    result = (
        db.table("ai_usage_log")
        .select("cost_usd")
        .eq("user_id", user_id)
        .eq("request_date", today_str)
        .execute()
    )
    if not result.data:
        return Decimal("0")
    return sum(Decimal(str(row["cost_usd"])) for row in result.data)


def check_daily_cap(user_id: str, request_date: date) -> None:
    """
    Raise DailyCapExceededError if user's spend on request_date >= DAILY_CAP_USD.
    Does nothing if spend is under cap.

    Soft cap semantics: blocks new generations once total daily spend reaches
    DAILY_CAP_USD. A single in-progress call can push the running total slightly
    above the cap (typically $0.01–0.05 per plan). Two concurrent requests from
    the same user can both pass pre-flight and both spend. This is acceptable for
    v0.2 / private beta.

    For hard-cap semantics (never exceed), pre-flight would need to estimate the
    maximum possible cost based on token limits and reject if spend + max_cost > cap.
    Out of scope for CP-203.
    """
    spend = get_daily_spend_usd(user_id, request_date)
    if spend >= DAILY_CAP_USD:
        raise DailyCapExceededError(
            current_spend=spend,
            cap=DAILY_CAP_USD,
            resets_at=_next_utc_midnight(),
        )


def log_ai_usage(
    user_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
    request_date: date,
    workspace_id: str | None = None,
    plan_id: str | None = None,
) -> None:
    """
    Persist one AI usage row. Never re-raises — the user already spent the tokens.
    Logs CRITICAL on failure so monitoring can detect cap-bypass risk.

    request_date must be the same value used for the pre-flight cap check —
    pass the date computed in the router, never recompute it here.
    """
    db = get_db()
    payload = {
        "user_id":       user_id,
        "workspace_id":  workspace_id,
        "plan_id":       plan_id,
        "request_date":  str(request_date),
        "model":         model,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "cost_usd":      str(cost_usd),  # numeric(10,6) — pass as string for safety
    }
    try:
        db.table("ai_usage_log").insert(payload).execute()
    except Exception as exc:
        logger.error(
            "CRITICAL: failed to log AI usage — daily cap may be bypassable "
            "| user_id=%s | cost_usd=%s | model=%s",
            user_id, cost_usd, model,
            exc_info=True,
        )
