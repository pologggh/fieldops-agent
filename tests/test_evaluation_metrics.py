"""Unit tests for evaluation metrics (Phase 11)."""

from evaluation.metrics import (
    calculate_scalar_accuracy,
    calculate_set_metrics,
    detect_unsupported_hallucination,
)


def test_set_metrics_perfect_match() -> None:
    """Exact match of skills yields 1.0 for Precision, Recall, and F1."""
    res = calculate_set_metrics(["HVAC", "Electrical"], ["electrical", "HVAC"])
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["f1"] == 1.0


def test_set_metrics_partial_recall() -> None:
    """Missing one expected skill halves recall while precision remains 1.0."""
    res = calculate_set_metrics(["HVAC", "Electrical"], ["HVAC"])
    assert res["precision"] == 1.0
    assert res["recall"] == 0.5
    assert round(res["f1"], 2) == 0.67


def test_set_metrics_over_prediction() -> None:
    """Predicting an extra unstated skill halves precision while recall is 1.0."""
    res = calculate_set_metrics(["HVAC"], ["HVAC", "Plumbing"])
    assert res["precision"] == 0.5
    assert res["recall"] == 1.0
    assert round(res["f1"], 2) == 0.67


def test_set_metrics_both_empty() -> None:
    """When both expected and predicted are empty, scores are 1.0 (correctly identified absence)."""
    res = calculate_set_metrics([], [])
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["f1"] == 1.0


def test_set_metrics_hallucinated_when_expected_empty() -> None:
    """When expected is empty but model predicted items, precision and F1 drop to 0.0."""
    res = calculate_set_metrics([], ["Plumbing"])
    assert res["precision"] == 0.0
    assert res["f1"] == 0.0


def test_scalar_accuracy_cases() -> None:
    """Test scalar accuracy with case-insensitivity, whitespace, and nulls."""
    assert calculate_scalar_accuracy("HVAC", "hvac") is True
    assert calculate_scalar_accuracy(" Shinjuku ", "shinjuku") is True
    assert calculate_scalar_accuracy(None, None) is True
    assert calculate_scalar_accuracy("Shinjuku", None) is False
    assert calculate_scalar_accuracy(None, "Shinjuku") is False
    assert calculate_scalar_accuracy("HVAC", "Plumbing") is False


def test_detect_unsupported_hallucination() -> None:
    """Detect unstated detail hallucinations."""
    # Expected null, predicted value -> Hallucination!
    assert detect_unsupported_hallucination(None, "Shinjuku") is True
    assert detect_unsupported_hallucination("", "tomorrow afternoon") is True
    assert detect_unsupported_hallucination([], ["HVAC"]) is True

    # Expected value, predicted value -> Not an unsupported hallucination
    assert detect_unsupported_hallucination("Shinjuku", "Shinjuku") is False
    assert detect_unsupported_hallucination(None, None) is False
    assert detect_unsupported_hallucination(None, "") is False
    assert detect_unsupported_hallucination(["HVAC"], ["HVAC"]) is False
