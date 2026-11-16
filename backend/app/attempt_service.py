import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bkt import INITIAL_MASTERY, update_mastery
from app.models import Attempt, Mastery, Question, Student
from app.schemas import AttemptCreate, AttemptResponse


def create_attempt(db: Session, attempt: AttemptCreate) -> AttemptResponse:
    """Validate and flush an attempt and its BKT update in the caller's transaction.

    The caller must commit on success or roll back on failure. This service never
    commits, rolls back, or closes the supplied session. Repeated calls are valid
    new practice attempts unless they reuse a non-null submission UUID.
    """
    # Lock an always-existing parent before looking up either retries or mastery.
    # Unlike locking Mastery alone, this also serializes first attempts.
    student = db.scalar(select(Student).where(
        Student.id == attempt.student_id,
    ).with_for_update())
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    if attempt.submission_id is not None:
        recorded = db.scalar(select(Attempt).where(
            Attempt.student_id == attempt.student_id,
            Attempt.submission_id == attempt.submission_id,
        ))
        if recorded is not None:
            if (recorded.question_id != attempt.question_id
                    or recorded.selected_answer != attempt.selected_answer):
                raise HTTPException(status_code=409, detail="Submission UUID already used with a different question or answer")
            if recorded.mastery_after is None:
                raise HTTPException(status_code=409, detail="Recorded submission has no mastery result")
            question = db.get(Question, recorded.question_id)
            return AttemptResponse(
                attempt_id=recorded.id,
                student_id=recorded.student_id,
                question_id=recorded.question_id,
                selected_answer=recorded.selected_answer,
                is_correct=recorded.is_correct,
                correct_answer=recorded.feedback_correct_answer if recorded.feedback_correct_answer is not None else question.correct_answer,
                mastery_probability=recorded.mastery_after,
                explanation=recorded.feedback_explanation,
            )

    question = db.get(Question, attempt.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    options = json.loads(question.options)
    if not 0 <= attempt.selected_answer < len(options):
        raise HTTPException(status_code=422, detail="Invalid answer option")

    is_correct = attempt.selected_answer == question.correct_answer
    mastery = db.scalar(
        select(Mastery).where(
            Mastery.student_id == attempt.student_id,
            Mastery.concept_id == question.concept_id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    prior_mastery = mastery.probability if mastery is not None else INITIAL_MASTERY
    new_probability = update_mastery(
        prior_mastery=prior_mastery,
        is_correct=is_correct,
    )

    new_attempt = Attempt(
        student_id=attempt.student_id,
        question_id=attempt.question_id,
        selected_answer=attempt.selected_answer,
        is_correct=is_correct,
        mastery_before=prior_mastery,
        mastery_after=new_probability,
        submission_id=attempt.submission_id,
        feedback_explanation=question.explanation,
        feedback_correct_answer=question.correct_answer,
    )
    db.add(new_attempt)

    if mastery is None:
        db.add(Mastery(
            student_id=attempt.student_id,
            concept_id=question.concept_id,
            probability=new_probability,
        ))
    else:
        mastery.probability = new_probability

    # Obtain the generated ID without ending the caller's transaction.
    db.flush()
    return AttemptResponse(
        attempt_id=new_attempt.id,
        student_id=new_attempt.student_id,
        question_id=new_attempt.question_id,
        selected_answer=new_attempt.selected_answer,
        is_correct=new_attempt.is_correct,
        correct_answer=question.correct_answer,
        mastery_probability=new_probability,
        explanation=new_attempt.feedback_explanation,
    )
