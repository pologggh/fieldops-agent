"""Evaluation metrics: set-based precision/recall/F1, scalar accuracy, and hallucination scoring."""

from typing import Any


def calculate_set_metrics(
    expected: list[str] | set[str] | None,
    predicted: list[str] | set[str] | None,
) -> dict[str, float]:
    """Calculate set-based Precision, Recall, and F1 score for unordered collections.

    Handles empty collection edge cases deterministically:
    - Both empty -> Precision=1.0, Recall=1.0, F1=1.0 (perfect match on absence)
    - Expected empty, Predicted non-empty -> Precision=0.0, Recall=1.0, F1=0.0
    - Expected non-empty, Predicted empty -> Precision=1.0, Recall=0.0, F1=0.0
    """
    exp_set = {str(item).strip().casefold() for item in (expected or []) if item and str(item).strip()}
    pred_set = {str(item).strip().casefold() for item in (predicted or []) if item and str(item).strip()}

    if not exp_set and not pred_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not exp_set and pred_set:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}
    if exp_set and not pred_set:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0}

    true_positives = len(exp_set & pred_set)
    precision = true_positives / len(pred_set) if pred_set else 0.0
    recall = true_positives / len(exp_set) if exp_set else 0.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def calculate_scalar_accuracy(
    expected: Any,
    predicted: Any,
    case_insensitive: bool = True,
) -> bool:
    """Compare two scalar values (e.g. service_type, urgency, location) for exact or normalized match."""
    if expected is None and predicted is None:
        return True
    if expected is None or predicted is None:
        return False

    if case_insensitive and isinstance(expected, str) and isinstance(predicted, str):
        return expected.strip().casefold() == predicted.strip().casefold()

    return expected == predicted


def detect_unsupported_hallucination(expected: Any, predicted: Any) -> bool:
    """Detect if the model invented an unsupported field when ground truth is null/empty.

    Returns True if ground truth is absent (None/empty) but prediction is present.
    """
    is_expected_empty = expected is None or (isinstance(expected, (str, list, dict, set)) and len(expected) == 0)
    is_predicted_present = predicted is not None and (
        not isinstance(predicted, (str, list, dict, set)) or len(predicted) > 0
    )

    return is_expected_empty and is_predicted_present
