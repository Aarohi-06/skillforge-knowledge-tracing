import pytest

from app.bkt import INITIAL_MASTERY, update_mastery


def test_correct_answer_increases_mastery():
    updated = update_mastery(INITIAL_MASTERY, True)

    assert updated > INITIAL_MASTERY


def test_incorrect_answer_decreases_mastery():
    updated = update_mastery(INITIAL_MASTERY, False)

    assert updated < INITIAL_MASTERY


def test_mastery_stays_between_zero_and_one():
    mastery = INITIAL_MASTERY

    for answer in [True, True, False, True, False]:
        mastery = update_mastery(mastery, answer)

        assert 0 <= mastery <= 1


def test_invalid_prior_mastery():
    with pytest.raises(ValueError):
        update_mastery(1.5, True)