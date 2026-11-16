
from app.models import Concept, Prerequisite, Mastery, Student
from conftest import TestingSessionLocal


def test_recommendations_respect_prerequisites(client):
    # Create a student and two related concepts.
    with TestingSessionLocal() as db:
        student = Student(username="test_student")

        arrays = Concept(
            name="Arrays",
            description="Array fundamentals",
        )
        binary_search = Concept(
            name="Binary Search",
            description="Searching sorted arrays",
        )

        db.add_all([student, arrays, binary_search])
        db.flush()

        db.add(
            Prerequisite(
                concept_id=binary_search.id,
                prerequisite_id=arrays.id,
            )
        )

        db.commit()

        student_id = student.id
        arrays_id = arrays.id
        binary_search_id = binary_search.id

    # Arrays is not mastered yet.
    response = client.get(f"/recommendations/{student_id}")

    assert response.status_code == 200

    recommendations = response.json()["recommendations"]
    recommended_ids = {
        item["concept_id"] for item in recommendations
    }

    assert arrays_id in recommended_ids
    assert binary_search_id not in recommended_ids

    # Now mark Arrays as mastered.
    with TestingSessionLocal() as db:
        db.add(
            Mastery(
                student_id=student_id,
                concept_id=arrays_id,
                probability=0.90,
            )
        )
        db.commit()

    # Binary Search should now be unlocked.
    response = client.get(f"/recommendations/{student_id}")

    assert response.status_code == 200

    recommendations = response.json()["recommendations"]
    recommended_ids = {
        item["concept_id"] for item in recommendations
    }

    assert binary_search_id in recommended_ids


def test_invalid_student_recommendations(client):
    response = client.get("/recommendations/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"
