
from sqlalchemy import text
from conftest import TestingSessionLocal

def test_database_is_isolated(client):
    with TestingSessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "skillforge_test_db"
