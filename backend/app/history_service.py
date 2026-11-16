import base64
import binascii
from datetime import timezone
import json

from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.models import Attempt, Concept, Question, Student
from app.schemas import HistoryAttemptResponse, LearningHistoryResponse


class HistoryCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(strict=True)
    student_id: int = Field(strict=True)
    concept_id: int | None = Field(strict=True)
    attempted_at: AwareDatetime
    attempt_id: int = Field(strict=True, gt=0, le=2147483647)


def decode_cursor(token: str, student_id: int, concept_id: int | None) -> HistoryCursor:
    try:
        decoded = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        position = HistoryCursor.model_validate(json.loads(decoded))
        if position.version != 1 or position.student_id != student_id or position.concept_id != concept_id:
            raise ValueError("Cursor scope/version mismatch")
        return position
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError, ValidationError):
        raise HTTPException(status_code=422, detail="Invalid history cursor") from None


def encode_cursor(item: HistoryAttemptResponse, student_id: int, concept_id: int | None) -> str:
    position = HistoryCursor(
        version=1, student_id=student_id, concept_id=concept_id,
        attempted_at=item.attempted_at.astimezone(timezone.utc), attempt_id=item.attempt_id,
    )
    return base64.urlsafe_b64encode(position.model_dump_json().encode()).decode().rstrip("=")


def get_learning_history(
    db: Session, student_id: int, concept_id: int | None, limit: int, cursor: str | None,
) -> LearningHistoryResponse:
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if concept_id is not None and db.get(Concept, concept_id) is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    query = select(
        Attempt.id.label("attempt_id"), Attempt.question_id, Question.concept_id,
        Attempt.attempted_at, Attempt.is_correct, Attempt.mastery_before, Attempt.mastery_after,
    ).join(Question, Question.id == Attempt.question_id).where(Attempt.student_id == student_id)
    if concept_id is not None:
        query = query.where(Question.concept_id == concept_id)
    if cursor is not None:
        position = decode_cursor(cursor, student_id, concept_id)
        query = query.where(tuple_(Attempt.attempted_at, Attempt.id) > (
            position.attempted_at, position.attempt_id,
        ))

    rows = db.execute(query.order_by(Attempt.attempted_at, Attempt.id).limit(limit + 1)).all()
    attempts = [HistoryAttemptResponse(
        **{**row._mapping, "attempted_at": row.attempted_at.astimezone(timezone.utc)},
        snapshots_available=row.mastery_before is not None and row.mastery_after is not None,
    ) for row in rows[:limit]]
    next_cursor = encode_cursor(attempts[-1], student_id, concept_id) if len(rows) > limit else None
    return LearningHistoryResponse(
        student_id=student_id, concept_id=concept_id, attempts=attempts, next_cursor=next_cursor,
    )
