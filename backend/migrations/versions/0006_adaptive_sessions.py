"""Persist ordered resumable adaptives without altering existing rows."""
from alembic import op
import sqlalchemy as sa

revision = "0006_adaptive_sessions"
down_revision = "0005_diagnostic_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("adaptive_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completion_reason", sa.String(40), nullable=True),
        sa.Column("restart_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('in_progress','completed','abandoned')", name="ck_adaptive_status"),
        sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_adaptive_completion"),
        sa.CheckConstraint("(status = 'completed' AND completion_reason IS NOT NULL AND completion_reason IN ('target_reached','eligible_pool_exhausted')) OR (status <> 'completed' AND completion_reason IS NULL)", name="ck_adaptive_completion_reason"),
        sa.UniqueConstraint("student_id", "restart_id", name="uq_adaptive_restart"),
    )
    op.create_index("ix_adaptive_student_created", "adaptive_sessions", ["student_id", "created_at"])
    op.create_index("uq_adaptive_active_student", "adaptive_sessions", ["student_id"], unique=True, postgresql_where=sa.text("status = 'in_progress'"))
    op.create_table("adaptive_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("adaptive_sessions.id"), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=True),
        sa.Column("submission_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("position >= 0 AND position < 5", name="ck_adaptive_position"),
        sa.CheckConstraint("(attempt_id IS NULL) = (submission_id IS NULL)", name="ck_adaptive_answer"),
        sa.UniqueConstraint("session_id", "position", name="uq_adaptive_position"),
        sa.UniqueConstraint("session_id", "question_id", name="uq_adaptive_question"),
        sa.UniqueConstraint("session_id", "submission_id", name="uq_adaptive_submission"),
        sa.UniqueConstraint("attempt_id", name="uq_adaptive_attempt"),
    )


def downgrade():
    op.drop_table("adaptive_assignments")
    op.drop_index("uq_adaptive_active_student", table_name="adaptive_sessions")
    op.drop_index("ix_adaptive_student_created", table_name="adaptive_sessions")
    op.drop_table("adaptive_sessions")
