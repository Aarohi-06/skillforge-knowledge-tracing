# SkillForge database migrations

Run commands from `backend`, using its virtual environment. Alembic reads
`DATABASE_URL` through the existing `app.database` / python-dotenv configuration.
An explicitly set environment variable takes precedence over `.env`. Credentials
must not be placed in `alembic.ini`, migration files, or source control.

Install the pinned backend requirements before using these commands:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Baseline

Revision `0001_existing_schema` represents only the current six application tables:
`concepts`, `students`, `prerequisites`, `questions`, `mastery`, and `attempts`.
It includes existing integer primary keys/sequences, seven foreign keys, four
unique constraints, column types/nullability, and timezone-aware timestamps.
There are no explicit model indexes beyond primary-key/unique backing indexes.
Python-side timestamp and probability defaults remain Python-side; this revision
does not add server defaults, data, or any enhancement tables/columns.
Alembic manages its own `alembic_version` infrastructure table.

Application imports/startup do not run Alembic. The existing `create_tables.py`
remains unchanged, but must not be used to upgrade existing tables. The API test
suite now verifies/adopts only its guarded isolated database and upgrades it
through Alembic before running tests. It never migrates the development database.

## Stage 3: per-attempt snapshots

Revision `0002_attempt_mastery_snapshots` adds nullable `Float` columns
`attempts.mastery_before` and `attempts.mastery_after`, consistent with the existing
mastery representation. There are no defaults, backfill, or data rewrites.
Historical attempts retain NULL snapshots. New submissions record the actual
prior probability and BKT result in the same transaction as the attempt and
current mastery. The public attempt request/response is unchanged.

The updated ORM cannot insert/query attempts against an unmigrated baseline
database. In particular, POST /attempts requires Stage 3 schema adoption before
the updated backend can be used for a local demo. No automatic adoption is
performed at application startup. Do not use `create_all()` as a workaround.
Downgrading this revision drops only the snapshot columns: attempts survive, but
snapshot data is lost and a later upgrade leaves those values NULL again.

## A genuinely empty database

Create an empty PostgreSQL database separately and explicitly point `DATABASE_URL`
at it. Verify the target locally without printing/sharing credentials. Then:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade 0003_idempotent_submissions
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

Do not run the baseline upgrade on a database with existing application tables;
it intentionally uses ordinary CREATE statements and will fail on conflicts.

## Safely adopt an existing, unversioned database

These are manual operator actions, not application startup actions. No existing
development database is automatically stamped or upgraded by this change.

1. Back up the database, verify restoration on a disposable clone, and arrange a
   quiet maintenance window. Inspect the exact target database and schema.
2. Review `app/models.py` and the baseline revision. Rehearse the process on the
   restored clone first.
3. Run this read-only check against the intended target:

   ```powershell
   .\.venv\Scripts\python.exe verify_schema.py --baseline
   ```

   Baseline mode accounts for the snapshot columns and submission UUID/constraint
   not belonging to revision `0001_existing_schema`, and rejects later columns
   if they are already present. This
   option must be maintained if future stages change the models further. Without
   this option, verification compares against the latest ORM schema instead.
   It compares types, nullability, foreign keys, unique constraints, indexes,
   server defaults, and primary-key columns. It enforces a read-only PostgreSQL
   transaction and does not create `alembic_version`. Exit code 1 means drift:
   **stop and investigate; do not stamp or automatically apply suggested changes.**
4. Review any database-specific objects separately, including triggers, grants,
   sequence ownership/current values, extensions, views and non-default schemas.
   The checker is not a complete database audit. Confirm there is no unrelated
   migration history and that the database still matches this baseline, not a
   future revision.
5. Only after verification and explicit operator approval, record this exact
   baseline revision:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic stamp 0001_existing_schema
   .\.venv\Scripts\python.exe -m alembic current
   ```

   Stamping writes revision metadata; it does not run the baseline's table DDL
   or repair schema mismatches. Use the explicit baseline, not `head`, since
   future migrations may have been added. Compare representative row counts and
   application behavior before/after.

6. As a separate, explicitly reviewed Stage 3 adoption operation, apply the
   additive snapshot revision, then verify the latest schema:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade 0002_attempt_mastery_snapshots
   .\.venv\Scripts\python.exe verify_schema.py --revision 0002_attempt_mastery_snapshots
   ```

   If the database is already versioned at `0001_existing_schema`, do not stamp
   it again: verify the baseline and apply the upgrade after approval. If it
   already has snapshot columns but no revision history, stop and investigate;
   do not apply the baseline adoption instructions blindly.

7. After separate Stage 4 approval, apply `0003_idempotent_submissions` as
   described below. `alembic check` compares against the latest models and must
   be run only after upgrading to the latest revision.

If a database is partial or differs from the baseline, prepare a separate reviewed
reconciliation plan. Do not drop/recreate it or stamp past those differences.

## Stage 4: idempotent submissions and student-level serialization

Revision `0003_idempotent_submissions` adds only nullable PostgreSQL UUID column
`attempts.submission_id` and unique constraint `uq_student_submission` on
`(student_id, submission_id)`. PostgreSQL permits multiple NULL keys. No existing
rows, mastery values, or snapshot values are rewritten; old UUID values stay NULL.

POST /attempts accepts an optional UUID. A matching key/payload for the same
student returns stored attempt identity, correctness and `mastery_after`, even
after later practice changed current mastery. Conflicting question/answer reuse
returns 409. Keys are scoped by student. Omitting a key (or sending NULL) keeps
intentional repeated practice. The response still contains its original seven
fields; no submission UUID is added to the response.

All service submissions acquire a PostgreSQL row lock on Student before retry
lookup or mastery access. The existing route owns commit/rollback, which releases
the lock. This covers concurrent first attempts and applies across processes,
without global locks. Direct writes bypassing this service must follow the same
locking protocol; the unique constraint remains a database-level safeguard.

The frontend retains a generated UUID for the same student/question/answer after
an error. Changing the payload or resetting Practice for a new attempt generates
a fresh key. Its existing synchronous in-flight guard prevents rapid repeated
clicks from issuing separate intended submissions. Pending keys are memory-only:
refreshing or reopening the app starts a new intent. The question bank is not
versioned: correctness and mastery are stored, while `correct_answer` is read from
the existing unchanged question. This stage does not support historical answer-key
edits or authentication; student IDs remain demo identity.

The development database is not automatically migrated. The Stage 4 ORM needs
revision 0003 before local attempt submission/querying can work. For a database
already at 0002, after backup verification and explicit approval only:

```powershell
.\.venv\Scripts\python.exe verify_schema.py --revision 0002_attempt_mastery_snapshots
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade 0003_idempotent_submissions
.\.venv\Scripts\python.exe verify_schema.py
.\.venv\Scripts\python.exe -m alembic check
```

Do not re-stamp an already versioned database. Downgrading 0003 removes only the
UUID constraint/column; attempts and snapshots survive, but old keys are lost.
Re-upgrading leaves those keys NULL and cannot recover their retry identity.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest test_migrations.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Migration tests use the guarded `TEST_DATABASE_URL` only as an administrative
connection. The role must have CREATEDB permission. Each test creates its own
`skillforge_migration_test_<random UUID>` database from `template0`, supplies its
connection explicitly to Alembic, disposes connections and drops only that
generated database. No development data is read or written by these tests.
The ordinary API tests continue to use `skillforge_test_db`. A session fixture
verifies its schema, explicitly adopts a verified unversioned baseline or exact
current schema, upgrades to head, and runs Alembic check. Unexpected drift fails
setup instead of resetting tables. Per-test row cleanup remains confined to that
isolated database. Run this suite serially: the API fixture is not designed for parallel
workers sharing that database.

Tests cover empty upgrade, Alembic check/no drift, constraints/indexes/sequences,
explicit adoption preserving existing data, drift detection, and downgrade/
reupgrade, including preservation of historical attempt rows and NULL snapshots.
A forced process interruption may leave a disposable database behind;
inspect ownership/name and active connections before manually cleaning it up.

The baseline downgrade drops application tables and data. It is tested only in
disposable databases and must never be used as an adoption or repair command.

## Future revisions

After a separately approved model change, use a disposable database upgraded to
the current revision to generate and test a candidate:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "Describe approved change"
```

Review every operation before applying it. Alembic autogeneration is not a
complete schema verifier; see the [official limitations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect).

## Stage 9 question bank

Revision `0004_question_bank` adds stable question identities, explanations and
recorded attempt feedback. See [QUESTION_BANK.md](QUESTION_BANK.md) for the frozen
adoption mapping, compatibility limits, backup/approval procedure and commands.
Development is intentionally not upgraded automatically. The earlier Stage 4
answer-key reconstruction limitation is superseded for migrated/new attempts by
the Stage 9 feedback snapshots.

## Stage 11 diagnostics

Revision `0005_diagnostic_sessions` adds two empty tables for persistent diagnostic
sessions and ordered question/attempt associations. Existing tables and records
are not altered. See [DIAGNOSTIC_API.md](DIAGNOSTIC_API.md) for endpoints,
transaction/idempotency rules, constraints, testing, and the separately approved
development upgrade procedure. Development remains at 0004 during implementation.
Downgrade removes session metadata but retains attempts and mastery; it loses
resume and diagnostic-origin associations and must not be used as a routine
production rollback. No development migration is automatic.

## Stage 13 adaptive sessions

Revision `0006_adaptive_sessions` adds empty adaptive session/assignment tables,
persisted selection reasons and lifecycle/idempotency constraints without altering
existing data or diagnostic tables. See [ADAPTIVE_API.md](ADAPTIVE_API.md) for
selection policy, API contracts, constraints, limitations and the separately
approved development upgrade procedure. Development remains at 0005 during
implementation. Downgrade retains attempts/mastery but loses adaptive session
metadata and origin associations; no development upgrade or rollback is automatic.
