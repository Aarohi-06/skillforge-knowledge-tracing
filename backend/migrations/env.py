from alembic import context
from sqlalchemy import create_engine, pool

from app.database import Base, DATABASE_URL
from app import models  # noqa: F401 -- register models

target_metadata = Base.metadata


def run_with_connection(connection):
    context.configure(
        connection=connection, target_metadata=target_metadata,
        compare_type=True, compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True, compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_with_connection(connection)
    else:
        engine = create_engine(DATABASE_URL, poolclass=pool.NullPool)
        try:
            with engine.connect() as connection:
                run_with_connection(connection)
        finally:
            engine.dispose()
