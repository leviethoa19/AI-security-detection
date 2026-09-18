"""Replaceable firearm-like visual evidence detection and track association."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from typing import Any, Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from security_ai.domain import (
    BoundingBox,
    HighRiskDetection,
    HighRiskEvidenceObservation,
    TrackObservation,
)

DEFAULT_FIREARM_PROMPTS = (
    "a handgun",
    "a pistol",
    "a revolver",
    "a rifle",
    "a shotgun",
)


class HighRiskObjectDetector(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def device_name(self) -> str: ...

    def detect(self, frame: NDArray[np.uint8]) -> tuple[HighRiskDetection, ...]: ...


Prediction = Mapping[str, object]
Predictor = Callable[[Image.Image, Sequence[str], float], Sequence[Prediction]]


class TransformersZeroShotFirearmDetector:
    """Open-vocabulary baseline; outputs uncertain firearm-like evidence only."""

    def __init__(
        self,
        model_name: str = "google/owlv2-base-patch16-ensemble",
        *,
        confidence_threshold: float = 0.4,
        prompts: Sequence[str] = DEFAULT_FIREARM_PROMPTS,
        device: str = "cpu",
        nms_iou_threshold: float = 0.5,
        predictor: Predictor | None = None,
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be in [0, 1]")
        if not prompts:
            raise ValueError("at least one firearm prompt is required")
        if not 0 < nms_iou_threshold <= 1:
            raise ValueError("nms_iou_threshold must be in (0, 1]")
        self._model_name = model_name
        self._confidence_threshold = confidence_threshold
        self._prompts = tuple(prompts)
        self._device = device
        self._nms_iou_threshold = nms_iou_threshold
        self._predictor = predictor or self._load_predictor(model_name, device)

    @property
    def version(self) -> str:
        return f"transformers-zero-shot:{self._model_name}"

    @property
    def device_name(self) -> str:
        return self._device

    def detect(self, frame: NDArray[np.uint8]) -> tuple[HighRiskDetection, ...]:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("expected a BGR frame with shape (height, width, 3)")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        predictions = self._predictor(image, self._prompts, self._confidence_threshold)
        detections: list[HighRiskDetection] = []
        for prediction in predictions:
            score = float(cast(float, prediction["score"]))
            box = cast(Mapping[str, object], prediction["box"])
            detections.append(
                HighRiskDetection(
                    box=BoundingBox(
                        x1=float(cast(float, box["xmin"])),
                        y1=float(cast(float, box["ymin"])),
                        x2=float(cast(float, box["xmax"])),
                        y2=float(cast(float, box["ymax"])),
                    ),
                    score=score,
                    label="firearm_like",
                )
            )
        return non_max_suppression(tuple(detections), self._nms_iou_threshold)

    @staticmethod
    def _load_predictor(model_name: str, device: str) -> Predictor:
        try:
            transformers = import_module("transformers")
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "install the high-risk extra before loading the zero-shot detector"
            ) from error
        pipeline_device = -1 if device == "cpu" else 0
        detector = transformers.pipeline(
            task="zero-shot-object-detection",
            model=model_name,
            device=pipeline_device,
        )

        def predict(
            image: Image.Image, prompts: Sequence[str], threshold: float
        ) -> Sequence[Prediction]:
            raw: Any = detector(
                image,
                candidate_labels=list(prompts),
                threshold=threshold,
            )
            return cast(Sequence[Prediction], raw)

        return predict


def associate_high_risk_evidence(
    detections: tuple[HighRiskDetection, ...],
    tracks: tuple[TrackObservation, ...],
    *,
    person_box_margin: float = 0.15,
) -> tuple[HighRiskEvidenceObservation, ...]:
    """Associate each object center with the nearest containing expanded person box."""

    if person_box_margin < 0:
        raise ValueError("person_box_margin cannot be negative")
    associated: list[HighRiskEvidenceObservation] = []
    for detection in detections:
        center_x = (detection.box.x1 + detection.box.x2) / 2
        center_y = (detection.box.y1 + detection.box.y2) / 2
        candidates: list[tuple[float, TrackObservation]] = []
        for track in tracks:
            expanded = _expand(track.box, person_box_margin)
            if expanded.x1 <= center_x <= expanded.x2 and expanded.y1 <= center_y <= expanded.y2:
                track_center_x = (track.box.x1 + track.box.x2) / 2
                track_center_y = (track.box.y1 + track.box.y2) / 2
                distance = (center_x - track_center_x) ** 2 + (center_y - track_center_y) ** 2
                candidates.append((distance, track))
        if not candidates:
            continue
        _, selected = min(candidates, key=lambda candidate: candidate[0])
        associated.append(
            HighRiskEvidenceObservation(
                track_id=selected.track_id,
                box=detection.box,
                score=detection.score,
                label=detection.label,
            )
        )
    return tuple(associated)


def non_max_suppression(
    detections: tuple[HighRiskDetection, ...],
    iou_threshold: float = 0.5,
) -> tuple[HighRiskDetection, ...]:
    """Collapse prompt-level duplicates for the product's unified evidence class."""

    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold must be in (0, 1]")
    selected: list[HighRiskDetection] = []
    for detection in sorted(detections, key=lambda item: item.score, reverse=True):
        if all(_box_iou(detection.box, kept.box) < iou_threshold for kept in selected):
            selected.append(detection)
    return tuple(selected)


def _box_iou(left: BoundingBox, right: BoundingBox) -> float:
    width = max(0.0, min(left.x2, right.x2) - max(left.x1, right.x1))
    height = max(0.0, min(left.y2, right.y2) - max(left.y1, right.y1))
    intersection = width * height
    left_area = max(0.0, left.x2 - left.x1) * max(0.0, left.y2 - left.y1)
    right_area = max(0.0, right.x2 - right.x1) * max(0.0, right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _expand(box: BoundingBox, margin: float) -> BoundingBox:
    width = box.x2 - box.x1
    height = box.y2 - box.y1
    return BoundingBox(
        x1=box.x1 - width * margin,
        y1=box.y1 - height * margin,
        x2=box.x2 + width * margin,
        y2=box.y2 + height * margin,
    )
