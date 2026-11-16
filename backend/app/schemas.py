
from typing import Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    concept_id: int
    title: str
    description: str
    difficulty: str
    options: list[str]



class AttemptCreate(BaseModel):
    student_id: int
    question_id: int
    selected_answer: int
    submission_id: UUID | None = None


class AttemptResponse(BaseModel):
    attempt_id: int
    student_id: int
    question_id: int
    selected_answer: int
    is_correct: bool
    correct_answer: int
    mastery_probability: float
    explanation: str | None = None


class ConceptProgressResponse(BaseModel):
    concept_id: int
    concept_name: str
    mastery_probability: float
    status: Literal["weak", "learning", "mastered"]
    attempted: bool


class ProgressSummary(BaseModel):
    total_concepts: int
    attempted_concepts: int
    mastered_concepts: int


class ProgressResponse(BaseModel):
    student_id: int
    summary: ProgressSummary
    concepts: list[ConceptProgressResponse]


class ConceptGraphNode(BaseModel):
    id: int
    name: str


class ConceptGraphEdge(BaseModel):
    source: int
    target: int


class ConceptGraphResponse(BaseModel):
    nodes: list[ConceptGraphNode]
    edges: list[ConceptGraphEdge]


class HistoryAttemptResponse(BaseModel):
    attempt_id: int
    question_id: int
    concept_id: int
    attempted_at: datetime
    is_correct: bool
    mastery_before: float | None
    mastery_after: float | None
    origin: Literal["ordinary_practice"] = "ordinary_practice"
    snapshots_available: bool


class LearningHistoryResponse(BaseModel):
    student_id: int
    concept_id: int | None
    attempts: list[HistoryAttemptResponse]
    next_cursor: str | None
