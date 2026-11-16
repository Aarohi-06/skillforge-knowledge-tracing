"""Record actual per-attempt mastery estimates; preserve unknown history as NULL.

Revision ID: 0002_attempt_mastery_snapshots
Revises: 0001_existing_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_attempt_mastery_snapshots"
down_revision = "0001_existing_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("attempts", sa.Column("mastery_before", sa.Float(), nullable=True))
    op.add_column("attempts", sa.Column("mastery_after", sa.Float(), nullable=True))


def downgrade():
    # Existing attempts survive, but recorded snapshots are lost on downgrade.
    op.drop_column("attempts", "mastery_after")
    op.drop_column("attempts", "mastery_before")
