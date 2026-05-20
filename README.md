# CommandPilot

Personal Operating System for ambitious people.

Turn a messy morning brain dump into a clear, AI-generated daily strategy.

## What It Does

1. User signs up or logs in with Supabase Auth.
2. User enters a morning check-in: energy, sleep, mood, fixed events, tasks, raw text.
3. AI generates a structured daily plan with priorities, time blocks, energy strategy, and review questions.
4. User stores personal rules that the AI considers.
5. User closes the day with an evening review.
6. Data is persisted per authenticated user and workspace in Supabase/PostgreSQL.

## Tech Stack

| Layer | Tech |
| --- | --- |
| Frontend | Next.js 14 App Router, React, TypeScript, Tailwind CSS |
| Backend | FastAPI, Pydantic, Python |
| Database | Supabase PostgreSQL |
| Auth | Supabase Auth |
| AI | OpenAI GPT-4o JSON mode |

## Local Development

### 1. Supabase Setup

1. Create a Supabase project.
2. In Authentication -> Providers, enable Email.
3. In Authentication -> URL Configuration, add `http://localhost:3000` as the site URL and redirect URL for local testing.
4. In SQL Editor, run the full contents of `supabase/schema.sql`.
5. Copy the project URL, anon key, and service role key.

The anon key is safe for the frontend. The service role key must only be used by the FastAPI backend.

### 1b. Running Migrations

After running `supabase/schema.sql` for the first time, apply any incremental migrations in order:

| File | What it does | Run when |
| --- | --- | --- |
| `supabase/migrations/001_profiles_language_check.sql` | Normalises `profiles.language` to `'en'` for null/invalid rows, then adds a CHECK constraint | Before deploying i18n / language-selection feature |
| `supabase/migrations/002_daily_plans_review_context_used.sql` | Adds `daily_plans.review_context_used boolean default false` if the column is missing | Before deploying backend code that writes `review_context_used` |

Run each file in the Supabase SQL Editor. Migrations are idempotent — safe to re-run.

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set these values in `backend/.env`:

| Variable | Description |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only service role key |
| `OPENAI_API_KEY` | OpenAI API key |
| `FRONTEND_URL` | Frontend URL, usually `http://localhost:3000` |
| `OPENAI_MODEL` | AI model, default `gpt-4o` |

Run the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. API docs are at `http://localhost:8000/docs`.

### 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

Set these values in `frontend/.env.local`:

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Backend API base URL, usually `http://localhost:8000` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |

Run the frontend:

```bash
npm run dev
```

Frontend runs at `http://localhost:3000`.

## Auth Model

- `/login` and `/signup` use Supabase email/password auth.
- Protected frontend routes are `/dashboard`, `/morning`, `/plans/[id]`, `/review`, `/rules`, and `/settings`.
- Frontend API requests send the Supabase access token in `Authorization: Bearer <token>`.
- Backend endpoints validate the token with Supabase before reading or writing data.
- Backend derives `user_id` from the validated session; clients do not choose their own user ID.
- On first signup/login, `/api/auth/bootstrap` ensures a profile, personal workspace, and `workspace_members` owner row exist.
- The Supabase service role key is used only in the backend.

## API Endpoints

All endpoints except health require a bearer token.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| POST | `/api/auth/bootstrap` | Ensure profile and personal workspace |
| POST | `/api/checkins` | Create or update today's morning check-in |
| GET | `/api/checkins/me` | List current user's check-ins |
| GET | `/api/checkins/{id}` | Get an owned check-in |
| POST | `/api/plans/generate` | Generate AI daily plan for an owned check-in |
| GET | `/api/plans/me` | List current user's plans |
| GET | `/api/plans/me/latest` | Get current user's latest plan |
| GET | `/api/plans/{id}` | Get an owned plan |
| POST | `/api/reviews` | Save evening review |
| GET | `/api/reviews/me` | List current user's reviews |
| GET | `/api/reviews/{id}` | Get an owned review |
| POST | `/api/rules` | Create user rule |
| GET | `/api/rules/me` | List current user's rules |
| PATCH | `/api/rules/{id}` | Update an owned rule |
| DELETE | `/api/rules/{id}` | Delete an owned rule |

## Manual Auth Test Checklist

- [ ] Visit `http://localhost:3000/dashboard` while logged out. You should be redirected to `/login`.
- [ ] Create a new account at `/signup`.
- [ ] Confirm email if your Supabase project requires confirmation, then log in.
- [ ] Confirm `/dashboard`, `/morning`, `/review`, `/rules`, and `/settings` load only while signed in.
- [ ] In Supabase, confirm the new user has one `profiles` row, one personal `workspaces` row, and one owner `workspace_members` row.
- [ ] Create a morning check-in and generate a plan.
- [ ] Create a rule and confirm it appears only for that account.
- [ ] Submit an evening review.
- [ ] Sign out from `/settings` and confirm protected routes redirect back to `/login`.
- [ ] Create or log in as a second user and confirm they cannot see the first user's plans, rules, check-ins, or reviews.
- [ ] Call an authenticated endpoint without `Authorization`; it should return `401`.
- [ ] Try fetching another user's record ID with a valid token; it should return `404`.

## Architecture Notes

- `workspace_id` is written on user-owned records to keep the multi-tenant foundation intact.
- Supabase RLS policies use `auth.uid()` for direct database access.
- FastAPI also validates ownership before returning records because backend uses the service role key.
- AI prompt logic is isolated in `backend/app/prompts/daily_plan.py`.

## Stability Sprint (2026-05-20)

Applied after the initial MVP build to make the app stable, secure, and mobile-testable:

1. **Root `.gitignore`** — Prevents venv, `.env`, `.next`, and `node_modules` from being committed.
2. **Schema slug collision fix** — Trigger now uses `replace(uuid, '-', '')` for a 32-char slug. `ON CONFLICT` changed to `DO NOTHING` (with a lookup fallback) so an existing workspace owner is never overwritten.
3. **`workspaces.owner_id` FK** — Added `ALTER TABLE` FK to `profiles(id)` after both tables are created, avoiding circular dependency.
4. **`ensure_user_workspace` hardened** — All three `.execute().data[0]` calls are now guarded; empty results raise `HTTP 500` with a clear message instead of `IndexError`.
5. **Bootstrap on SIGNED_IN only** — `onAuthStateChange` now calls `bootstrap()` only on `SIGNED_IN` (and clears state on `SIGNED_OUT`), preventing redundant API calls on every token refresh.
6. **Mobile bottom navigation** — `MobileNav` component added to `AppShell`. Fixed `pb-16 md:pb-0` on `<main>` so content isn't hidden behind the bar.
7. **`PlanResponse` types** — `top_priorities` and `time_blocks` changed from `List[dict]` to `List[Priority]` / `List[TimeBlock]`. FastAPI now validates and serialises these correctly.
8. **Language default standardised to `"en"`** — Fixed in `PlanGenerateRequest`, `ai_service.py`, and `schema.sql` profiles table (was `"de"` in all three).
9. **Header hydration fix** — `formatDate(today())` now runs inside a `useEffect`, avoiding SSR/client mismatch from `localStorage` access during render.
10. **AI error handling** — `max_tokens` raised to `4096`. `json.JSONDecodeError` and `pydantic.ValidationError` are now caught separately and re-raised as descriptive `ValueError`s.
11. **Cleanup** — Removed unused `date-fns` dependency; removed dead `./pages/**` glob from `tailwind.config.ts`.
