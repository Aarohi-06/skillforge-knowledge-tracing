import ast
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from sqlalchemy import event, select

from app import resource_service
from app.models import Attempt, Concept, Mastery, Prerequisite, Student
from app.resource_service import ContentError, load_catalog
from conftest import TestingSessionLocal, test_engine

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "data/concept_resources.json").read_text(encoding="utf-8"))
NAMES = [lesson["concept_name"] for lesson in CATALOG["lessons"]]


def test_catalog_matches_seed_and_question_concepts():
    tree = ast.parse((ROOT / "backend/seed_concepts.py").read_text())
    seed = next(ast.literal_eval(node.value) for node in ast.walk(tree)
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "concept_data" for t in node.targets))
    questions = json.loads((ROOT / "data/questions.json").read_text(encoding="utf-8"))
    assert len(load_catalog().lessons) == 8
    assert set(NAMES) == {row[0] for row in seed} == {q["concept"] for q in questions}


@pytest.mark.parametrize("name,expected", list(zip(NAMES, [
    "40\n[10, 15, 20, 40]", "9", "2", "3", "[1, 2, 4, 5]",
    "[1, 2, 3, 4, 7, 9]", "24", "['B', 'A', 'C']",
])))
def test_authored_examples_execute_with_reviewed_output(name, expected):
    lesson = next(item for item in load_catalog().lessons if item.concept_name == name)
    output = io.StringIO()
    # Execute only version-controlled, locally authored examples, never API input.
    with redirect_stdout(output):
        exec(compile(lesson.worked_example.code, f"lesson:{name}", "exec"), {})
    assert output.getvalue().strip() == expected == lesson.worked_example.expected_output


@pytest.mark.parametrize("index,name", list(enumerate(NAMES)))
def test_all_resources_map_by_database_name_not_fixed_id(client, index, name):
    concept_id = 400 + (7 - index) * 13
    with TestingSessionLocal() as db:
        db.add(Concept(id=concept_id, name=name))
        db.commit()
    response = client.get(f"/concepts/{concept_id}/resources")
    assert response.status_code == 200
    data = response.json()
    assert data["concept_id"] == concept_id
    assert data["concept_name"] == name
    assert data["schema_version"] == 1
    assert data["content_version"] == "1.0.0"
    assert set(data) == {"concept_id", "concept_name", "schema_version", "content_version", "overview", "key_ideas", "worked_example", "common_mistakes", "complexity", "resources"}
    assert len(data["common_mistakes"]) >= 2
    assert all(link["verification_status"] == "verified" for link in data["resources"])


def test_unknown_and_missing_resources(client):
    assert client.get("/concepts/999999/resources").json() == {"detail": "Concept not found"}
    assert client.get("/concepts/999999/resources").status_code == 404
    with TestingSessionLocal() as db:
        concept = Concept(name="Unmapped concept")
        db.add(concept)
        db.commit()
        concept_id = concept.id
    response = client.get(f"/concepts/{concept_id}/resources")
    assert response.status_code == 404
    assert response.json()["detail"] == "Learning resources not found for this concept"


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(schema_version=2),
    lambda d: d.update(content_version=" "),
    lambda d: d["lessons"].append(copy.deepcopy(d["lessons"][0])),
    lambda d: d["lessons"][0]["overview"].pop("explanation"),
    lambda d: d["lessons"][0]["overview"].update(explanation=123),
    lambda d: d["lessons"][0].update(common_mistakes=[]),
    lambda d: d["lessons"][0]["worked_example"].update(steps=["only one"]),
    lambda d: d["lessons"][0]["complexity"].update(assumptions=[]),
    lambda d: d["lessons"][0]["resources"][0].update(url="not a URL"),
    lambda d: d["lessons"][0]["resources"][0].update(verified_on=None),
    lambda d: d["lessons"][0].update(unexpected="field"),
])
def test_reject_incomplete_or_malformed_content(tmp_path, mutation):
    data = copy.deepcopy(CATALOG)
    mutation(data)
    path = tmp_path / "content.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError, match="Invalid learning resource catalog"):
        load_catalog(path)


@pytest.mark.parametrize("raw", ['{"schema_version": 1, "schema_version": 1}', '{broken', '[]'])
def test_reject_invalid_json_and_duplicate_fields(tmp_path, raw):
    path = tmp_path / "content.json"
    path.write_text(raw)
    with pytest.raises(ContentError):
        load_catalog(path)


def test_invalid_or_missing_catalog_fails_clearly(client, tmp_path, monkeypatch):
    with TestingSessionLocal() as db:
        db.add(Concept(id=500, name="Arrays"))
        db.commit()
    path = tmp_path / "resources.json"
    monkeypatch.setattr(resource_service, "CONTENT_PATH", path)
    for content in [None, "{invalid"]:
        if content is not None:
            path.write_text(content)
        response = client.get("/concepts/500/resources")
        assert response.status_code == 500
        assert response.json()["detail"] == "Learning resource content is invalid or unavailable"


def test_locked_lessons_readable_without_student_state_changes(client):
    with TestingSessionLocal() as db:
        db.add_all([Student(id=600, username="reader"), Concept(id=601, name="Arrays"), Concept(id=602, name="Binary Search")])
        db.flush()
        db.add(Prerequisite(concept_id=602, prerequisite_id=601))
        db.add(Mastery(student_id=600, concept_id=601, probability=0.3))
        db.commit()
    progress = client.get("/progress/600").json()
    recommendations = client.get("/recommendations/600").json()
    statements = []
    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())
    event.listen(test_engine, "before_cursor_execute", track)
    try:
        assert client.get("/concepts/602/resources").status_code == 200
        assert client.get("/concepts/602/resources").status_code == 200
    finally:
        event.remove(test_engine, "before_cursor_execute", track)
    assert statements == ["SELECT", "SELECT"]
    assert client.get("/progress/600").json() == progress
    assert client.get("/recommendations/600").json() == recommendations
    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all() == []
        assert len(db.scalars(select(Mastery)).all()) == 1
