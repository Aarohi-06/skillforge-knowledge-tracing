
WEAK_THRESHOLD = 0.40
MASTERED_THRESHOLD = 0.80


def get_mastery_status(probability: float) -> str:
    if not 0 <= probability <= 1:
        raise ValueError("Mastery probability must be between 0 and 1")

    if probability < WEAK_THRESHOLD:
        return "weak"

    if probability < MASTERED_THRESHOLD:
        return "learning"

    return "mastered"
