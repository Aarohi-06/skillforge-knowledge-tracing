"""Persistent diagnostics; callers own transactions, shared service owns BKT."""
import json
from datetime import timezone
from uuid import uuid4, uuid5
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attempt_service import create_attempt
from app.diagnostic_schemas import DiagnosticAnswer, DiagnosticFeedback, DiagnosticProgress, DiagnosticResults
from app.mastery_rules import get_mastery_status
from app.models import Attempt, Concept, DiagnosticAssignment, DiagnosticSession, Question, Student, utc_now
from app.schemas import AttemptCreate, QuestionResponse

FOUNDATIONS = ("Arrays", "Time Complexity", "Recursion")


def lock_student(db: Session, student_id: int):
    student = db.scalar(select(Student).where(Student.id == student_id).with_for_update().execution_options(populate_existing=True))
    if student is None:
        raise HTTPException(404, "Student not found")


def owned_session(db, student_id, session_id):
    session = db.scalar(select(DiagnosticSession).where(DiagnosticSession.id == session_id, DiagnosticSession.student_id == student_id).execution_options(populate_existing=True))
    if session is None:
        raise HTTPException(404, "Diagnostic session not found")
    return session


def assignments(db, session):
    return db.scalars(select(DiagnosticAssignment).where(DiagnosticAssignment.session_id == session.id).order_by(DiagnosticAssignment.position).execution_options(populate_existing=True)).all()


def progress(db, session):
    rows = assignments(db, session)
    remaining = next((item for item in rows if item.attempt_id is None), None)
    question = db.get(Question, remaining.question_id) if remaining and session.status == "in_progress" else None
    public = QuestionResponse(id=question.id, concept_id=question.concept_id, title=question.title,
        description=question.description, difficulty=question.difficulty, options=json.loads(question.options)) if question else None
    return DiagnosticProgress(session_id=session.id, student_id=session.student_id, status=session.status,
        created_at=session.created_at.astimezone(timezone.utc), updated_at=session.updated_at.astimezone(timezone.utc),
        completed_at=session.completed_at.astimezone(timezone.utc) if session.completed_at else None,
        total_questions=len(rows), answered_questions=sum(item.attempt_id is not None for item in rows),
        next_position=remaining.position if public else None, next_question=public)


def start(db: Session, student_id: int, restart_id=None):
    lock_student(db, student_id)
    if restart_id is not None:
        replay = db.scalar(select(DiagnosticSession).where(DiagnosticSession.student_id == student_id, DiagnosticSession.restart_id == restart_id))
        if replay:
            return progress(db, replay)
    latest = db.scalar(select(DiagnosticSession).where(DiagnosticSession.student_id == student_id)
        .order_by((DiagnosticSession.status == "in_progress").desc(), DiagnosticSession.created_at.desc(), DiagnosticSession.id.desc()).limit(1))
    if restart_id is None and latest:
        return progress(db, latest)
    # Validate the entire bounded selection before abandoning the old session.
    selected = []
    for name in FOUNDATIONS:
        questions = db.scalars(select(Question).join(Concept).where(Concept.name == name)
            .order_by(Question.question_key.asc().nulls_last(), Question.id).limit(2)).all()
        if len(questions) != 2:
            raise HTTPException(409, f"Diagnostic requires at least two questions for {name}")
        selected.extend(questions)
    now = utc_now()
    if latest and latest.status == "in_progress":
        latest.status = "abandoned"
        latest.updated_at = now
        db.flush()  # Release the partial unique index slot before insertion.
    session = DiagnosticSession(id=uuid4(), student_id=student_id, restart_id=restart_id,
        status="in_progress", created_at=now, updated_at=now)
    db.add(session)
    db.flush()
    db.add_all([DiagnosticAssignment(session_id=session.id, position=index, question_id=question.id)
                for index, question in enumerate(selected)])
    db.flush()
    return progress(db, session)


def submit(db: Session, student_id: int, session_id, answer: DiagnosticAnswer):
    lock_student(db, student_id)
    session = owned_session(db, student_id, session_id)
    rows = assignments(db, session)
    replay = next((row for row in rows if row.submission_id == answer.submission_id), None)
    # Namespacing also prevents a client UUID used in another session from
    # accidentally reusing an earlier session's BKT update.
    internal_id = uuid5(session.id, str(answer.submission_id))
    if replay:
        recorded = db.get(Attempt, replay.attempt_id)
        if replay.question_id != answer.question_id or recorded.selected_answer != answer.selected_answer:
            raise HTTPException(409, "Diagnostic submission UUID already used with a different question or answer")
        feedback = create_attempt(db, AttemptCreate(student_id=student_id, question_id=answer.question_id,
            selected_answer=answer.selected_answer, submission_id=internal_id))
        return DiagnosticFeedback(session_id=session.id, position=replay.position, feedback=feedback)
    if session.status != "in_progress":
        raise HTTPException(409, "Diagnostic is not in progress")
    current = next((row for row in rows if row.attempt_id is None), None)
    if current is None or current.question_id != answer.question_id:
        raise HTTPException(409, "Answer the current assigned diagnostic question; skipping or resubmitting is not allowed")
    collision = db.scalar(select(Attempt.id).where(Attempt.student_id == student_id, Attempt.submission_id == internal_id))
    if collision is not None:
        raise HTTPException(409, "Submission identifier is already associated with another attempt")
    feedback = create_attempt(db, AttemptCreate(student_id=student_id, question_id=answer.question_id,
        selected_answer=answer.selected_answer, submission_id=internal_id))
    current.attempt_id = feedback.attempt_id
    current.submission_id = answer.submission_id
    session.updated_at = utc_now()
    if all(row.attempt_id is not None for row in rows):
        session.status = "completed"
        session.completed_at = session.updated_at
    db.flush()
    return DiagnosticFeedback(session_id=session.id, position=current.position, feedback=feedback)


def results(db, session):
    if session.status != "completed":
        raise HTTPException(409, "Diagnostic must be completed before retrieving results")
    rows = db.execute(select(DiagnosticAssignment, Attempt, Concept)
        .join(Attempt, Attempt.id == DiagnosticAssignment.attempt_id)
        .join(Question, Question.id == DiagnosticAssignment.question_id)
        .join(Concept, Concept.id == Question.concept_id)
        .where(DiagnosticAssignment.session_id == session.id).order_by(DiagnosticAssignment.position)).all()
    concepts = {}
    for assignment, attempt, concept in rows:
        previous = concepts.get(concept.id)
        concepts[concept.id] = dict(concept_id=concept.id, concept_name=concept.name,
            estimated_mastery=attempt.mastery_after,
            status=get_mastery_status(attempt.mastery_after) if attempt.mastery_after is not None else None,
            answered_questions=(previous['answered_questions'] if previous else 0) + 1)
    correct = sum(attempt.is_correct for _, attempt, _ in rows)
    return DiagnosticResults(session_id=session.id, student_id=session.student_id, status="completed",
        total_questions=len(rows), answered_questions=len(rows), correct_answers=correct,
        accuracy=correct / len(rows) if rows else 0, concepts=list(concepts.values()))


def complete(db, student_id, session_id):
    lock_student(db, student_id)
    session = owned_session(db, student_id, session_id)
    if session.status != "completed":
        raise HTTPException(409, "All six assigned questions must be answered to complete the diagnostic")
    return results(db, session)
