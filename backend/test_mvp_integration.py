import pytest
from sqlalchemy import select

from app.bkt import INITIAL_MASTERY, update_mastery
from app.mastery_rules import get_mastery_status
from app.models import Attempt, Concept, Mastery, Prerequisite, Question, Student
from conftest import TestingSessionLocal


@pytest.fixture
def scenario(client):
    with TestingSessionLocal() as db:
        students = [Student(username=name) for name in ["learner", "other"]]
        concepts = [Concept(name=name) for name in ["Foundation", "Dependent", "Independent"]]
        db.add_all([*students, *concepts])
        db.flush()
        db.add(Prerequisite(prerequisite_id=concepts[0].id, concept_id=concepts[1].id))
        question = Question(
            concept_id=concepts[0].id, title="First index?", description="Choose one",
            difficulty="easy", options='["0", "1"]', correct_answer=0,
        )
        db.add(question)
        db.commit()
        return {
            "student": students[0].id, "other": students[1].id,
            "root": concepts[0].id, "dependent": concepts[1].id,
            "independent": concepts[2].id, "question": question.id,
        }


def test_answer_progress_recommendation_graph_flow_and_student_isolation(client, scenario):
    s = scenario
    other_progress = client.get(f"/progress/{s['other']}").json()
    other_recommendations = client.get(f"/recommendations/{s['other']}").json()
    assert client.get("/concept-graph").json()["edges"] == [
        {"source": s["root"], "target": s["dependent"]},
    ]
    probability = INITIAL_MASTERY
    # Explicit repeated attempts remain allowed; each must update exactly once.
    for count, correct in enumerate([False, True, True, True, False], start=1):
        prior = probability
        answer = 0 if correct else 1
        result = client.post("/attempts", json={
            "student_id": s["student"], "question_id": s["question"], "selected_answer": answer,
        })
        assert result.status_code == 200
        probability = update_mastery(probability, correct)
        feedback = result.json()
        assert set(feedback) == {
            "attempt_id", "student_id", "question_id", "selected_answer",
            "is_correct", "correct_answer", "mastery_probability", "explanation",
        }
        assert feedback["is_correct"] is correct
        assert feedback["selected_answer"] == answer
        assert feedback["mastery_probability"] == pytest.approx(probability)

        progress = client.get(f"/progress/{s['student']}").json()
        root = next(item for item in progress["concepts"] if item["concept_id"] == s["root"])
        assert root["attempted"] is True
        assert root["mastery_probability"] == pytest.approx(probability)
        assert root["status"] == get_mastery_status(probability)
        assert progress["summary"] == {
            "total_concepts": 3, "attempted_concepts": 1,
            "mastered_concepts": int(root["status"] == "mastered"),
        }
        for item in progress["concepts"]:
            if item["concept_id"] != s["root"]:
                assert item["attempted"] is False
                assert item["mastery_probability"] == INITIAL_MASTERY

        response = client.get(f"/recommendations/{s['student']}").json()
        recommendations = response["recommendations"]
        assert response["total_recommendations"] == len(recommendations)
        ids = [item["concept_id"] for item in recommendations]
        assert (s["dependent"] in ids) == (root["status"] == "mastered")
        if root["status"] != "mastered":
            assert ids[0] == s["root"]
            assert recommendations[0]["action"] == ("revise" if root["status"] == "weak" else "practice")
        else:
            assert s["root"] not in ids
        for item in recommendations:
            assert set(item) == {"concept_id", "concept_name", "mastery_probability", "status", "action", "reason"}
            assert item["reason"]
            if item["concept_id"] != s["root"]:
                assert item["action"] == "learn"

        assert client.get(f"/progress/{s['other']}").json() == other_progress
        assert client.get(f"/recommendations/{s['other']}").json() == other_recommendations
        with TestingSessionLocal() as db:
            attempts = db.scalars(select(Attempt).order_by(Attempt.id)).all()
            assert len(attempts) == count
            assert attempts[-1].selected_answer == answer
            assert attempts[-1].student_id == s["student"]
            assert attempts[-1].is_correct is correct
            assert attempts[-1].mastery_before == pytest.approx(prior)
            assert attempts[-1].mastery_after == pytest.approx(probability)
            masteries = db.scalars(select(Mastery)).all()
            assert len(masteries) == 1
            assert masteries[0].probability == pytest.approx(probability)


@pytest.mark.parametrize("field,value,status,detail", [
    ("student_id", 999999, 404, "Student not found"),
    ("question_id", 999999, 404, "Question not found"),
    ("selected_answer", -1, 422, "Invalid answer option"),
    ("selected_answer", 2, 422, "Invalid answer option"),
    ("selected_answer", 999999, 422, "Invalid answer option"),
])
def test_invalid_attempts_do_not_write(client, scenario, field, value, status, detail):
    payload = {"student_id": scenario["student"], "question_id": scenario["question"], "selected_answer": 0}
    payload[field] = value
    response = client.post("/attempts", json=payload)
    assert response.status_code == status
    assert response.json()["detail"] == detail
    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all() == []
        assert db.scalars(select(Mastery)).all() == []


def test_questions_do_not_expose_answers(client, scenario):
    response = client.get("/questions")
    assert response.status_code == 200
    assert len(response.json()) == 1
    question = response.json()[0]
    assert set(question) == {"id", "concept_id", "title", "description", "difficulty", "options"}
    assert question["options"] == ["0", "1"]
    assert question["id"] == scenario["question"]


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_local_frontend_can_submit_with_cors(client, origin):
    response = client.options("/attempts", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_empty_recommendations_for_existing_student(client):
    with TestingSessionLocal() as db:
        student = Student(username="empty_student")
        db.add(student)
        db.commit()
        student_id = student.id
    response = client.get(f"/recommendations/{student_id}")
    assert response.status_code == 200
    assert response.json() == {"student_id": student_id, "total_recommendations": 0, "recommendations": []}
