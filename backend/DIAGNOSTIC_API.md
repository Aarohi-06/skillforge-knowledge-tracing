# Stage 11: diagnostic assessment backend

No frontend, adaptive session, model-training, deployment, or development migration
is part of this stage. Demo student IDs remain the existing identity mechanism;
student scoping is enforced, but it is not authentication.

## API

All routes are under `/students/{student_id}/diagnostics`. Session IDs are UUIDs.

| Method and path | Behavior |
| --- | --- |
| `POST /start` | No body. Create the first session or resume the existing active/latest session. Returns a completed session if that is the current diagnostic; does not silently start another. |
| `GET /{session_id}` | Read scoped progress and the next unanswered question. |
| `POST /{session_id}/answers` | Submit the current assigned question. Required body below. |
| `POST /{session_id}/complete` | Idempotently return completed results. Returns 409 until all six answers have been saved. |
| `GET /{session_id}/results` | Return completed results; 409 for incomplete/abandoned sessions. |
| `POST /restart` | Required `{"request_id":"<UUID>"}`. Abandon the active session, if any, and create a new session, without deleting attempts or resetting mastery. Reusing the request ID returns that original restart's session, including its current state, rather than restarting again. |

Answer body:

```json
{
  "question_id": 123,
  "selected_answer": 1,
  "submission_id": "b085cc61-c19d-438a-a369-1b2e0b7174cb"
}
```

`selected_answer` is a strict nonnegative zero-based integer index. UUIDs are
mandatory for diagnostic answers/restarts. Invalid UUIDs/types return 422;
missing students or wrong-student/missing sessions return 404. Insufficient
question coverage, skipping, competing/duplicate answer intents, conflicting UUID
payloads, and invalid lifecycle operations return 409. Invalid option indices
return 422 through the existing attempt service.

Progress response fields:

- `session_id`, `student_id`, `status` (`in_progress`, `completed`, `abandoned`).
- UTC `created_at`, `updated_at`, nullable `completed_at`.
- `total_questions`, `answered_questions`.
- Nullable zero-based `next_position` and `next_question` (existing public
  question fields: ID, concept ID, title, description, difficulty, options).

No correct-answer index or explanation appears in progress/results. Abandoned
and completed sessions have no next question. The sixth successful submission
automatically completes the session atomically; no separate completion request is
required. `/complete` confirms that state and returns results, never skips work.

Answer response is `{"session_id": "...", "position": 0, "feedback": {...}}`.
`feedback` is the existing authorized post-submission attempt response, including
correctness, correct-answer index, recorded explanation and mastery probability.
It excludes mutable session progress so a matching retry returns identical saved
feedback even after later answers/restart/completion. Resume with GET or `/start`
for the next question. Ordinary `POST /attempts` remains unchanged.

Results include `session_id`, `student_id`, `status: "completed"`,
`total_questions`, `answered_questions`, `correct_answers`, and `accuracy` (a
fraction 0..1 of diagnostic answers correct). `concepts` contains concept ID/name,
answered count, `estimated_mastery`, and backend-classified mastery `status`.
`mastery_basis: "last_diagnostic_attempt"` explicitly distinguishes snapshot-based
BKT estimates from raw assessment accuracy. This is not trained-model confidence
or measured ability. NULL historical snapshots remain NULL; no values are inferred.
Completed per-concept estimates come from each concept's final diagnostic attempt
and remain stable after later practice. Current mastery continues to drive the
existing recommendations/progress endpoints unchanged.

## Selection and access policy

Exactly six existing questions are assigned: two each from **Arrays**, **Time
Complexity**, then **Recursion**. Each concept is resolved by its database name.
SQL queries are bounded to two rows and ordered by stable question key (NULL keys
last) then integer ID as a tie-breaker. No database integer IDs are hardcoded.
Validate all three concepts before creating/abandoning a session. Insufficient
coverage fails without modifying the previous active session.

The actual question IDs and zero-based order are persisted; resume never
reshuffles them or adds newly imported questions. Current authored wording is read
when questions are served; this stage does not version entire question text.
Diagnostic answering intentionally bypasses prerequisite eligibility checks. This
does not alter ordinary practice rules or graph relationships. Real diagnostic
answers update ordinary BKT mastery through the shared attempt service, which may
affect recommendations/unlocking as any saved evidence would. Restart never
erases that learning. Reading session progress itself never updates mastery.

## Persistence and transaction safety

Revision **`0005_diagnostic_sessions`**, parent `0004_question_bank`, adds only:

- `diagnostic_sessions`: UUID PK; student FK; status; nullable restart UUID;
  created/updated/completed timestamps. Status/completion check constraints,
  unique student/restart key, student/created index, and a partial unique index
  enforce at most one `in_progress` session per student.
- `diagnostic_assignments`: integer PK; session/question FKs; position; nullable
  attempt FK and client submission UUID. Constraints enforce positions 0..5,
  paired answer/UUID presence, unique session/position, session/question,
  session/submission UUID, and unique associated attempt.

Every operation first locks the same Student row used by ordinary attempts.
Concurrent start, answer, completion and restart operations serialize per student,
without a global/application mutex. The partial unique index is an additional DB
guard. Foreign keys prevent removing assigned questions or associated attempts.

Diagnostic submissions call the existing `create_attempt` service; no BKT formula,
parameter or scoring model is duplicated. A UUID5 derived from session UUID and
client submission UUID scopes the shared service's idempotency key to the session.
Reusing a client UUID in a different diagnostic is a separate intended attempt.
An unexpected collision with an ordinary practice attempt is rejected rather than
attaching it as diagnostic evidence. A second distinct UUID cannot re-answer the
same assignment. Recorded identical retries are allowed on completed/abandoned
sessions; all other submissions to those sessions are rejected.

Routes own commits/rollbacks. Attempt, mastery, feedback snapshots, assignment
association, and completion status persist in one transaction. An answer/restart
race either saves the answer before abandonment or rejects it afterward; no
learning is deleted. Retrying a restart key never abandons another newer session.
All session operations are scoped to the requested student.

Learning History now labels associated attempts `origin: "diagnostic"`; ordinary
attempts retain `"ordinary_practice"`. Its outer join is one-to-one (unique attempt
association), preserves cursor order/pagination and NULL snapshots, and adds no
per-row queries or answer-key fields. Clients displaying origins should accept
both values. The existing frontend does not display/use origin; its history API
type now accepts both values, with no diagnostic interface or display changes.

## Migration and development compatibility

Development must remain at **0004** during this stage. New diagnostic and history
queries need 0005; do not run them against the old schema. Ordinary question and
attempt operations require no new columns. No startup migration/import is added.

After a separately approved fresh verified backup and target/revision checks:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe verify_schema.py --revision 0004_question_bank
# Explicit approval required before this upgrade:
.\.venv\Scripts\python.exe -m alembic upgrade 0005_diagnostic_sessions
.\.venv\Scripts\python.exe verify_schema.py
.\.venv\Scripts\python.exe -m alembic check
```

Compare original rows, PK/FK relationships and sequences afterward; migration
creates empty diagnostic tables and leaves all existing data unchanged. Never
stamp/reset development. Downgrade removes diagnostic session/assignment metadata
only, retaining every original and diagnostic Attempt/Mastery record. It loses
resume/session UUID mappings and origin associations, so it is not a routine
rollback strategy once real sessions exist. Re-upgrade starts with empty session
tables and cannot reconstruct them from attempts; a verified backup is needed.

Tests run on guarded `skillforge_test_db` and disposable UUID-named PostgreSQL
databases. Development verification is read-only. No diagnostic frontend,
adaptive question selection, authentication, or expiry/automatic abandonment is
implemented.

## Files and validation

Added:

- `app/diagnostic_service.py`, `app/diagnostic_routes.py`, `app/diagnostic_schemas.py`
- `migrations/versions/0005_diagnostic_sessions.py`
- `test_diagnostics.py`, `test_diagnostic_migration.py`
- `DIAGNOSTIC_API.md`

Modified:

- `app/models.py`, `app/main.py`, `app/schemas.py`, `app/history_service.py`
- `conftest.py`, `verify_schema.py`
- `test_migrations.py`, `test_question_bank_migration.py` (older-revision
  comparisons remain explicit; current head checks include diagnostic tables).
- `HISTORY_API.md`, `MIGRATIONS.md`
- `../frontend/src/api/history.ts` (origin union only; no UI changes).

Validation: **221 backend tests passed**, including 15 new tests covering API
lifecycle, balanced persisted selection, missing coverage, ownership, exact-once
BKT updates, rollback, collisions, closed-session replay, history origins, existing
mastery, and concurrent starts/answers/restarts. Migration tests use disposable
PostgreSQL databases and verify upgrade/downgrade, old-row/sequence preservation,
NULL snapshots, partial uniqueness, and assignment foreign keys/uniqueness.
**88 frontend tests**, TypeScript, ESLint and production build passed. One existing
Starlette/httpx TestClient deprecation warning remains.

Development stayed at 0004. Complete rows/hashes, schema, PK/FK definitions and
sequence state matched the read-only checkpoint after all tests. No diagnostic
session/attempt was created in development and no deployment was performed.
