# Stage 14: Adaptive Practice frontend

Dashboard provides a separate **Adaptive Practice** entry alongside ordinary
Practice, Diagnostic Assessment and recommendations. Opening it renders an inert
welcome screen; **Start or Resume Adaptive Practice** contacts the backend for
demo student 1. No session is created merely by rendering a page.

The view shows one backend-assigned question, concept name, target/progress, the
actual `selection_reason`, selectable native option buttons and Submit. It does
not implement ranking, prerequisites, BKT, or question prediction. Reasons render
as plain text. If a reason is missing, the UI reports that explicitly rather than
inventing an explanation. Currently blocked assignments show backend
`blocked_reason` and disable fresh submissions. Pending idempotent retries remain
recoverable even when eligibility or session lifecycle has since changed.

Authorized correct/incorrect feedback, correct option, authored explanation and
BKT estimate use the existing `AttemptFeedback`. Feedback and the original reason
stay attached to the submitted question until **Continue**, which fetches actual
session state. The next question is never selected or guessed locally. Results
are retrieved when backend status becomes completed, including early completion.
`eligible_pool_exhausted` is presented as an expected completion reason, not an
error or an implication that everything is mastered. Zero-answer accuracy is
Not available, and missing BKT snapshots are Not recorded. Correct-answer count
uses answered questions as its denominator, separately from the five-question
target. Per-concept estimates and session selection reasons come from results.

Results link to Dashboard recommendations and My Progress; those existing pages
remount and fetch fresh data. **Start a New Session** and **Restart Adaptive
Session** require confirmation. The shared diagnostic confirmation component
accepts optional adaptive title/message props while retaining diagnostic defaults.
Focus moves to the welcome/question/results heading or safe cancel action.
Existing winter pastel utilities/styles are reused, with no new dependencies.

## Session and retry recovery

Student-scoped localStorage key `skillforge:adaptive:1:v1` is independent of
diagnostic storage. It contains session identity, pending question/choice/position/
target/selection reason and submission UUID, plus a confirmed restart request UUID
when needed. It never stores correct answers, authored explanations or results.
Malformed cache is discarded with a warning. Storage blocked/full falls back to
in-memory retries; reload still recovers authoritative backend progress, but an
old feedback response may be unavailable without its UUID.

New answer intent generates one UUID before sending; failures keep that payload
and lock the choice. Retry and reload recovery replay it to retrieve saved
feedback, never infer that the server failed to save. A new assigned question
gets a new UUID. Restart retries/reloads likewise retain their request UUID.
Synchronous busy guards prevent duplicate clicks. Cancellation on view cleanup
invalidates late responses even when fetch ignores abort; server writes may still
complete, so pending identities remain for recovery.

Without pending intent, `/start` reconciles current state rather than trusting a
stale saved session ID. Confirmed pending restart recovery takes priority. Missing,
abandoned and conflicting sessions offer **Check Current Session**. Failed
results/progress reads can retry without another answer submission. After a page
reload, use the normal Dashboard entry and Start or Resume to recover the session.

## Files

Added:

- `src/api/adaptive.ts`
- `src/adaptiveStore.ts`
- `src/AdaptivePage.tsx`
- `tests/adaptive.test.mjs`
- `tests/adaptiveRendering.test.mjs`
- `ADAPTIVE_UI.md`

Modified: `src/App.tsx` (entry/view), `src/DiagnosticPage.tsx` (optional shared
restart-confirmation wording only). Diagnostic state management and ordinary
Practice submission logic are unchanged. No backend/schema/content changes.

## Validation and manual checks

Automated tests cover API routes/payloads, inert welcome, start/resume, reloads,
five-question flow, arbitrary backend next IDs and exact reason text, correct/
incorrect feedback, no leakage, duplicate clicks, UUID-preserving retries,
restart recovery, null-accuracy/early completion, eligibility loss, malformed or
blocked storage, stale responses, accuracy/mastery labels, plain-text escaping,
accessible markup, and ordinary/diagnostic regressions.

Manual browser verification remains required:

- Live start/resume and Continue through normal and early completion; verify
  Dashboard/My Progress refresh after saved adaptive answers.
- Reload/navigation during slow or lost answer/restart responses, and concurrent
  tabs that restart or change prerequisite eligibility.
- Confirmation cancel/confirm focus, keyboard option navigation and submission,
  screen-reader feedback/result announcements and visible focus outlines.
- Mobile stacking, long selection reasons/options/explanations, empty results,
  API unavailability and blocked/full browser storage.

Use an isolated designated test student/database for live checks. Automated
frontend tests mock backend responses and do not create development sessions or
attempts. No authentication, deployment or later-stage features are included.

Validation completed: **134 frontend tests passed** (26 added), with TypeScript,
ESLint and production build passing. The full backend regression suite passed
**250 tests plus 11 subtests**, including the existing standalone verification
tests; one existing Starlette/httpx deprecation warning remains. Read-only
development comparison confirmed revision 0006 with unchanged complete rows,
hashes, schema, PK/FK definitions and sequence state; adaptive tables stayed empty.
