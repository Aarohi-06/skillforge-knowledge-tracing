from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.attempt_service import create_attempt
from app.bkt import INITIAL_MASTERY, update_mastery
from app.main import submit_attempt
from app.models import Attempt, Concept, Mastery, Question, Student
from app.schemas import AttemptCreate
from conftest import TestingSessionLocal


@pytest.fixture
def practice_data(client):
    # The existing client fixture clears only the isolated test database.
    with TestingSessionLocal() as db:
        student = Student(username="service_student")
        concept = Concept(name="Service Arrays")
        db.add_all([student, concept])
        db.flush()
        question = Question(
            concept_id=concept.id, title="First index?", description="Choose an index",
            difficulty="easy", options='["0", "1"]', correct_answer=0,
        )
        db.add(question)
        db.commit()
        return student.id, question.id, concept.id


def seed_mastery(practice_data, probability):
    if probability is not None:
        student_id, _, concept_id = practice_data
        with TestingSessionLocal() as db:
            db.add(Mastery(student_id=student_id, concept_id=concept_id, probability=probability))
            db.commit()


@pytest.mark.parametrize("prior", [None, 0.0, 0.6])
@pytest.mark.parametrize("answer", [0, 1])
def test_service_flushes_correct_update_without_owning_transaction(practice_data, prior, answer):
    seed_mastery(practice_data, prior)
    student_id, question_id, concept_id = practice_data
    expected = update_mastery(INITIAL_MASTERY if prior is None else prior, answer == 0)

    with TestingSessionLocal() as db:
        with patch.object(db, "commit", wraps=db.commit) as commit, patch.object(db, "rollback", wraps=db.rollback) as rollback:
            result = create_attempt(db, AttemptCreate(
                student_id=student_id, question_id=question_id, selected_answer=answer,
            ))
            commit.assert_not_called()
            rollback.assert_not_called()

        assert result.model_dump() == {
            "attempt_id": result.attempt_id,
            "student_id": student_id, "question_id": question_id,
            "selected_answer": answer, "is_correct": answer == 0,
            "correct_answer": 0, "mastery_probability": pytest.approx(expected), "explanation": None,
        }
        assert result.attempt_id is not None
        attempt = db.get(Attempt, result.attempt_id)
        assert attempt.selected_answer == answer
        assert attempt.mastery_before == pytest.approx(INITIAL_MASTERY if prior is None else prior)
        assert attempt.mastery_after == pytest.approx(expected)
        mastery = db.scalar(select(Mastery))
        assert mastery.concept_id == concept_id
        assert mastery.probability == pytest.approx(expected)

        # A separate connection must still see only the original committed state.
        with TestingSessionLocal() as observer:
            assert observer.scalars(select(Attempt)).all() == []
            original = observer.scalar(select(Mastery))
            assert (original is None) == (prior is None)
            if original is not None:
                assert original.probability == prior

        db.commit()

    with TestingSessionLocal() as db:
        attempts = db.scalars(select(Attempt)).all()
        assert len(attempts) == 1
        assert attempts[0].mastery_before == pytest.approx(INITIAL_MASTERY if prior is None else prior)
        assert attempts[0].mastery_after == pytest.approx(expected)
        assert db.scalar(select(Mastery)).probability == pytest.approx(expected)


@pytest.mark.parametrize("field,value,status,detail", [
    ("student_id", 999999, 404, "Student not found"),
    ("question_id", 999999, 404, "Question not found"),
    ("selected_answer", -1, 422, "Invalid answer option"),
    ("selected_answer", 2, 422, "Invalid answer option"),
])
def test_service_invalid_input_does_not_stage_writes(practice_data, field, value, status, detail):
    student_id, question_id, _ = practice_data
    payload = dict(student_id=student_id, question_id=question_id, selected_answer=0)
    payload[field] = value
    with TestingSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            create_attempt(db, AttemptCreate(**payload))
        assert error.value.status_code == status
        assert error.value.detail == detail
        assert not db.new
        assert not db.dirty
        assert db.scalars(select(Attempt)).all() == []
        assert db.scalars(select(Mastery)).all() == []


def test_service_allows_repeated_attempts_in_the_same_transaction(practice_data):
    student_id, question_id, _ = practice_data
    request = AttemptCreate(student_id=student_id, question_id=question_id, selected_answer=0)
    with TestingSessionLocal() as db:
        first = create_attempt(db, request)
        second = create_attempt(db, request)
        assert first.attempt_id != second.attempt_id
        expected = update_mastery(update_mastery(INITIAL_MASTERY, True), True)
        assert second.mastery_probability == pytest.approx(expected)
        db.commit()
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 2
        assert len(db.scalars(select(Mastery)).all()) == 1
        assert db.scalar(select(Mastery)).probability == pytest.approx(expected)
        attempts = db.scalars(select(Attempt).order_by(Attempt.id)).all()
        assert attempts[0].mastery_before == INITIAL_MASTERY
        assert attempts[0].mastery_after == pytest.approx(first.mastery_probability)
        assert attempts[1].mastery_before == pytest.approx(attempts[0].mastery_after)
        assert attempts[1].mastery_after == pytest.approx(expected)


@pytest.mark.parametrize("prior", [None, 0.6])
@pytest.mark.parametrize("failure_point", ["flush", "commit"])
def test_route_rolls_back_attempt_and_mastery_on_transaction_failure(practice_data, prior, failure_point):
    seed_mastery(practice_data, prior)
    student_id, question_id, _ = practice_data
    request = AttemptCreate(student_id=student_id, question_id=question_id, selected_answer=0)
    with TestingSessionLocal() as db:
        original_flush = db.flush

        def fail(*args, **kwargs):
            if failure_point == "flush":
                original_flush(*args, **kwargs)
                # Real PostgreSQL error after both records were written, before commit.
                db.execute(text("SELECT 1 / 0"))
            raise SQLAlchemyError("Simulated commit failure")

        with patch.object(db, failure_point, side_effect=fail), patch.object(db, "rollback", wraps=db.rollback) as rollback:
            with pytest.raises(SQLAlchemyError):
                submit_attempt(request, db)
            rollback.assert_called_once_with()

        # Rollback must also restore the failed session to usable state.
        assert db.scalar(text("SELECT 1")) == 1

    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all() == []
        mastery = db.scalar(select(Mastery))
        assert (mastery is None) == (prior is None)
        if mastery is not None:
            assert mastery.probability == prior


def test_legacy_attempt_with_null_snapshots_remains_valid(practice_data):
    student_id, question_id, _ = practice_data
    with TestingSessionLocal() as db:
        legacy = Attempt(student_id=student_id, question_id=question_id, selected_answer=1, is_correct=False)
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id
        create_attempt(db, AttemptCreate(student_id=student_id, question_id=question_id, selected_answer=0))
        db.commit()
    with TestingSessionLocal() as db:
        legacy = db.get(Attempt, legacy_id)
        assert legacy.mastery_before is None
        assert legacy.mastery_after is None
        assert len(db.scalars(select(Attempt)).all()) == 2
