from sqlalchemy import select

from app.models import Concept, Prerequisite, Mastery, Attempt
from conftest import TestingSessionLocal


def test_empty_concept_graph(client):
    response = client.get("/concept-graph")
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}


def test_concept_graph_includes_isolated_nodes_and_directed_edges(client):
    with TestingSessionLocal() as db:
        concepts = [Concept(name=name) for name in ["Arrays", "Search", "Trees", "Isolated"]]
        db.add_all(concepts)
        db.flush()
        ids = [concept.id for concept in concepts]
        db.add_all([
            Prerequisite(prerequisite_id=ids[0], concept_id=ids[1]),
            Prerequisite(prerequisite_id=ids[0], concept_id=ids[2]),
            Prerequisite(prerequisite_id=ids[1], concept_id=ids[2]),
        ])
        db.commit()

    response = client.get("/concept-graph")
    assert response.status_code == 200
    assert response.json() == {
        "nodes": [dict(id=concept_id, name=name) for concept_id, name in zip(
            ids, ["Arrays", "Search", "Trees", "Isolated"]
        )],
        "edges": [
            {"source": ids[0], "target": ids[1]},
            {"source": ids[0], "target": ids[2]},
            {"source": ids[1], "target": ids[2]},
        ],
    }
    assert client.get("/concept-graph").json() == response.json()
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Concept)).all()) == 4
        assert len(db.scalars(select(Prerequisite)).all()) == 3
        assert db.scalars(select(Mastery)).all() == []
        assert db.scalars(select(Attempt)).all() == []
