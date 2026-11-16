
import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Concept, Prerequisite


def build_concept_graph(db: Session) -> nx.DiGraph:
    graph = nx.DiGraph()

    # Fetch concepts from PostgreSQL.
    concepts = db.scalars(select(Concept)).all()

    for concept in concepts:
        graph.add_node(
            concept.id,
            name=concept.name,
            description=concept.description,
        )

    # Fetch prerequisite relationships.
    prerequisites = db.scalars(select(Prerequisite)).all()

    for relation in prerequisites:
        # Direction: prerequisite -> dependent concept
        graph.add_edge(
            relation.prerequisite_id,
            relation.concept_id,
        )

    return graph
