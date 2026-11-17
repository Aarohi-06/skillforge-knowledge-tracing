
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)


class Prerequisite(Base):
    __tablename__ = "prerequisites"

    id: Mapped[int] = mapped_column(primary_key=True)

    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id"), nullable=False
    )
    prerequisite_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "prerequisite_id",
            name="uq_concept_prerequisite"
        ),
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable for legacy/manual records; the supported importer requires keys.
    question_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20))

    options: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[int] = mapped_column(Integer)

    concept: Mapped["Concept"] = relationship()

    __table_args__ = (
        UniqueConstraint("question_key", name="uq_question_key"),
        Index("ix_questions_concept_id_id", "concept_id", "id"),
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"), nullable=False
    )

    selected_answer: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)

    mastery_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    mastery_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    submission_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    feedback_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_correct_answer: Mapped[int | None] = mapped_column(Integer, nullable=True)

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    __table_args__ = (
        UniqueConstraint("student_id", "submission_id", name="uq_student_submission"),
    )


class Mastery(Base):
    __tablename__ = "mastery"

    id: Mapped[int] = mapped_column(primary_key=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id"), nullable=False
    )

    probability: Mapped[float] = mapped_column(
        Float, default=0.2
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "concept_id",
            name="uq_student_concept"
        ),
    )


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    restart_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('in_progress','completed','abandoned')", name="ck_diagnostic_status"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_diagnostic_completion"),
        UniqueConstraint("student_id", "restart_id", name="uq_diagnostic_restart"),
        Index("ix_diagnostic_student_created", "student_id", "created_at"),
        Index("uq_diagnostic_active_student", "student_id", unique=True, postgresql_where=text("status = 'in_progress'")),
    )


class DiagnosticAssignment(Base):
    __tablename__ = "diagnostic_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("diagnostic_sessions.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)
    submission_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    __table_args__ = (
        CheckConstraint("position >= 0 AND position < 6", name="ck_diagnostic_position"),
        CheckConstraint("(attempt_id IS NULL) = (submission_id IS NULL)", name="ck_diagnostic_answer"),
        UniqueConstraint("session_id", "position", name="uq_diagnostic_position"),
        UniqueConstraint("session_id", "question_id", name="uq_diagnostic_question"),
        UniqueConstraint("session_id", "submission_id", name="uq_diagnostic_submission"),
        UniqueConstraint("attempt_id", name="uq_diagnostic_attempt"),
    )


class AdaptiveSession(Base):
    __tablename__ = "adaptive_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    completion_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    restart_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('in_progress','completed','abandoned')", name="ck_adaptive_status"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_adaptive_completion"),
        CheckConstraint("(status = 'completed' AND completion_reason IS NOT NULL AND completion_reason IN ('target_reached','eligible_pool_exhausted')) OR (status <> 'completed' AND completion_reason IS NULL)", name="ck_adaptive_completion_reason"),
        UniqueConstraint("student_id", "restart_id", name="uq_adaptive_restart"),
        Index("ix_adaptive_student_created", "student_id", "created_at"),
        Index("uq_adaptive_active_student", "student_id", unique=True, postgresql_where=text("status = 'in_progress'")),
    )


class AdaptiveAssignment(Base):
    __tablename__ = "adaptive_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_sessions.id"), nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)
    submission_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    __table_args__ = (
        CheckConstraint("position >= 0 AND position < 5", name="ck_adaptive_position"),
        CheckConstraint("(attempt_id IS NULL) = (submission_id IS NULL)", name="ck_adaptive_answer"),
        UniqueConstraint("session_id", "position", name="uq_adaptive_position"),
        UniqueConstraint("session_id", "question_id", name="uq_adaptive_question"),
        UniqueConstraint("session_id", "submission_id", name="uq_adaptive_submission"),
        UniqueConstraint("attempt_id", name="uq_adaptive_attempt"),
    )
