# CommandPilot Backend

## /api/health/ai

### Behavior

`GET /api/health/ai` — always public, no OpenAI call made:

```json
{
  "openai_key_present": true,
  "openai_model": "gpt-4o",
  "debug_ai_prompt": false
}
```

`GET /api/health/ai?ping=true` — requires `X-Debug-Token: <DEBUG_HEALTH_TOKEN>` header.
Returns `403 Forbidden` if:
- `DEBUG_HEALTH_TOKEN` is not set in env (default), or
- the header is absent or does not match exactly.

When authorized, makes a `models.list()` call to OpenAI (no tokens charged) and returns:

```json
{
  "openai_key_present": true,
  "openai_model": "gpt-4o",
  "debug_ai_prompt": false,
  "openai_reachable": true
}
```

Or if unreachable:

```json
{
  "openai_reachable": false,
  "openai_error_type": "APIConnectionError"
}
```

---

## Smoke Tests

### 1. Local — valid key, confirm basic config

```bash
# Start backend locally with a valid .env
uvicorn app.main:app --reload

curl http://localhost:8000/api/health/ai
# Expected: { "openai_key_present": true, "openai_model": "gpt-4o", ... }
```

### 2. Local — valid key, confirm real OpenAI reachability

```bash
# Set DEBUG_HEALTH_TOKEN=mysecret in .env, restart server
curl -H "X-Debug-Token: mysecret" \
  "http://localhost:8000/api/health/ai?ping=true"
# Expected: { ..., "openai_reachable": true }
```

### 3. Local — invalid key, verify no secret leakage in logs

```bash
# Set OPENAI_API_KEY=sk-invalid in .env, restart server
curl -H "X-Debug-Token: mysecret" \
  "http://localhost:8000/api/health/ai?ping=true"
# Expected response: { "openai_reachable": false, "openai_error_type": "AuthenticationError" }
# Expected log line:
#   WARNING  Health ping: OpenAI unreachable | exc=AuthenticationError | model=gpt-4o
# Confirm: no API key value, no response body, no raw exception string in logs.
```

### 4. Network/APIConnectionError — 502 with stable frontend message

Simulate by setting `OPENAI_API_KEY` to a valid key but blocking outbound traffic,
or using a valid key while OpenAI is unreachable.

```bash
# Trigger plan generation
POST /api/plans/generate  { "checkin_id": "<valid_id>" }

# Expected HTTP response: 502 Bad Gateway
# Expected body (FastAPI wraps detail as an object):
{
  "detail": {
    "code": "OPENAI_CONNECTION_ERROR",
    "message": "Plan generation failed: could not reach the AI service. Please try again in a moment."
  }
}
# Expected log line (no raw exception string):
#   ERROR  OpenAI connection/timeout error | exc=APIConnectionError | model=gpt-4o | internal_code=OPENAI_CONNECTION_ERROR
```

### 5. Production deploy smoke test (Render)

After deploy:

```bash
BASE=https://your-app.onrender.com

# 5a. Basic health
curl $BASE/api/health
# Expected: { "status": "ok", ... }

# 5b. AI config check (public, no ping)
curl $BASE/api/health/ai
# Expected: { "openai_key_present": true, "openai_model": "gpt-4o", ... }
# If openai_key_present is false → OPENAI_API_KEY is missing in Render env vars.

# 5c. Real connectivity ping (requires DEBUG_HEALTH_TOKEN set in Render env)
curl -H "X-Debug-Token: $DEBUG_HEALTH_TOKEN" \
  "$BASE/api/health/ai?ping=true"
# Expected: { "openai_reachable": true }
# If false with APIConnectionError → network issue between Render and api.openai.com.
# If false with AuthenticationError → key is present but invalid/revoked.

# 5d. Unauthenticated ping attempt must be blocked
curl "$BASE/api/health/ai?ping=true"
# Expected: 403 Forbidden — no OpenAI call triggered.

# 5e. End-to-end plan generation with beta user
# Login → Checkin → POST /api/plans/generate
# Expected: 200 OK with plan payload.
```
