# Learning History API (Stage 5)

`GET /students/{student_id}/history`

Read-only access to recorded attempts and fixed-parameter BKT estimates. These
estimates are not test scores or validated measurements of learning outcomes.
No new schema or migrations are required.

## Query parameters

| Parameter | Default | Validation |
| --- | --- | --- |
| `concept_id` | No filter | Positive PostgreSQL integer; existing concept required |
| `limit` | 50 | Integer from 1 to 100 |
| `cursor` | First page | Non-empty opaque cursor, at most 1024 characters |

Missing students return 404 `Student not found`; missing concepts return 404
`Concept not found`. Invalid query parameters or cursors return 422. Existing
students/concepts with no matching attempts receive 200 with an empty list and
`next_cursor: null`.

## Response

```json
{
  "student_id": 1,
  "concept_id": null,
  "attempts": [
    {
      "attempt_id": 12,
      "question_id": 3,
      "concept_id": 1,
      "attempted_at": "2026-01-01T10:00:00Z",
      "is_correct": true,
      "mastery_before": 0.2,
      "mastery_after": 0.5764705882352941,
      "origin": "ordinary_practice",
      "snapshots_available": true
    }
  ],
  "next_cursor": null
}
```

The example illustrates the contract, not a particular student's records.
Timestamps represent the recorded instant in UTC. Snapshot values are returned
without rounding or recomputation. `snapshots_available` is true only when both
values are present, including valid zero values. Legacy/partial snapshots stay
NULL; clients must not fill them with initial mastery or interpolated estimates.

Attempts associated with a persisted diagnostic assignment have origin
`diagnostic` (Stage 11); adaptive assignments yield `adaptive_practice` (Stage 13).
All other attempts retain `ordinary_practice`. The one-to-one optional assignment
joins preserve the response layout and pagination.
No selected answer, correct-answer
index, option content, username, or submission UUID is exposed.

## Pagination

Results are oldest first, ordered by `(attempted_at ASC, attempt_id ASC)`.
The cursor is versioned URL-safe base64 JSON containing the last returned
timestamp (including microseconds), ID, student ID, and concept filter. Clients
should treat it as opaque and follow the returned `next_cursor`.

The next page uses the strict tuple comparison `(attempted_at, id) > position`,
so equal timestamps do not skip or repeat records. The service fetches `limit+1`
rows and emits a cursor only if that extra row exists. Clients may change page
size while retaining the cursor, but must retain the student and concept filter.
Changing the filter/student requires starting a fresh traversal.

This is forward pagination over live data, not a frozen multi-request snapshot.
New records after the cursor can appear on later pages. Backdated inserts or
changes to ordering/filter fields behind the cursor require a fresh traversal.
Ordinary application submissions do not edit historical attempts.

## Isolation and operational limits

Every query predicates on the requested student, regardless of cursor contents.
Cursors are validated and scoped but unsigned: they are positions, not access
tokens. The MVP's caller-supplied student ID is still not authentication or
authorization. Public deployment requires a separately approved identity model.

The history query joins questions once to resolve concept IDs and left-joins
diagnostic and adaptive assignments through their unique attempt associations. Query count is
bounded (student validation, optional concept validation, one page query), with
no per-attempt database access. Existing indexes/schema are unchanged; larger
datasets may later warrant a separately reviewed history index. Concept IDs are
resolved from the current question association; question-content versioning is
outside this stage.
