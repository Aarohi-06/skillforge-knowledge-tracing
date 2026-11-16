
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app import models  # Register all SQLAlchemy models


load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is missing from .env")

if TEST_DATABASE_URL == os.getenv("DATABASE_URL"):
    raise RuntimeError("Test database must be different from development database")

if TEST_DATABASE_URL.rsplit("/", 1)[-1] != "skillforge_test_db":
    raise RuntimeError("Refusing to run tests against an unexpected database")

test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="session", autouse=True)
def migrate_isolated_test_database():
    # Only the guarded skillforge_test_db is eligible for this automatic setup.
    # Development adoption remains an explicit operator action.
    from verify_schema import schema_differences

    with test_engine.begin() as connection:
        cfg = Config(str(Path(__file__).with_name("alembic.ini")))
        cfg.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        revision = MigrationContext.configure(connection).get_current_revision()
        if revision is None and tables:
            if schema_differences(connection, baseline=True) == []:
                command.stamp(cfg, "0001_existing_schema")
            elif schema_differences(connection, revision="0002_attempt_mastery_snapshots") == []:
                command.stamp(cfg, "0002_attempt_mastery_snapshots")
            elif schema_differences(connection, revision="0003_idempotent_submissions") == []:
                command.stamp(cfg, "0003_idempotent_submissions")
            elif schema_differences(connection) == []:
                command.stamp(cfg, "0004_question_bank")
            else:
                raise RuntimeError("Isolated test schema has unexpected drift; refusing automatic adoption")
        command.upgrade(cfg, "head")
        command.check(cfg)


@pytest.fixture
def client():
    # Start each test with empty tables.
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
