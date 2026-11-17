"""Persist ordered resumable diagnostics without altering existing rows."""
from alembic import op
import sqlalchemy as sa

revision = "0005_diagnostic_sessions"
down_revision = "0004_question_bank"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("diagnostic_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("restart_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('in_progress','completed','abandoned')", name="ck_diagnostic_status"),
        sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_diagnostic_completion"),
        sa.UniqueConstraint("student_id", "restart_id", name="uq_diagnostic_restart"),
    )
    op.create_index("ix_diagnostic_student_created", "diagnostic_sessions", ["student_id", "created_at"])
    op.create_index("uq_diagnostic_active_student", "diagnostic_sessions", ["student_id"], unique=True, postgresql_where=sa.text("status = 'in_progress'"))
    op.create_table("diagnostic_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("diagnostic_sessions.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=True),
        sa.Column("submission_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("position >= 0 AND position < 6", name="ck_diagnostic_position"),
        sa.CheckConstraint("(attempt_id IS NULL) = (submission_id IS NULL)", name="ck_diagnostic_answer"),
        sa.UniqueConstraint("session_id", "position", name="uq_diagnostic_position"),
        sa.UniqueConstraint("session_id", "question_id", name="uq_diagnostic_question"),
        sa.UniqueConstraint("session_id", "submission_id", name="uq_diagnostic_submission"),
        sa.UniqueConstraint("attempt_id", name="uq_diagnostic_attempt"),
    )


def downgrade():
    op.drop_table("diagnostic_assignments")
    op.drop_index("uq_diagnostic_active_student", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_student_created", table_name="diagnostic_sessions")
    op.drop_table("diagnostic_sessions")
