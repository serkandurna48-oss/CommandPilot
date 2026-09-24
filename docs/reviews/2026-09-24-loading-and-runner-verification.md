# Loading errors and runner handoff verification

Base revision: `247ca64a2fcce7a555ea4487418c6a6c238f3b71`.

First fix commit: `7af411a` (`fix: surface dashboard plan and work-order loading errors`).
That commit was created under the earlier commit authorization, before the
user's subsequent instruction forbidding commits. During that restricted
phase, all follow-up work remained uncommitted and nothing was pushed.
The user subsequently authorized reviewing the complete diff, committing the
remaining changes and deploying v1. Pre-deployment checks again passed:
frontend lint, type-check and all 32 focused frontend regression tests.
Browser access was retried, but Chrome still reported unavailable.

## Missing data

Eight frontend files hid failed reads as empty states or, in the operator
list, substituted demo work orders. They now show load errors and retry
controls. The dashboard also clears an old plan after a successful empty
response and shows a later plan-fetch error even when an old plan exists.

Additional local verification found and fixed:

1. **Empty error messages still looked like success.** A rejected request with
   `new Error("")` hid the error in all four histories and the operator list.
   HomeBriefing and ProjectCards also treated an empty error string as no error.
   Error rendering now checks the explicit `null` sentinel, so the translated
   fallback and retry action remain visible without server-provided text.
2. **Obsolete requests could overwrite fresh results.** Effect cleanup no
   longer invalidated pending history requests after adding retry callbacks.
   Replaying the effect, resolving the second fetch, then rejecting the first
   reproduced a spurious error over a successful load. Request sequence guards
   now discard obsolete responses in the four histories, rules/operator lists
   and dashboard. These guards do not cancel network traffic.
3. **Dashboard Jarvis context still claimed absence after fetch failure.**
   The snapshot and quick-action prompts used initial empty arrays/null even
   when the visible cards reported failure. They now distinguish loading,
   failed reads and successfully empty results. No AI calls were needed.

This fixes misleading presentation of failed requests. It does not establish
or fix the transport/server cause of intermittent production fetch failures.

Verification in this session:

- `npm run lint`: passed without warnings or errors.
- `npm run type-check`: passed.
- `node scripts/test_frontend_load_errors.cjs`: 32 passed. The checks use
  actual TSX transpiled in memory, simulated React hooks/API responses and
  React static rendering. They cover errors with/without text, retries,
  retries that return populated lists, obsolete responses, dashboard/Jarvis
  consistency, and lifecycle callbacks.
  This is not a real browser test or a test of React's scheduler. No test
  dependencies were installed. Before the follow-up fixes, nine of the
  initial 16 regression cases failed; all now pass.
- `.\\.venv\\Scripts\\python.exe scripts/test_import_result_integrity.py`:
  27 passed with mocked API calls, including refusal to report review-ready
  after required result writes fail.
- `.\\.venv\\Scripts\\python.exe backend/tests/test_work_order_transitions.py`:
  11 passed with a mocked database. These cover Python RPC/error handling,
  not the real database state machine or persistence.
- `git diff --check`: passed.
- Browser error injection/retry clicking and mobile verification remain open:
  no browser was available through the session's browser-control tools.

## Why the UI stops at running

`LifecycleControls.tsx` deliberately delegates result reporting to the local
runner/import scripts. The UI supports preparation (`draft -> approved ->
queued`), marking an order `running`, cancellation, resuming interrupted work,
and review decisions (`review_ready -> accepted/rework_requested/cancelled`).
Marking an order running does not itself launch a local runner.

The runner executes work and imports its result through
`scripts/run_work_order.py` / `scripts/import_work_order_result.py`. This
creates the review package and reports the result status. The browser does
not provide a manual review-package editor or a browser-only execution path.
The existing daemon can pick up the autonomous-start trigger, but requires
local setup and a running process; it is not a hosted execution service.
That setup requirement is a usability limitation, not evidence of a broken
running-state button. No onboarding feature was added in this change.

Production verification in this session (authenticated, read-only GET against
`https://commandpilot.onrender.com`):

- Work order `6d8ac613-c5b0-4511-b17c-92d0ab00982c` is clearly marked as a test.
- Status is `review_ready`, not `accepted`.
- Its persisted review package contains the isolated scratch-file summary,
  `files_changed`, a manual test description, and verdict `ready_for_review`.
- All six steps are `completed`; a scratch-file artifact is present.
- The prior session's actual file creation/import is reported in the handoff;
  this session verified persisted records, not the scratch file itself.
- **Still open:** click the real Accept button in the production UI, then
  reload and verify `accepted` with the same review package. Browser control
  was unavailable; no API status PATCH was substituted for this UI test.

The local LifecycleControls checks additionally confirm that Accept calls
`onStatusChange("accepted")`, a rejected Accept call is visible and retryable,
and running exposes Stop without a manual result/Accept transition. They do
not establish that the production Accept button and persistence work end to end.

## Remaining verification and handoff

- Browser access is unavailable in this session (both in-app browser and
  Chrome reported unavailable). Block one list endpoint, confirm the visible
  error/retry state, unblock it, click Retry, then confirm real data returns.
  A successful empty response must still show the genuine empty state.
- Open the test order, inspect its review package, click the actual Accept
  control and reload. Expected: `accepted` and the same persisted review
  package. Do not claim this is complete based on the isolated callback test.
- Mobile layout and touch interaction remain untested.
- The cause of intermittent production request failures remains unknown.
  The next diagnostic needs a failed request's HTTP status/timing and matching
  server log, without exposing credentials. Do not infer a cold-start or
  authentication cause from the presentation bug alone.
- No full backend suite was run; no claim of a fully green backend suite is
  made. No paid AI calls or production writes were performed.
- Review the complete delta with `git diff 247ca64 -- frontend`; plain
  `git diff` excludes already committed changes. The regression script and
  this report are separate additions outside the frontend directory.

No production data was changed in the initial verification. The test order
was not deleted. The subsequent v1 authorization covers commit/push/deployment
and the actual browser Accept/reload check, once browser access is available.
