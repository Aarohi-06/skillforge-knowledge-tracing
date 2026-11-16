
import pytest
from sqlalchemy import select

from app.bkt import INITIAL_MASTERY, update_mastery
from app.models import Attempt, Concept, Mastery, Question, Student
from conftest import TestingSessionLocal


def test_correct_answer_creates_attempt_and_mastery(client):
    # Arrange: Create a student, concept, and question.
    with TestingSessionLocal() as db:
        student = Student(username="test_student")
        concept = Concept(
            name="Test Arrays",
            description="Testing array fundamentals",
        )

        db.add_all([student, concept])
        db.flush()

        question = Question(
            concept_id=concept.id,
            title="Array indexing",
            description="What is the index of the first array element?",
            difficulty="easy",
            options='["0", "1", "2", "3"]',
            correct_answer=0,
        )

        db.add(question)
        db.commit()

        student_id = student.id
        question_id = question.id
        concept_id = concept.id

    # Act: Submit a correct answer through the API.
    response = client.post(
        "/attempts",
        json={
            "student_id": student_id,
            "question_id": question_id,
            "selected_answer": 0,
        },
    )

    # Assert: Check the API response.
    assert response.status_code == 200

    data = response.json()
    assert data["is_correct"] is True
    assert data["correct_answer"] == 0

    expected_mastery = update_mastery(INITIAL_MASTERY, True)

    assert data["mastery_probability"] == pytest.approx(
        expected_mastery
    )

    # Assert: Check what PostgreSQL actually saved.
    with TestingSessionLocal() as db:
        attempts = db.scalars(select(Attempt)).all()
        masteries = db.scalars(select(Mastery)).all()

        assert len(attempts) == 1
        assert len(masteries) == 1

        assert attempts[0].student_id == student_id
        assert attempts[0].question_id == question_id
        assert attempts[0].is_correct is True

        assert masteries[0].student_id == student_id
        assert masteries[0].concept_id == concept_id
        assert masteries[0].probability == pytest.approx(
            expected_mastery
        )

#second test

def test_incorrect_answer_decreases_mastery(client):
    # Create test data.
    with TestingSessionLocal() as db:
        student = Student(username="test_student")
        concept = Concept(
            name="Test Arrays",
            description="Testing array fundamentals",
        )

        db.add_all([student, concept])
        db.flush()

        question = Question(
            concept_id=concept.id,
            title="Array indexing",
            description="What is the index of the first array element?",
            difficulty="easy",
            options='["0", "1", "2", "3"]',
            correct_answer=0,
        )

        db.add(question)
        db.commit()

        student_id = student.id
        question_id = question.id

    # Submit an incorrect answer (1 instead of 0).
    response = client.post(
        "/attempts",
        json={
            "student_id": student_id,
            "question_id": question_id,
            "selected_answer": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["is_correct"] is False
    assert data["mastery_probability"] < INITIAL_MASTERY

    expected_mastery = update_mastery(INITIAL_MASTERY, False)

    assert data["mastery_probability"] == pytest.approx(
        expected_mastery
    )

    # Verify the result was persisted.
    with TestingSessionLocal() as db:
        mastery = db.scalar(select(Mastery))

        assert mastery is not None
        assert mastery.probability == pytest.approx(
            expected_mastery
        )

#third test

def test_repeated_attempts_update_existing_mastery(client):
    # Arrange
    with TestingSessionLocal() as db:
        student = Student(username="test_student")
        concept = Concept(
            name="Test Arrays",
            description="Testing array fundamentals",
        )

        db.add_all([student, concept])
        db.flush()

        question = Question(
            concept_id=concept.id,
            title="Array indexing",
            description="What is the first array index?",
            difficulty="easy",
            options='["0", "1", "2", "3"]',
            correct_answer=0,
        )

        db.add(question)
        db.commit()

        student_id = student.id
        question_id = question.id

    # First attempt: correct answer
    first_response = client.post(
        "/attempts",
        json={
            "student_id": student_id,
            "question_id": question_id,
            "selected_answer": 0,
        },
    )

    assert first_response.status_code == 200

    first_mastery = first_response.json()["mastery_probability"]

    # Second attempt: incorrect answer
    second_response = client.post(
        "/attempts",
        json={
            "student_id": student_id,
            "question_id": question_id,
            "selected_answer": 1,
        },
    )

    assert second_response.status_code == 200

    second_mastery = second_response.json()["mastery_probability"]

    # Mastery should change after the second attempt.
    assert second_mastery < first_mastery

    # Verify PostgreSQL records.
    with TestingSessionLocal() as db:
        attempts = db.scalars(select(Attempt)).all()
        masteries = db.scalars(select(Mastery)).all()

        assert len(attempts) == 2
        assert len(masteries) == 1

        assert masteries[0].probability == pytest.approx(
            second_mastery
        )

#fourth test

def test_invalid_student_returns_404(client):
    # Create a valid concept and question.
    with TestingSessionLocal() as db:
        concept = Concept(
            name="Test Arrays",
            description="Testing array fundamentals",
        )

        db.add(concept)
        db.flush()

        question = Question(
            concept_id=concept.id,
            title="Array indexing",
            description="What is the first array index?",
            difficulty="easy",
            options='["0", "1", "2", "3"]',
            correct_answer=0,
        )

        db.add(question)
        db.commit()

        question_id = question.id

    # Submit an answer using a nonexistent student ID.
    response = client.post(
        "/attempts",
        json={
            "student_id": 999999,
            "question_id": question_id,
            "selected_answer": 0,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"

    # Invalid submissions must not create records.
    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all() == []
        assert db.scalars(select(Mastery)).all() == []
