from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import adaptive_service as service
from app.diagnostic_routes import transaction
from app.adaptive_schemas import AdaptiveAnswer, AdaptiveFeedback, AdaptiveProgress, AdaptiveRestart, AdaptiveResults

router = APIRouter(prefix="/students/{student_id}/adaptive-sessions", tags=["adaptive-practice"])



@router.post("/start", response_model=AdaptiveProgress)
def start(student_id: int, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.start(db, student_id))


@router.post("/restart", response_model=AdaptiveProgress)
def restart(student_id: int, request: AdaptiveRestart, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.start(db, student_id, request.request_id))


@router.get("/{session_id}", response_model=AdaptiveProgress)
def progress(student_id: int, session_id: UUID, db: Session = Depends(get_db)):
    service.lock_student(db, student_id)
    return service.progress(db, service.owned(db, student_id, session_id))


@router.post("/{session_id}/answers", response_model=AdaptiveFeedback)
def answer(student_id: int, session_id: UUID, request: AdaptiveAnswer, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.submit(db, student_id, session_id, request))


@router.get("/{session_id}/results", response_model=AdaptiveResults)
def results(student_id: int, session_id: UUID, db: Session = Depends(get_db)):
    service.lock_student(db, student_id)
    return service.results(db, service.owned(db, student_id, session_id))
