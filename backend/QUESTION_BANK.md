# Stage 9: scalable question bank and answer explanations

Stage 9 changes backend/content infrastructure only. No explanation UI or adaptive
selection is implemented, and no development migration/import is automatic.

## Identity and frozen adoption mapping

`data/questions.json` remains an array and adds required `question_key` and
`explanation` fields. Keys are explicitly authored permanent identifiers, not
computed from integer IDs, positions, titles, descriptions, or options. Allocate
a new unused key for a genuinely new question; never renumber existing keys.
Adding questions requires only JSON edits, not Python changes.

The frozen `migrations/data/0004_legacy_questions.json` captures all six original
identity fields plus reviewed keys and explanations. **Do not edit this migration
manifest when normal authored content changes.** Migration 0004 compares the
complete canonical record: concept name, title, description, difficulty, decoded
ordered options, and answer index. It does not match text alone or depend on IDs.
It verifies every existing row before schema changes. Unknown records or two rows
claiming one identity cause an explicit failure, leaving the transaction unchanged.
During migration the question table is locked before verification to prevent a
writer changing the verified identity before key assignment. Stop application
traffic and operator imports for adoption; this is migration DDL protection, not
an added application-level submission lock.
An empty database or a recognized subset is supported. Existing customized or
unknown legacy records require a separately reviewed mapping before adoption;
never guess, delete, or reseed them to make the migration pass.

At the Stage 9 read-only development checkpoint all 25 questions matched exactly.
The observed ID column below is audit evidence only, not the matching algorithm.

| Observed development ID | Stable key | Existing title |
| --- | --- | --- |
| 1 | `arrays-001` | Array Indexing |
| 2 | `arrays-002` | Array Insertion |
| 3 | `arrays-003` | Array Traversal |
| 4 | `time-complexity-001` | Big O Notation |
| 5 | `time-complexity-002` | Nested Loops |
| 6 | `time-complexity-003` | Logarithmic Complexity |
| 7 | `linear-search-001` | Linear Search Basics |
| 8 | `linear-search-002` | Linear Search Worst Case |
| 9 | `linear-search-003` | Linear Search Best Case |
| 10 | `binary-search-001` | Binary Search Requirement |
| 11 | `binary-search-002` | Binary Search Complexity |
| 12 | `binary-search-003` | Binary Search Midpoint |
| 13 | `bubble-sort-001` | Bubble Sort Comparison |
| 14 | `bubble-sort-002` | Bubble Sort Complexity |
| 15 | `bubble-sort-003` | Bubble Sort Optimization |
| 16 | `merge-sort-001` | Merge Sort Strategy |
| 17 | `merge-sort-002` | Merge Sort Complexity |
| 18 | `merge-sort-003` | Merge Sort Merge Step |
| 19 | `recursion-001` | Recursion Base Case |
| 20 | `recursion-002` | Recursive Factorial |
| 21 | `recursion-003` | Recursion Call Stack |
| 22 | `sorting-fundamentals-001` | Sorting Stability |
| 23 | `sorting-fundamentals-002` | Comparison Sorting |
| 24 | `sorting-fundamentals-003` | In-place Sorting |
| 25 | `sorting-fundamentals-004` | Sorting Lower Bound |

## Schema migration

Revision `0004_question_bank`, parent `0003_idempotent_submissions`, adds:

- `questions.question_key`: nullable varchar(100), unique constraint
  `uq_question_key` (PostgreSQL unique backing index).
- `questions.explanation`: nullable text.
- `(concept_id, id)` index `ix_questions_concept_id_id` for concept filtering,
  ordered ID pagination and future bounded candidate queries.
- `attempts.feedback_explanation`: nullable text snapshot.
- `attempts.feedback_correct_answer`: nullable integer snapshot.
- Trigger `immutable_question_key` and function `prevent_question_rekey` prevent
  changing/removing any already assigned non-null key, including direct SQL.

The reviewed 25 questions receive keys and explanations during migration, with no
changes to original question fields or IDs. No rows are inserted/deleted and no
sequences are advanced. Key nullability allows existing/manual client fixtures
and non-imported records; the supported importer always requires non-null keys.
It refuses to guess an identity for an unkeyed row. This avoids a fabricated
ID-derived default or a breaking non-null constraint for legacy writers.

Existing attempt fields, foreign keys, mastery probabilities, BKT snapshots, and
UUIDs remain unchanged. Historical explanation snapshots remain NULL because no
explanation was shown. The known unchanged answer index at adoption is captured
for historical retries; no old correctness or mastery is recalculated.

Downgrade removes only these new schema objects/columns. Questions and attempts
survive, but keys/explanations/feedback snapshots are lost. Re-upgrade can adopt
only the original frozen identities: databases with new/customized content after
0004 need a verified backup/reviewed identity plan. Downgrade is not a data backup
or a routine rollback strategy. This data-dependent migration requires an online
connection; offline `alembic --sql` generation is not supported.

## Import and dry-run

Run from `backend`, using the existing environment-selected database:

```powershell
.\.venv\Scripts\python.exe seed_questions.py --dry-run
.\.venv\Scripts\python.exe seed_questions.py --file ..\data\questions.json --dry-run
.\.venv\Scripts\python.exe seed_questions.py --file ..\data\questions.json
```

**The final command writes: run against development only after separate approval.**
Reports include `inserts`, `updates`, `unchanged`, and actionable `conflicts`.
Dry-run uses a PostgreSQL read-only transaction, including no sequence changes.
Malformed content exits nonzero; database mapping conflicts are reported and exit
nonzero. The write command validates the whole plan before writing, then commits
one transaction. Constraint/persistence errors roll everything back. Imports never
run at startup or delete omitted questions. Serialize operator imports; the unique
constraint rejects competing inserts rather than silently duplicating them.

Validation rejects duplicate JSON fields, duplicate keys, duplicate complete
records under alias keys, missing/unknown fields, blank strings, invalid types,
invalid difficulty/indices, duplicate options and unknown database concept names.
Matching uses only the key after migration. Full-record collision detection refuses
to create an alias for another existing row or adopt an unkeyed legacy row.
Permitted authored updates are title, description, difficulty, and explanation.
Changing concept/options/answer identity is rejected for existing keys; that needs
separate reviewed versioning, not a new key silently substituted for an old row.
No automated validator can prove a rewritten question has identical educational
meaning: content review is still required. Current wording/options/answers were
preserved for all 25 questions.

## API and feedback consistency

`POST /attempts` adds `explanation: string | null` to the existing response only
after valid submission. Missing explanations do not block practice. Both correct
and incorrect valid submissions receive the authored explanation. Existing UUID
conflict behavior, student-row locking, commits/rollbacks, BKT calculations and
mastery snapshots are unchanged.

New attempts snapshot the explanation **including an intentional NULL** and
correct-answer index. Matching UUID retries return these stored values, correctness,
and mastery_after; later authored edits cannot change recorded feedback. A new
attempt sees the currently authored explanation. Migrated historical attempts
return NULL explanations even after question explanations are added. Manually
created attempts with no answer snapshot retain the legacy answer-key fallback;
all normal new submissions and migrated historical records have a snapshot.

`GET /questions` retains its public fields and unfiltered array behavior. It never
returns keys, answer indices, explanations, or feedback snapshots. Optional query
parameters allow bounded selection in SQL:

```
GET /questions?concept_id=7&after_id=120&limit=20
```

`concept_id` must be positive, `after_id` nonnegative, and `limit` 1..100.
Results are ordered by ID; use the last ID as the next `after_id`. Unknown concept
filters return an empty array. The existing frontend still requests all questions
for compatibility; moving it to filtered retrieval is separate frontend work.
The primary key already supports individual question lookup during submission;
the unique key index supports import lookup and the composite index supports
concept/keyset queries. No adaptive selection/ranking is added.

History and lesson endpoints retain their explicit schemas and do not expose
answer keys or explanations. No new public bypass endpoint is introduced.

## Development adoption (not executed in Stage 9)

Development remains at **0003**. The Stage 9 ORM requires **0004** for question and
attempt operations. Until explicitly approved migration, running these operations
against the old development schema is incompatible. No startup migration is added.

After a fresh verified backup, target/revision checks, and explicit authorization:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe verify_schema.py --revision 0003_idempotent_submissions
.\.venv\Scripts\python.exe verify_question_mapping.py
# Stop for any mismatch; do not stamp or reset.
.\.venv\Scripts\python.exe -m alembic upgrade 0004_question_bank
.\.venv\Scripts\python.exe verify_schema.py
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe seed_questions.py --dry-run
```

The initial migration already populates the 25 explanations, so an unchanged source
should report 25 unchanged records; no follow-up write import is required. Compare
all old row counts/fields, attempts, mastery, foreign keys and sequence values with
the backup/checkpoint. Do not stamp an already versioned database.

Tests use only the guarded isolated test DB and UUID-named disposable migration
DBs. They cover all 25 explanations, correct/incorrect feedback, no pre-answer
leakage, snapshots/retries, import idempotence/rollback/dry-run/omission/conflicts,
immutable keys, SQL filtering and populated upgrade/downgrade preservation.

## Files and validation

Added:

- `app/question_import.py`
- `migrations/versions/0004_question_bank.py`
- `migrations/data/0004_legacy_questions.json`
- `verify_question_mapping.py`
- `test_question_bank.py`
- `test_question_bank_migration.py`
- `QUESTION_BANK.md`

Modified:

- `../data/questions.json`
- `app/models.py`, `app/schemas.py`, `app/main.py`, `app/attempt_service.py`
- `seed_questions.py`, `verify_schema.py`, `conftest.py`
- `test_migrations.py`, `test_attempt_service.py`, `test_mvp_integration.py`,
  `test_idempotent_attempts.py`
- `MIGRATIONS.md`

Stage 9 validation: 206 backend tests passed (58 added); frontend 77 tests,
TypeScript, ESLint, and production build passed. The existing Starlette/httpx
deprecation warning remains. Development was accessed read-only for schema,
identity and row-hash verification; no migration/import was applied there.
