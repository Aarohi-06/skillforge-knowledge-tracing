from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel
from app.diagnostic_schemas import DiagnosticAnswer, DiagnosticRestart, DiagnosticMastery
from app.schemas import AttemptResponse, QuestionResponse

AdaptiveAnswer = DiagnosticAnswer
AdaptiveRestart = DiagnosticRestart


class AdaptiveProgress(BaseModel):
    session_id: UUID
    student_id: int
    status: Literal["in_progress", "completed", "abandoned"]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    target_questions: int = 5
    assigned_questions: int
    answered_questions: int
    next_position: int | None
    next_question: QuestionResponse | None
    selection_reason: str | None
    current_question_eligible: bool | None
    blocked_reason: str | None
    completion_reason: Literal["target_reached", "eligible_pool_exhausted"] | None


class AdaptiveFeedback(BaseModel):
    session_id: UUID
    position: int
    feedback: AttemptResponse


class AdaptiveQuestionResult(BaseModel):
    position: int
    question_id: int
    concept_id: int
    selection_reason: str
    is_correct: bool


class AdaptiveResults(BaseModel):
    session_id: UUID
    student_id: int
    status: Literal["completed"]
    target_questions: int = 5
    answered_questions: int
    correct_answers: int
    accuracy: float | None
    mastery_basis: Literal["last_adaptive_attempt"] = "last_adaptive_attempt"
    completion_reason: Literal["target_reached", "eligible_pool_exhausted"]
    concepts: list[DiagnosticMastery]
    questions: list[AdaptiveQuestionResult]
