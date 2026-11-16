
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bkt import INITIAL_MASTERY
from app.concept_graph import build_concept_graph
from app.mastery_rules import get_mastery_status
from app.models import Mastery


def get_recommendations(db: Session, student_id: int) -> list[dict]:
    graph = build_concept_graph(db)

    # Load the student's existing mastery records.
    mastery_records = db.scalars(
        select(Mastery).where(Mastery.student_id == student_id)
    ).all()

    mastery_map = {
        record.concept_id: record.probability
        for record in mastery_records
    }

    recommendations = []

    for concept_id in graph.nodes:
        concept_name = graph.nodes[concept_id]["name"]

        # Use initial BKT mastery if the concept hasn't been attempted.
        probability = mastery_map.get(concept_id, INITIAL_MASTERY)
        status = get_mastery_status(probability)

        # Prerequisites are incoming edges in our graph.
        prerequisites = list(graph.predecessors(concept_id))

        unmet_prerequisites = [
            prerequisite_id
            for prerequisite_id in prerequisites
            if get_mastery_status(
                mastery_map.get(prerequisite_id, INITIAL_MASTERY)
            ) != "mastered"
        ]

        # Don't recommend advanced concepts before their prerequisites.
        if unmet_prerequisites:
            continue

        if status == "weak":
            action = "revise" if concept_id in mastery_map else "learn"
            reason = (
                f"Your mastery of {concept_name} is low. Revise this concept."
                if action == "revise"
                else f"{concept_name} is ready to learn."
            )

        elif status == "learning":
            action = "practice"
            reason = (
                f"You are making progress in {concept_name}. "
                "Continue practicing to strengthen your understanding."
            )

        else:
            continue

        recommendations.append(
            {
                "concept_id": concept_id,
                "concept_name": concept_name,
                "mastery_probability": round(probability, 4),
                "status": status,
                "action": action,
                "reason": reason,
            }
        )

    # Prioritize revision, then practice, then new concepts.
    priority = {"revise": 0, "practice": 1, "learn": 2}

    recommendations.sort(
        key=lambda item: (
            priority[item["action"]],
            item["mastery_probability"],
            item["concept_id"],
        )
    )

    return recommendations
