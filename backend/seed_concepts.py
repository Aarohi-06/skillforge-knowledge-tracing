
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Concept, Prerequisite


concept_data = [
    ("Arrays", "Introduction to arrays and indexing."),
    ("Time Complexity", "Understanding algorithm efficiency."),
    ("Linear Search", "Sequential searching techniques."),
    ("Binary Search", "Efficient searching in sorted data."),
    ("Bubble Sort", "Comparison-based iterative sorting."),
    ("Merge Sort", "Divide-and-conquer sorting algorithm."),
    ("Recursion", "Solving problems using recursive calls."),
    ("Sorting Fundamentals", "Basic sorting concepts and stability."),
]

prerequisite_data = [
    ("Linear Search", "Arrays"),
    ("Binary Search", "Arrays"),
    ("Binary Search", "Linear Search"),
    ("Bubble Sort", "Arrays"),
    ("Bubble Sort", "Time Complexity"),
    ("Merge Sort", "Arrays"),
    ("Merge Sort", "Recursion"),
    ("Sorting Fundamentals", "Arrays"),
]


def seed():
    with SessionLocal.begin() as db:
        for name, description in concept_data:
            existing = db.scalar(
                select(Concept).where(Concept.name == name)
            )

            if existing is None:
                db.add(
                    Concept(name=name, description=description)
                )

        db.flush()

        concepts = {
            concept.name: concept
            for concept in db.scalars(select(Concept)).all()
        }

        for concept_name, prerequisite_name in prerequisite_data:
            concept_id = concepts[concept_name].id
            prerequisite_id = concepts[prerequisite_name].id

            existing = db.scalar(
                select(Prerequisite).where(
                    Prerequisite.concept_id == concept_id,
                    Prerequisite.prerequisite_id == prerequisite_id,
                )
            )

            if existing is None:
                db.add(
                    Prerequisite(
                        concept_id=concept_id,
                        prerequisite_id=prerequisite_id,
                    )
                )

    print("DSA concepts and prerequisites seeded successfully!")


if __name__ == "__main__":
    seed()
