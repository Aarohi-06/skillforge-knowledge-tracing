"""Read-only schema comparison; never creates an Alembic version table."""
import argparse
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401 -- register models


SNAPSHOT_COLUMNS = {"mastery_before", "mastery_after"}


def schema_differences(connection, *, baseline=False, revision=None):
    if baseline:
        revision = "0001_existing_schema"
    excluded = set()
    if revision == "0001_existing_schema":
        excluded = SNAPSHOT_COLUMNS | {"submission_id"}
    elif revision == "0002_attempt_mastery_snapshots":
        excluded = {"submission_id"}
    question_excluded = set()
    if revision in {"0001_existing_schema", "0002_attempt_mastery_snapshots", "0003_idempotent_submissions"}:
        excluded |= {"feedback_explanation", "feedback_correct_answer"}
        question_excluded = {"question_key", "explanation"}
    context = MigrationContext.configure(connection, opts={
        "compare_type": True, "compare_server_default": True,
    })
    differences = compare_metadata(context, Base.metadata)
    inspector = inspect(connection)
    if excluded or question_excluded:
        omitted = {"attempts": excluded, "questions": question_excluded}
        ignored_constraints = {"uq_question_key"} if question_excluded else set()
        if "submission_id" in excluded:
            ignored_constraints.add("uq_student_submission")
        differences = [item for item in differences if not (
            item[0] == "add_column" and item[3].name in omitted.get(item[2], set())
        ) and not (
            item[0] == "add_constraint" and item[1].name in ignored_constraints
        ) and not (
            item[0] == "add_index" and question_excluded and item[1].name == "ix_questions_concept_id_id"
        )]
        for table, columns in omitted.items():
            if inspector.has_table(table):
                for column in inspector.get_columns(table):
                    if column["name"] in columns:
                        differences.append(("unexpected_revision_column", table, column["name"]))
        if question_excluded and inspector.has_table("questions"):
            if any(index["name"] == "ix_questions_concept_id_id" for index in inspector.get_indexes("questions")):
                differences.append(("unexpected_revision_index", "questions", "ix_questions_concept_id_id"))
    # Autogeneration does not reliably detect primary-key changes.
    for table in Base.metadata.sorted_tables:
        if inspector.has_table(table.name):
            actual = inspector.get_pk_constraint(table.name)["constrained_columns"]
            expected = [column.name for column in table.primary_key.columns]
            if actual != expected:
                differences.append(("primary_key_mismatch", table.name, actual, expected))
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--baseline", action="store_true", help="Compare against the pre-snapshot baseline schema")
    selection.add_argument("--revision", choices=["0001_existing_schema", "0002_attempt_mastery_snapshots", "0003_idempotent_submissions"], help="Compare against a supported older revision")
    args = parser.parse_args()
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            differences = schema_differences(connection, baseline=args.baseline, revision=args.revision)
        if differences:
            print("Schema differences found; DO NOT stamp this database:")
            for difference in differences:
                print(repr(difference))
            return 1
        print("No model/schema differences detected. No database changes were made.")
        print("Review the baseline and migration documentation before manually stamping.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
