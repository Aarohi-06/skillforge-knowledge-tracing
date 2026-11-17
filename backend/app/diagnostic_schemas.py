from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas import AttemptResponse, QuestionResponse


class DiagnosticAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: int = Field(strict=True, gt=0, le=2147483647)
    selected_answer: int = Field(strict=True, ge=0)
    submission_id: UUID


class DiagnosticRestart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


class DiagnosticProgress(BaseModel):
    session_id: UUID
    student_id: int
    status: Literal["in_progress", "completed", "abandoned"]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    total_questions: int
    answered_questions: int
    next_position: int | None
    next_question: QuestionResponse | None


class DiagnosticFeedback(BaseModel):
    session_id: UUID
    position: int
    feedback: AttemptResponse


class DiagnosticMastery(BaseModel):
    concept_id: int
    concept_name: str
    estimated_mastery: float | None
    status: Literal["weak", "learning", "mastered"] | None
    answered_questions: int


class DiagnosticResults(BaseModel):
    session_id: UUID
    student_id: int
    status: Literal["completed"]
    total_questions: int
    answered_questions: int
    correct_answers: int
    accuracy: float
    mastery_basis: Literal["last_diagnostic_attempt"] = "last_diagnostic_attempt"
    concepts: list[DiagnosticMastery]
