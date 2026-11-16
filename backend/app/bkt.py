
# Default BKT parameters for the SkillForge MVP

INITIAL_MASTERY = 0.20
LEARN_PROB = 0.10
GUESS_PROB = 0.20
SLIP_PROB = 0.10


def update_mastery(
    prior_mastery: float,
    is_correct: bool,
    learn_prob: float = LEARN_PROB,
    guess_prob: float = GUESS_PROB,
    slip_prob: float = SLIP_PROB,
) -> float:
    """
    Update a student's concept mastery using
    Bayesian Knowledge Tracing.

    Returns the probability of mastery before
    the next question.
    """

    if not 0 <= prior_mastery <= 1:
        raise ValueError("Prior mastery must be between 0 and 1")

    for name, value in [
        ("learn_prob", learn_prob),
        ("guess_prob", guess_prob),
        ("slip_prob", slip_prob),
    ]:
        if not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")

    # Step 1: Bayesian update based on the answer
    if is_correct:
        numerator = prior_mastery * (1 - slip_prob)
        denominator = numerator + (1 - prior_mastery) * guess_prob
    else:
        numerator = prior_mastery * slip_prob
        denominator = numerator + (1 - prior_mastery) * (1 - guess_prob)

    if denominator == 0:
        raise ValueError("Observation has zero probability")

    posterior = numerator / denominator

    # Step 2: Account for learning before the next attempt
    updated_mastery = posterior + (1 - posterior) * learn_prob

    return updated_mastery
