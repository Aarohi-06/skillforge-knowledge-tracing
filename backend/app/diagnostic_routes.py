from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import diagnostic_service as service
from app.diagnostic_schemas import DiagnosticAnswer, DiagnosticFeedback, DiagnosticProgress, DiagnosticRestart, DiagnosticResults

router = APIRouter(prefix="/students/{student_id}/diagnostics", tags=["diagnostics"])


def transaction(db, operation):
    try:
        response = operation()
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("/start", response_model=DiagnosticProgress)
def start(student_id: int, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.start(db, student_id))


@router.post("/restart", response_model=DiagnosticProgress)
def restart(student_id: int, request: DiagnosticRestart, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.start(db, student_id, request.request_id))


@router.get("/{session_id}", response_model=DiagnosticProgress)
def progress(student_id: int, session_id: UUID, db: Session = Depends(get_db)):
    service.lock_student(db, student_id)
    return service.progress(db, service.owned_session(db, student_id, session_id))


@router.post("/{session_id}/answers", response_model=DiagnosticFeedback)
def answer(student_id: int, session_id: UUID, request: DiagnosticAnswer, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.submit(db, student_id, session_id, request))


@router.post("/{session_id}/complete", response_model=DiagnosticResults)
def complete(student_id: int, session_id: UUID, db: Session = Depends(get_db)):
    return transaction(db, lambda: service.complete(db, student_id, session_id))


@router.get("/{session_id}/results", response_model=DiagnosticResults)
def results(student_id: int, session_id: UUID, db: Session = Depends(get_db)):
    service.lock_student(db, student_id)
    return service.results(db, service.owned_session(db, student_id, session_id))
