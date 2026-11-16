# Concept learning resources

`GET /concepts/{concept_id}/resources` is a public, read-only lesson endpoint.
No student ID or prerequisite eligibility is required. Reading never creates an
attempt, changes BKT mastery, or unlocks practice.

## Response

The response contains the actual database `concept_id` and `concept_name`,
`schema_version` (currently 1), `content_version` (currently `1.0.0`), and:

- `overview`: `explanation` and `why_it_matters`.
- `key_ideas`: objects with `term` and `explanation`.
- `worked_example`: `title`, ordered `steps`, `language`, `code`, and
  `expected_output` (the textual Python stdout).
- `common_mistakes`: objects with `mistake` and `explanation`.
- `complexity`: explicit `assumptions`, `notes`, and `operations`, each with
  `operation`, `time`, and `auxiliary_space`.
- `resources`: links with `title`, `url`, `resource_type`,
  `verification_status`, and nullable `verified_on`.

Unknown concept IDs return 404 `Concept not found`. An existing concept without
an exact-name lesson returns 404 `Learning resources not found for this concept`.
Malformed or unreadable content returns 500 with a clear content-unavailable
message; detailed validation errors are logged server-side. No fallback lesson
or dynamically generated text is returned. Noninteger IDs return FastAPI's 422.

## Content maintenance

The authored source is `data/concept_resources.json` at the repository root.
Include that file when distributing the backend. Mapping uses the database
concept's exact name, never a hardcoded ID. Renaming a concept requires updating
its lesson. The whole small catalog is validated on each read to avoid serving
partially valid or stale content. There is no network access or code execution
in the API; example code is returned as text only.

Validation rejects unknown fields, blank text, invalid field types, invalid
URLs, incomplete sections, duplicate concept names (case insensitive), and
duplicate JSON keys. At least two key ideas, two example steps, two mistakes,
and one explicitly scoped complexity operation are required. Resource lists may
be empty rather than supplying invented links. Verified links require a date;
unverified links must have a null verification date.

All eight current concept names are covered. Tests compare coverage with both
seed definitions and question references, and execute the repository-authored
Python examples against independently specified expected outputs. Examples
include array insertion, nested-loop counting, search indices, complete bubble
and merge sorts, factorial, and stable ordering of equal-key records.

Increment `content_version` for lesson edits; increment `schema_version` and
update the models and consumers together for structural changes. Run from
`backend`: ` .\.venv\Scripts\python.exe -m pytest test_resources.py -q -p no:cacheprovider`.
Tests use the existing guarded isolated PostgreSQL fixtures, not development.

## Link verification and review

All eight links were opened successfully on 2026-11-16, with the expected
educational page content: Python documentation (lists, bisect, sorting), and
Runestone's authored interactive textbook (analysis, sequential search, bubble
sort, merge sort, recursion). Blocked or unavailable candidate URLs were omitted.
Verification records availability on that date, not a guarantee of future
availability. No network link checks run during normal API requests or tests.

Lessons are original concise explanations. Complexity notes distinguish Python
lists from fixed arrays, amortized append from insertion, binary-search
preconditions and bisect insertion points, optimized bubble-sort best cases,
merge-sort peak storage, recursion stack/bit-cost assumptions, stability, and
the comparison-sort lower bound. Automated tests check structure and worked
outputs; future content edits still require human technical review.

No migration, database seed, dependency, or frontend change is needed.
