from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from PIL import Image

from security_ai.domain import BoundingBox, HighRiskDetection, TrackObservation
from security_ai.high_risk import (
    TransformersZeroShotFirearmDetector,
    associate_high_risk_evidence,
    non_max_suppression,
)


def test_zero_shot_adapter_maps_uncertain_predictions() -> None:
    def predictor(
        image: Image.Image, prompts: Sequence[str], threshold: float
    ) -> list[Mapping[str, object]]:
        assert image.size == (64, 64)
        assert "a handgun" in prompts
        assert threshold == 0.2
        return [
            {
                "score": 0.73,
                "label": "a handgun",
                "box": {"xmin": 10, "ymin": 20, "xmax": 30, "ymax": 40},
            }
        ]

    detector = TransformersZeroShotFirearmDetector(
        confidence_threshold=0.2,
        predictor=predictor,
    )

    detections = detector.detect(np.zeros((64, 64, 3), dtype=np.uint8))

    assert detections == (HighRiskDetection(BoundingBox(10, 20, 30, 40), 0.73, "firearm_like"),)


def test_association_selects_containing_person_track() -> None:
    detections = (HighRiskDetection(BoundingBox(40, 40, 50, 50), 0.8),)
    tracks = (
        TrackObservation("left", BoundingBox(0, 0, 30, 100)),
        TrackObservation("right", BoundingBox(35, 0, 70, 100)),
    )

    associated = associate_high_risk_evidence(detections, tracks)

    assert len(associated) == 1
    assert associated[0].track_id == "right"


def test_uncontained_detection_is_not_associated() -> None:
    detections = (HighRiskDetection(BoundingBox(100, 100, 110, 110), 0.8),)
    tracks = (TrackObservation("person", BoundingBox(0, 0, 30, 60)),)

    assert associate_high_risk_evidence(detections, tracks) == ()


def test_nms_collapses_prompt_duplicates_and_keeps_distinct_objects() -> None:
    detections = (
        HighRiskDetection(BoundingBox(10, 10, 30, 30), 0.8),
        HighRiskDetection(BoundingBox(11, 11, 31, 31), 0.7),
        HighRiskDetection(BoundingBox(50, 50, 60, 60), 0.6),
    )

    selected = non_max_suppression(detections)

    assert selected == (detections[0], detections[2])
