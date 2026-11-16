import pytest
from sqlalchemy import select

from app.bkt import INITIAL_MASTERY, update_mastery
from app.mastery_rules import get_mastery_status
from app.models import Attempt, Concept, Mastery, Question, Student
from conftest import TestingSessionLocal


def test_progress_includes_all_concepts_and_isolates_students(client):
    with TestingSessionLocal() as db:
        student = Student(username="progress_student")
        other = Student(username="other_student")
        concepts = [Concept(name=name) for name in ["Arrays", "Stacks", "Trees", "Graphs"]]
        db.add_all([student, other, *concepts])
        db.flush()
        student_id = student.id
        concept_ids = [concept.id for concept in concepts]
        probabilities = [INITIAL_MASTERY, 0.60, 0.90]
        for concept, probability in zip(concepts, probabilities):
            db.add(Mastery(student_id=student.id, concept_id=concept.id, probability=probability))
        db.add(Mastery(student_id=other.id, concept_id=concepts[3].id, probability=0.95))
        db.commit()

    response = client.get(f"/progress/{student_id}")

    assert response.status_code == 200
    assert response.json() == {
        "student_id": student_id,
        "summary": {"total_concepts": 4, "attempted_concepts": 3, "mastered_concepts": 1},
        "concepts": [
            {
                "concept_id": concept_id,
                "concept_name": name,
                "mastery_probability": probability,
                "status": status,
                "attempted": attempted,
            }
            for concept_id, name, probability, status, attempted in zip(
                concept_ids,
                ["Arrays", "Stacks", "Trees", "Graphs"],
                [INITIAL_MASTERY, 0.60, 0.90, INITIAL_MASTERY],
                ["weak", "learning", "mastered", "weak"],
                [True, True, True, False],
            )
        ],
    }


@pytest.mark.parametrize("probability,status", [
    (0.0, "weak"), (0.3999, "weak"), (0.40, "learning"),
    (0.7999, "learning"), (0.80, "mastered"), (1.0, "mastered"),
])
def test_progress_uses_existing_thresholds(client, probability, status):
    with TestingSessionLocal() as db:
        student = Student(username="threshold_student")
        concept = Concept(name="Arrays")
        db.add_all([student, concept])
        db.flush()
        student_id = student.id
        db.add(Mastery(student_id=student.id, concept_id=concept.id, probability=probability))
        db.commit()

    response = client.get(f"/progress/{student_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["concepts"][0]["status"] == status
    assert data["concepts"][0]["mastery_probability"] == probability
    assert data["summary"]["mastered_concepts"] == int(status == "mastered")


@pytest.mark.parametrize("with_concept", [False, True])
def test_progress_for_new_student_is_read_only(client, with_concept):
    with TestingSessionLocal() as db:
        student = Student(username="new_student")
        db.add(student)
        if with_concept:
            db.add(Concept(name="Arrays"))
        db.commit()
        student_id = student.id

    first = client.get(f"/progress/{student_id}")
    second = client.get(f"/progress/{student_id}")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    data = first.json()
    assert data["summary"] == {
        "total_concepts": int(with_concept), "attempted_concepts": 0, "mastered_concepts": 0,
    }
    if with_concept:
        assert data["concepts"][0]["mastery_probability"] == INITIAL_MASTERY
        assert data["concepts"][0]["attempted"] is False
    else:
        assert data["concepts"] == []
    with TestingSessionLocal() as db:
        assert db.scalars(select(Mastery)).all() == []
        assert db.scalars(select(Attempt)).all() == []


def test_progress_reflects_submitted_attempt_without_updating_mastery(client):
    with TestingSessionLocal() as db:
        student = Student(username="practice_student")
        concept = Concept(name="Arrays")
        db.add_all([student, concept])
        db.flush()
        question = Question(
            concept_id=concept.id, title="First index?", description="Choose an index",
            difficulty="easy", options='["0", "1"]', correct_answer=0,
        )
        db.add(question)
        db.commit()
        student_id, question_id = student.id, question.id

    attempt = client.post("/attempts", json={
        "student_id": student_id, "question_id": question_id, "selected_answer": 0,
    })
    assert attempt.status_code == 200
    expected = update_mastery(INITIAL_MASTERY, True)
    for _ in range(2):
        response = client.get(f"/progress/{student_id}")
        assert response.status_code == 200
        progress = response.json()["concepts"][0]
        assert progress["attempted"] is True
        assert progress["mastery_probability"] == pytest.approx(expected)
        assert progress["status"] == get_mastery_status(expected)
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 1
        masteries = db.scalars(select(Mastery)).all()
        assert len(masteries) == 1
        assert masteries[0].probability == pytest.approx(expected)


def test_progress_nonexistent_student(client):
    response = client.get("/progress/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Student not found"}
