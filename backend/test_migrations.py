from pathlib import Path
import os
import re
import subprocess
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import UniqueConstraint, create_engine, inspect, text

from app.database import Base
from conftest import test_engine
from verify_schema import schema_differences


BASELINE = "0001_existing_schema"
SNAPSHOTS = "0002_attempt_mastery_snapshots"
IDEMPOTENCY = "0003_idempotent_submissions"


@pytest.fixture
def migration_engine():
    # Administrative SQL goes through the guarded TEST_DATABASE_URL, never the
    # development engine. Only a freshly generated name can be created/dropped.
    name = f"skillforge_migration_test_{uuid4().hex}"
    assert re.fullmatch(r"skillforge_migration_test_[0-9a-f]{32}", name)
    assert name != test_engine.url.database
    engine = create_engine(test_engine.url.set(database=name))
    created = False
    try:
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
        created = True
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == name
        yield engine
    finally:
        engine.dispose()
        if created:
            assert re.fullmatch(r"skillforge_migration_test_[0-9a-f]{32}", name)
            with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
                admin.execute(text(f'DROP DATABASE "{name}"'))


def config(connection):
    cfg = Config(str(Path(__file__).with_name("alembic.ini")))
    cfg.attributes["connection"] = connection
    return cfg


def test_empty_database_upgrades_through_baseline_to_snapshots_without_pending_changes(migration_engine):
    with migration_engine.begin() as connection:
        assert inspect(connection).get_table_names() == []
        cfg = config(connection)
        command.upgrade(cfg, BASELINE)
        assert MigrationContext.configure(connection).get_current_revision() == BASELINE
        assert schema_differences(connection, baseline=True) == []
        assert not {"mastery_before", "mastery_after"} & {
            column["name"] for column in inspect(connection).get_columns("attempts")
        }
        command.upgrade(cfg, SNAPSHOTS)
        assert MigrationContext.configure(connection).get_current_revision() == SNAPSHOTS
        assert schema_differences(connection, revision=SNAPSHOTS) == []
        command.upgrade(cfg, IDEMPOTENCY)
        assert MigrationContext.configure(connection).get_current_revision() == IDEMPOTENCY
        assert schema_differences(connection, revision=IDEMPOTENCY) == []

        command.upgrade(cfg, "head")
        command.check(cfg)
        assert schema_differences(connection) == []

        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
        for table in Base.metadata.sorted_tables:
            actual_columns = {item["name"]: item for item in inspector.get_columns(table.name)}
            assert set(actual_columns) == set(table.columns.keys())
            assert inspector.get_pk_constraint(table.name)["constrained_columns"] == ["id"]
            assert len(inspector.get_foreign_keys(table.name)) == len(table.foreign_key_constraints)
            expected_unique = {
                tuple(column.name for column in constraint.columns): constraint.name
                for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
            }
            actual_unique = inspector.get_unique_constraints(table.name)
            assert {tuple(item["column_names"]) for item in actual_unique} == set(expected_unique)
            for item in actual_unique:
                expected_name = expected_unique[tuple(item["column_names"])]
                if expected_name:
                    assert item["name"] == expected_name
            # The concept/keyset query index is the sole non-unique index.
            assert {index.name for index in table.indexes} == ({"ix_questions_concept_id_id"} if table.name == "questions" else set())
            assert all(item.get("duplicates_constraint") or item["name"] == "ix_questions_concept_id_id" for item in inspector.get_indexes(table.name))
            for column in table.columns:
                actual = actual_columns[column.name]
                assert actual["nullable"] == column.nullable
                if not column.primary_key:
                    assert actual["default"] is None
                else:
                    assert connection.scalar(text("SELECT pg_get_serial_sequence(:table, 'id')"), {"table": table.name})

        # Upgrading an already versioned schema is a no-op.
        command.upgrade(cfg, "head")
        command.check(cfg)


def test_existing_unversioned_baseline_can_be_verified_and_explicitly_stamped(migration_engine):
    # Emulate the old bootstrap only in a new disposable database.
    with migration_engine.begin() as connection:
        command.upgrade(config(connection), BASELINE)
        connection.execute(text("DROP TABLE alembic_version"))
    with migration_engine.begin() as connection:
        connection.execute(text("INSERT INTO concepts (name, description) VALUES ('Preserved', 'Existing data')"))

    with migration_engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        assert schema_differences(connection, baseline=True) == []
        assert "alembic_version" not in inspect(connection).get_table_names()

    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.stamp(cfg, BASELINE)
        command.upgrade(cfg, IDEMPOTENCY)
        assert schema_differences(connection, revision=IDEMPOTENCY) == []
        assert connection.scalar(text("SELECT description FROM concepts WHERE name='Preserved'")) == "Existing data"
        assert schema_differences(connection, revision=IDEMPOTENCY) == []


def test_schema_verification_reports_drift_without_modifying_database(migration_engine):
    with migration_engine.begin() as connection:
        command.upgrade(config(connection), IDEMPOTENCY)
        connection.execute(text("ALTER TABLE concepts ADD COLUMN unexpected TEXT"))
    with migration_engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        differences = schema_differences(connection, revision=IDEMPOTENCY)
        assert any(item[0] == "remove_column" for item in differences)
        assert "unexpected" in {item["name"] for item in inspect(connection).get_columns("concepts")}


def test_baseline_downgrade_and_reupgrade_only_in_disposable_database(migration_engine):
    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.upgrade(cfg, IDEMPOTENCY)
        command.downgrade(cfg, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        assert MigrationContext.configure(connection).get_current_revision() is None
        command.upgrade(cfg, IDEMPOTENCY)
        assert schema_differences(connection, revision=IDEMPOTENCY) == []


def test_cli_uses_environment_database_url(migration_engine):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = migration_engine.url.render_as_string(hide_password=False)
    for arguments in (["upgrade", "head"], ["check"]):
        subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=Path(__file__).parent,
            env=environment, check=True, capture_output=True, text=True,
        )
    with migration_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == "0004_question_bank"
        assert schema_differences(connection) == []


def test_snapshot_migration_preserves_legacy_attempts_and_current_mastery(migration_engine):
    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.upgrade(cfg, BASELINE)
        student_id = connection.scalar(text("INSERT INTO students (username, created_at) VALUES ('legacy', CURRENT_TIMESTAMP) RETURNING id"))
        concept_id = connection.scalar(text("INSERT INTO concepts (name) VALUES ('Legacy Arrays') RETURNING id"))
        question_id = connection.scalar(text("""
            INSERT INTO questions (concept_id, title, description, difficulty, options, correct_answer)
            VALUES (:concept, 'Index', 'First index?', 'easy', '["0", "1"]', 0) RETURNING id
        """), {"concept": concept_id})
        parameters = {"student": student_id, "question": question_id, "concept": concept_id}
        connection.execute(text("""
            INSERT INTO attempts (student_id, question_id, selected_answer, is_correct, attempted_at)
            VALUES (:student, :question, 0, TRUE, CURRENT_TIMESTAMP),
                   (:student, :question, 1, FALSE, CURRENT_TIMESTAMP)
        """), parameters)
        connection.execute(text("""
            INSERT INTO mastery (student_id, concept_id, probability, updated_at)
            VALUES (:student, :concept, 0.6, CURRENT_TIMESTAMP)
        """), parameters)
        original_attempts = connection.execute(text("SELECT * FROM attempts ORDER BY id")).mappings().all()
        original_mastery = connection.execute(text("SELECT * FROM mastery")).mappings().all()

        command.upgrade(cfg, SNAPSHOTS)
        rows = connection.execute(text("SELECT * FROM attempts ORDER BY id")).mappings().all()
        assert len(rows) == 2
        for original, row in zip(original_attempts, rows):
            assert row["mastery_before"] is None
            assert row["mastery_after"] is None
            assert {key: row[key] for key in original} == dict(original)
        assert connection.execute(text("SELECT * FROM mastery")).mappings().all() == original_mastery
        assert schema_differences(connection, revision=SNAPSHOTS) == []
        # A snapshot-schema database must never be mistaken for the old baseline.
        assert len(schema_differences(connection, baseline=True)) == 2

        connection.execute(text("UPDATE attempts SET mastery_before=0.2, mastery_after=0.6 WHERE selected_answer=0"))
        command.downgrade(cfg, BASELINE)
        assert connection.execute(text("SELECT * FROM attempts ORDER BY id")).mappings().all() == original_attempts
        assert connection.execute(text("SELECT * FROM mastery")).mappings().all() == original_mastery
        assert schema_differences(connection, baseline=True) == []
        command.upgrade(cfg, SNAPSHOTS)
        assert connection.scalar(text("SELECT count(*) FROM attempts WHERE mastery_before IS NULL AND mastery_after IS NULL")) == 2
        command.upgrade(cfg, IDEMPOTENCY)
        assert schema_differences(connection, revision=IDEMPOTENCY) == []


def test_submission_uuid_migration_preserves_data_and_enforces_student_scope(migration_engine):
    from sqlalchemy.exc import IntegrityError

    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.upgrade(cfg, SNAPSHOTS)
        connection.execute(text("INSERT INTO students (id,username,created_at) VALUES (1,'one',CURRENT_TIMESTAMP),(2,'two',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO concepts (id,name) VALUES (1,'Arrays')"))
        connection.execute(text("""INSERT INTO questions (id,concept_id,title,description,difficulty,options,correct_answer)
            VALUES (1,1,'Index','First index?','easy','["0","1"]',0)"""))
        connection.execute(text("""INSERT INTO attempts (student_id,question_id,selected_answer,is_correct,attempted_at,mastery_before,mastery_after)
            VALUES (1,1,0,TRUE,CURRENT_TIMESTAMP,0.2,0.6),(1,1,1,FALSE,CURRENT_TIMESTAMP,NULL,NULL)"""))
        connection.execute(text("INSERT INTO mastery (student_id,concept_id,probability,updated_at) VALUES (1,1,0.6,CURRENT_TIMESTAMP)"))
        old = connection.execute(text("SELECT * FROM attempts ORDER BY id")).mappings().all()
        mastery = connection.execute(text("SELECT * FROM mastery")).mappings().all()
        command.upgrade(cfg, IDEMPOTENCY)
        rows = connection.execute(text("SELECT * FROM attempts ORDER BY id")).mappings().all()
        assert all(row['submission_id'] is None for row in rows)
        assert [{key: row[key] for key in old[0]} for row in rows] == old
        assert connection.execute(text("SELECT * FROM mastery")).mappings().all() == mastery
        key = uuid4()
        connection.execute(text("UPDATE attempts SET submission_id=:key WHERE id=1"), {"key": key})
        statement = text("""INSERT INTO attempts (student_id,question_id,selected_answer,is_correct,attempted_at,submission_id)
            VALUES (:student,1,0,TRUE,CURRENT_TIMESTAMP,:key)""")
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(statement, {"student": 1, "key": key})
        connection.execute(statement, {"student": 2, "key": key})
        connection.execute(statement, {"student": 1, "key": None})
        connection.execute(statement, {"student": 1, "key": None})
        assert connection.scalar(text("SELECT count(*) FROM attempts")) == 5
        assert schema_differences(connection, revision=IDEMPOTENCY) == []
        command.downgrade(cfg, SNAPSHOTS)
        assert connection.scalar(text("SELECT count(*) FROM attempts")) == 5
        assert connection.execute(text("SELECT * FROM attempts WHERE id <= 2 ORDER BY id")).mappings().all() == old
        assert connection.execute(text("SELECT * FROM mastery")).mappings().all() == mastery
        assert schema_differences(connection, revision=SNAPSHOTS) == []
        command.upgrade(cfg, IDEMPOTENCY)
        assert connection.scalar(text("SELECT count(*) FROM attempts WHERE submission_id IS NULL")) == 5
        assert schema_differences(connection, revision=IDEMPOTENCY) == []
