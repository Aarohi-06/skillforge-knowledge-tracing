"""Add optional per-student submission UUIDs without changing existing attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0003_idempotent_submissions"
down_revision = "0002_attempt_mastery_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("attempts", sa.Column("submission_id", sa.Uuid(), nullable=True))
    # PostgreSQL permits multiple NULLs while enforcing non-null UUID uniqueness.
    op.create_unique_constraint("uq_student_submission", "attempts", ["student_id", "submission_id"])


def downgrade():
    op.drop_constraint("uq_student_submission", "attempts", type_="unique")
    op.drop_column("attempts", "submission_id")
