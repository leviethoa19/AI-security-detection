from __future__ import annotations

import pytest

from security_ai.domain import BoundingBox, HighRiskDetection
from security_ai.high_risk_eval import _deduplicate_boxes, evaluate_thresholds


def test_threshold_metrics_match_predictions_by_iou() -> None:
    ground_truth = {
        "positive": (BoundingBox(10, 10, 30, 30),),
        "negative": (),
    }
    predictions = {
        "positive": (
            HighRiskDetection(BoundingBox(10, 10, 30, 30), 0.8),
            HighRiskDetection(BoundingBox(40, 40, 50, 50), 0.2),
        ),
        "negative": (HighRiskDetection(BoundingBox(0, 0, 10, 10), 0.4),),
    }

    low, high = evaluate_thresholds(ground_truth, predictions, (0.1, 0.5))

    assert low.true_positives == 1
    assert low.false_positives == 2
    assert low.false_negatives == 0
    assert low.precision == pytest.approx(1 / 3)
    assert high.true_positives == 1
    assert high.false_positives == 0
    assert high.f1 == 1.0


def test_unmatched_ground_truth_is_false_negative() -> None:
    metrics = evaluate_thresholds(
        {"positive": (BoundingBox(0, 0, 10, 10),)},
        {"positive": ()},
        (0.5,),
    )[0]

    assert metrics.false_negatives == 1
    assert metrics.recall == 0.0


def test_unified_ground_truth_collapses_overlapping_source_labels() -> None:
    boxes = (
        BoundingBox(10, 10, 30, 30),
        BoundingBox(10.2, 10.2, 30.2, 30.2),
        BoundingBox(50, 50, 60, 60),
    )

    assert _deduplicate_boxes(boxes) == (boxes[0], boxes[2])
