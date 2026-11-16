
import networkx as nx

from app.concept_graph import build_concept_graph
from app.models import Concept, Prerequisite
from conftest import TestingSessionLocal


def test_concept_graph(client):
    with TestingSessionLocal() as db:
        root = Concept(name="Root")
        dependent = Concept(name="Dependent")
        isolated = Concept(name="Isolated")
        db.add_all([root, dependent, isolated])
        db.flush()
        db.add(Prerequisite(prerequisite_id=root.id, concept_id=dependent.id))
        db.commit()
        graph = build_concept_graph(db)
        assert set(graph.nodes) == {root.id, dependent.id, isolated.id}
        assert set(graph.edges) == {(root.id, dependent.id)}

    print("\n--- SkillForge Concept Graph ---")

    print("Total concepts:", graph.number_of_nodes())
    print("Total prerequisites:", graph.number_of_edges())

    print("\nPrerequisite Relationships:")

    for source, target in graph.edges():
        source_name = graph.nodes[source]["name"]
        target_name = graph.nodes[target]["name"]

        print(f"{source_name} -> {target_name}")

    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 1
    assert nx.is_directed_acyclic_graph(graph)

    print("\nGraph verification successful!")
