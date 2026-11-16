
import pytest

from app.mastery_rules import get_mastery_status


def test_weak_mastery():
    assert get_mastery_status(0.20) == "weak"


def test_learning_mastery():
    assert get_mastery_status(0.60) == "learning"


def test_mastered():
    assert get_mastery_status(0.90) == "mastered"


def test_threshold_boundaries():
    assert get_mastery_status(0.3999) == "weak"
    assert get_mastery_status(0.40) == "learning"
    assert get_mastery_status(0.7999) == "learning"
    assert get_mastery_status(0.80) == "mastered"


def test_invalid_probabilities():
    with pytest.raises(ValueError):
        get_mastery_status(-0.1)

    with pytest.raises(ValueError):
        get_mastery_status(1.1)
