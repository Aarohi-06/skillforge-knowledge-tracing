
from app.database import SessionLocal
from app.recommendation_engine import get_recommendations


def main():
    student_id = 1  # Our existing demo student

    with SessionLocal() as db:
        recommendations = get_recommendations(db, student_id)

    print("\n--- SkillForge Recommendations ---")
    print(f"Student ID: {student_id}")
    print(f"Total recommendations: {len(recommendations)}")

    for index, recommendation in enumerate(recommendations, start=1):
        print(f"\nRecommendation {index}")
        print("Concept:", recommendation["concept_name"])
        print("Mastery:", recommendation["mastery_probability"])
        print("Status:", recommendation["status"])
        print("Action:", recommendation["action"])
        print("Reason:", recommendation["reason"])


if __name__ == "__main__":
    main()
