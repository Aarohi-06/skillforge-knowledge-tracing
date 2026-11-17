# Stage 13: adaptive practice sessions (backend only)

## Endpoints and contracts

All paths are under `/students/{student_id}/adaptive-sessions`. Session IDs are
UUIDs; all operations verify student existence and session ownership.

| Method / suffix | Behavior |
| --- | --- |
| `POST /start` | No body. Create the first session, resume an active session, or return the latest completed session. Never silently starts another after completion. |
| `GET /{session_id}` | Current state, saved current question and selection reason; never assigns or reshuffles questions. |
| `POST /{session_id}/answers` | Answer only the assigned question. Saves shared BKT evidence and selects at most one new question in the same transaction. |
| `GET /{session_id}/results` | Completed results only; incomplete/abandoned returns 409. |
| `POST /restart` | `{"request_id":"<UUID>"}` abandons the active adaptive session and starts another, without resetting mastery or deleting attempts. Reusing a request ID returns that original restart's session/current state. |

Answer request:

```json
{
  "question_id": 123,
  "selected_answer": 1,
  "submission_id": "b085cc61-c19d-438a-a369-1b2e0b7174cb"
}
```

Question IDs are actual database IDs returned by the API, never hardcoded in
selection. Selected answer is a strict nonnegative zero-based integer. Required
UUIDs, invalid field types/option indices return 422. Missing students or
wrong-student/missing sessions return 404. Skipping/re-answering, UUID payload
conflicts, closed-session new submissions and newly locked concepts return 409.

State response fields:

- `session_id`, `student_id`, `status` (`in_progress`, `completed`, `abandoned`).
- UTC `created_at`, `updated_at`, nullable `completed_at`.
- `target_questions` (5), `assigned_questions`, `answered_questions`.
- Nullable zero-based `next_position`, `next_question` (existing public question
  schema), and persisted `selection_reason`.
- Nullable `current_question_eligible`, and a `blocked_reason` if prerequisites
  have changed since assignment.
- Nullable `completion_reason`: `target_reached` or `eligible_pool_exhausted`.

Only a successful answer returns authorized correctness/answer/explanation:
`{"session_id":"...","position":0,"feedback":{...existing AttemptResponse...}}`.
It deliberately excludes mutable session progress, so identical retries return
identical recorded feedback even after completion/restart. GET state afterward
to retrieve the next question. No pre-answer response exposes answer indices or
authored explanations. Selection reasons describe mastery/eligibility/recency,
not the answer. Existing ordinary `POST /attempts` remains unchanged.

Results include `session_id`, `student_id`, `status: "completed"`,
`target_questions`, `answered_questions`, `correct_answers`, and `accuracy` (0..1,
NULL when no questions were answered). `completion_reason` explains a short
session. `concepts` contains ID/name, answered count, nullable `estimated_mastery`
and backend mastery status. `mastery_basis: "last_adaptive_attempt"` means the
last recorded mastery_after per answered concept, not a recomputation or trained
confidence score. NULL snapshots remain NULL. Later ordinary/diagnostic practice
does not rewrite these session results; current mastery still drives existing
progress/recommendations normally. `questions` lists position, question ID,
concept ID, saved selection reason and correctness for completed answers. Raw
accuracy is distinct from BKT estimated mastery.

## Progressive selection policy

Target five questions. Start persists one assignment; each successful answer
updates BKT first, then recalculates eligibility and ranks the next candidate.
Resume returns that persisted assignment and reason, not a fresh selection.

1. Use the existing database concept graph. All immediate prerequisites must have
   backend `mastered` status, classified through `get_mastery_status`. Missing
   mastery uses the existing BKT initial probability. No separate thresholds or
   prerequisite semantics are introduced.
2. Exclude every question already assigned in this session (including the current
   one). Exclude locked concepts. Mastered but eligible concepts may still supply
   practice if they are the weakest remaining candidates; recommendation ranking
   and its exclusion of mastered concepts are unchanged.
3. Rank candidates lexicographically in SQL: current concept BKT probability
   ascending; this student's most recent attempt timestamp ascending with
   never-attempted first; concept integer ID ascending; stable question key
   ascending with NULL keys last; question integer ID ascending.
4. Recency uses MAX(attempted_at) across ordinary, diagnostic and adaptive attempts,
   including legacy NULL-snapshot attempts, always filtered by student. It is a
   relative least-recent policy, not an arbitrary fixed cooldown. Weakness takes
   priority over recency: a recently attempted weak concept can outrank a fresh
   stronger concept, but equally weak alternatives prefer unseen/older questions.
5. SQL filters eligible concept IDs, excludes assigned questions, and uses LIMIT 1.
   Only the small concept graph/mastery map is materialized, not the question bank.
   No random shuffle, external model, new question data, or preselected five-item
   batch is used.

The assignment stores a human-readable reason with the actual estimate at
selection, prerequisite eligibility and recency/tie policy. An initial estimate
is explicitly labeled as having no recorded mastery. Reasons are historical
selection context, not current guarantees. After five answers, complete with
`target_reached`. If no eligible unassigned candidates exist at a selection
point, complete early with `eligible_pool_exhausted`, even at zero answers.
No question is repeated within a session. Restart may intentionally reuse
questions, with recency still considered.

If another learning action lowers a prerequisite after a question was assigned,
GET reports it blocked and submission rechecks eligibility under the student
lock. It returns 409 instead of allowing locked practice. The question remains
persisted: restore eligibility or explicitly restart, rather than silently skip
an assignment. GET never mutates a session to resolve such a change.

## Persistence, transactions and isolation

Revision **`0006_adaptive_sessions`**, parent `0005_diagnostic_sessions`, adds only
`adaptive_sessions` and `adaptive_assignments`. No existing columns/rows change.
Session fields follow diagnostic infrastructure, plus nullable completion reason.
Assignments add required selection_reason. UUID session PK, student/session/
question/attempt FKs, status/completion/reason and position/pairing checks, unique
session/position, session/question, session/submission key, attempt association,
and student/restart key protect persistence. A partial unique index permits at
most one active **adaptive** session per student. Diagnostic and adaptive sessions
may coexist; neither abandons the other. Existing unique question keys and
concept/ID retrieval index are reused; no unnecessary indexes are added to old
tables.

All operations use the existing Student-row lock, the same one held by ordinary
and diagnostic attempts. Shared helpers are reused without changing diagnostic
service behavior: student locking, route commit/rollback wrapper, strict answer/
restart input schemas and per-concept mastery response fields. No global mutex or
separate BKT model is added. The shared attempt service persists the answer,
current mastery, mastery snapshots and authorized feedback snapshots. Assignment
association, next selection and completion status share the route transaction.
A selection or persistence failure rolls back the entire answer/BKT update.

Client submission UUIDs are namespaced with the session UUID (UUID5) before
calling the existing attempt service. Same UUID/payload replays one saved attempt;
conflicting payloads return 409. Different UUIDs cannot re-answer an assignment.
An unexpected collision with an ordinary attempt is rejected, not attached.
Completed/abandoned sessions accept only authorized recorded replays. Concurrent
starts produce one active session; answer/restart races either save evidence
before abandonment or reject it afterward. Restart retry keys are persistent and
never abandon another newer session. Mastery and all old attempts survive restart.

GET handlers follow diagnostic locking for a consistent multi-query read. Use a
normal transaction that permits SELECT FOR UPDATE; explicitly read-only PostgreSQL
transactions reject it. Request dependency cleanup releases locks on exit.
Existing caller-supplied student IDs remain demo identity, not authentication.

History marks associated attempts `origin: "adaptive_practice"`, retaining
`diagnostic` and `ordinary_practice`. Unique attempt associations keep the outer
joins one-to-one, preserving cursor ordering, snapshots and no answer leakage.
The existing frontend history type accepts the extra origin; no adaptive UI is
implemented. Recommendation engine, graph rules and BKT code remain unchanged.

## Development adoption and limits

Development intentionally remains at **0005** during implementation. Adaptive
and updated history queries require 0006; ordinary practice and diagnostics need
no new columns. No automatic migration/import or startup writes are added.
After a fresh verified backup, target/revision checks and separate approval:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe verify_schema.py --revision 0005_diagnostic_sessions
# Only after explicit migration approval:
.\.venv\Scripts\python.exe -m alembic upgrade 0006_adaptive_sessions
.\.venv\Scripts\python.exe verify_schema.py
.\.venv\Scripts\python.exe -m alembic check
```

Verify old counts/full-row hashes, diagnostic records, PK/FK definitions and
sequence state; both new tables must initially be empty. Do not stamp/reset.
Downgrade removes adaptive session metadata only and retains all attempts/mastery
(including adaptive evidence). It loses selection reasons, session idempotency
associations, resume state and adaptive history origins, so it is not a routine
rollback once sessions exist. Re-upgrade cannot reconstruct sessions from attempts.

Limitations: fixed five-question target; deterministic heuristic rather than
trained personalization; no expiry, authentication, question-content versioning,
adaptive frontend or diagnostic behavior changes. Global operator edits to graph/
question data should be done outside active traffic. The small graph/mastery map
is loaded for eligibility; scaling recency aggregation beyond this MVP may warrant
query-plan measurement and separately justified indexes.

## Files and validation

Added:

- `app/adaptive_service.py`, `app/adaptive_routes.py`, `app/adaptive_schemas.py`
- `migrations/versions/0006_adaptive_sessions.py`
- `test_adaptive.py`, `test_adaptive_migration.py`
- `ADAPTIVE_API.md`

Modified:

- `app/models.py`, `app/main.py`, `app/history_service.py`, `app/schemas.py`
- `verify_schema.py`, `conftest.py`
- `test_migrations.py`, `test_diagnostic_migration.py` (current-head and explicit
  older-revision verification)
- `MIGRATIONS.md`, `HISTORY_API.md`
- `../frontend/src/api/history.ts` (origin union only; no adaptive UI)

Validation: **241 backend tests passed**, including **20 new adaptive tests**.
Coverage includes start/resume/reload, progressive five-question assignment,
mastery recalculation, exact prerequisite thresholds, deterministic ties, student-
scoped recency, no repeats, zero/short-pool completion, blocked assignments after
eligibility loss, closed-session replay, collisions, rollback, student isolation,
no answer leakage, accurate paginated origins, diagnostic coexistence, bounded SQL,
and concurrent starts/answers/restarts. Disposable PostgreSQL migration tests
verify empty/populated upgrade/downgrade, existing diagnostic/attempt/mastery data,
NULL snapshots, old sequence values, partial uniqueness and assignment FKs.
Existing diagnostic, Practice, recommendation and migration regressions passed.

**108 frontend tests**, TypeScript (`tsc -b`), ESLint and production build passed.
The existing Starlette/httpx TestClient deprecation warning remains. Development
was accessed only for read-only checkpoint comparison: revision 0005, every
existing row/hash, table/schema, PK/FK definition and application sequence state
remained unchanged. No development migration, adaptive session, attempt or mastery
update was performed, and no deployment was started.
