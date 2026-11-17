# Stage 12 diagnostic frontend

Dashboard → **Diagnostic Assessment** opens an inert welcome screen in the
existing shell. **Start or Resume Assessment** contacts the authoritative backend
for demo student 1. Merely rendering the welcome screen does not create a session.
The six-question interface uses backend-assigned order, concept names from the
existing concept catalog, a labeled progress element, selected-state answer
buttons, and the existing authorized `AttemptFeedback` component. The backend
auto-completes the sixth answer; the UI retrieves results rather than submitting
another answer or locally scoring the assessment.

Feedback remains attached to its submitted question until **Next Question** or
**View Results**. The following question comes from GET session progress; the UI
never chooses or skips question IDs. Results separately show raw correct count /
accuracy and the backend's last-diagnostic-attempt BKT estimates (including NULL
as Not recorded). Dashboard and My Progress actions remount their existing pages,
which fetch fresh recommendations/progress. Restart requires an inline
confirmation with a focused safe cancel action and explicitly preserves mastery
and attempt history.

## Persistence and retry policy

`localStorage` key `skillforge:diagnostic:1:v1` stores schema version, student,
session identity, pending answer (public question, choice, position, total and
submission UUID), and any confirmed pending restart request UUID. No correct
answer, explanation or result is cached. Session identity is not authorization.
Malformed/incompatible cache is discarded; backend state remains authoritative.

One UUID is generated **before** an intended answer request and retained until
the student proceeds. A failed/ambiguous response keeps the choice locked and
offers retry with that exact payload. On reload, Start or Resume replays a pending
answer to recover authorized saved feedback, including completed/abandoned-session
retries supported by the backend. A genuinely new question gets a fresh UUID.
Confirmed restart requests similarly reuse one request UUID across failures and
reloads. Pending restart recovery takes priority over pending answer recovery.

Without a pending operation, `/start` reconciles against the current backend
session, rather than trusting a local session ID that may have been superseded
in another tab. Completed sessions load results. Abandoned, missing and conflicting
session responses offer **Check Current Assessment**; this clears stale local
intent only after the authoritative current session is returned. There is no
client-side expiry timer; the current backend has no expiry status.

Synchronous store busy guards block duplicate clicks. View cleanup aborts requests
and ignores late responses even when a fetch implementation ignores cancellation.
Aborting a request does not mean its server transaction was undone: pending UUIDs
remain available for recovery. Results/progress and feedback are checked against
student/session/question identity before display.

Browser storage is best-effort. If blocked or full, a visible warning explains
that retries are retained only for the current visit. After reload the backend
still restores progress, but feedback for an old answer may be unavailable without
its UUID. Concurrent tabs remain governed by backend lifecycle/conflict rules;
there is no background tab synchronization or polling. Catalog failures show
Concept name unavailable rather than guessing a concept from question position.

## Files and validation

Added `src/api/diagnostics.ts`, `src/diagnosticStore.ts`, `src/DiagnosticPage.tsx`,
`tests/diagnostics.test.mjs`, `tests/diagnosticRendering.test.mjs`, and this document.
Changed `src/App.tsx`, `src/index.css`, and `src/AttemptFeedback.tsx` (optional next
label/disabled props; existing Practice defaults are preserved).

Tests cover API contracts, start/resume, stale local IDs, all six questions,
correct/incorrect feedback, rapid duplicate clicks, network ambiguity and reload
recovery, fresh answer UUIDs, restart retries, stale async responses, completed
results, failed result retrieval, abandoned/conflicting sessions, invalid storage,
no pre-answer leakage, result labels, native controls and accessibility markup.

Manual browser verification remains required:

- Live start/resume through six questions; leave/re-enter and reload while an
  answer is pending; compare My Progress/recommendations afterward.
- Network throttling/lost answer and restart responses; retries and other-tab
  restart/completion conflicts. Use a designated test student/database to avoid
  adding verification attempts to development data.
- Confirmation cancel/confirm focus, keyboard selection/submission/Next, visible
  focus rings and screen-reader feedback announcements.
- Mobile stacking, long question/option/explanation wrapping, results cards and
  browser storage blocked/full behavior.

No backend, migration, schema, BKT, question-content, recommendation-ranking or
dependency changes are included. No development diagnostic records were created
for automated frontend validation; backend regression tests use the existing
guarded isolated/disposable database fixtures.

Validation completed: **108 frontend tests passed**, TypeScript (`tsc -b`), ESLint
and production build passed; **221 backend tests passed** with the existing
Starlette/httpx TestClient deprecation warning. Read-only development verification
confirmed revision 0005, no model/schema drift, unchanged original row hashes and
sequences, and both diagnostic tables still empty. After a reload the application
opens its normal Dashboard; use its diagnostic entry and Start or Resume to recover
the backend session or pending authorized feedback. No new page-routing dependency
or automatic assessment creation on render was introduced.
