"""Threshold evaluation for the firearm-like visual evidence baseline."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from security_ai.domain import BoundingBox, HighRiskDetection
from security_ai.high_risk import TransformersZeroShotFirearmDetector


@dataclass(frozen=True, slots=True)
class ThresholdMetrics:
    threshold: float
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def evaluate_thresholds(
    ground_truth: dict[str, tuple[BoundingBox, ...]],
    predictions: dict[str, tuple[HighRiskDetection, ...]],
    thresholds: tuple[float, ...],
    *,
    iou_threshold: float = 0.5,
) -> list[ThresholdMetrics]:
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold must be in (0, 1]")
    return [
        _evaluate_threshold(ground_truth, predictions, threshold, iou_threshold)
        for threshold in thresholds
    ]


def _evaluate_threshold(
    ground_truth: dict[str, tuple[BoundingBox, ...]],
    predictions: dict[str, tuple[HighRiskDetection, ...]],
    threshold: float,
    iou_threshold: float,
) -> ThresholdMetrics:
    if not 0 <= threshold <= 1:
        raise ValueError("thresholds must be in [0, 1]")
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    image_ids = set(ground_truth) | set(predictions)
    for image_id in image_ids:
        expected = ground_truth.get(image_id, ())
        unmatched = set(range(len(expected)))
        detected = sorted(
            (item for item in predictions.get(image_id, ()) if item.score >= threshold),
            key=lambda item: item.score,
            reverse=True,
        )
        for prediction in detected:
            candidates = [
                (box_index, _iou(prediction.box, expected[box_index])) for box_index in unmatched
            ]
            if candidates:
                best_index, best_iou = max(candidates, key=lambda item: item[1])
            else:
                best_index, best_iou = -1, 0.0
            if best_iou >= iou_threshold:
                true_positives += 1
                unmatched.remove(best_index)
            else:
                false_positives += 1
        false_negatives += len(unmatched)

    precision = _safe_ratio(true_positives, true_positives + false_positives)
    recall = _safe_ratio(true_positives, true_positives + false_negatives)
    f1 = _safe_ratio(2 * precision * recall, precision + recall)
    return ThresholdMetrics(
        threshold=threshold,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _iou(left: BoundingBox, right: BoundingBox) -> float:
    intersection_width = max(0.0, min(left.x2, right.x2) - max(left.x1, right.x1))
    intersection_height = max(0.0, min(left.y2, right.y2) - max(left.y1, right.y1))
    intersection = intersection_width * intersection_height
    left_area = max(0.0, left.x2 - left.x1) * max(0.0, left.y2 - left.y1)
    right_area = max(0.0, right.x2 - right.x1) * max(0.0, right.y2 - right.y1)
    return _safe_ratio(intersection, left_area + right_area - intersection)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the firearm-like baseline")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="google/owlv2-base-patch16-ensemble")
    parser.add_argument("--thresholds", default="0.05,0.1,0.15,0.2,0.3,0.4,0.5")
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument(
        "--max-images",
        type=int,
        help="Evaluate only the first N manifest items (useful for smoke tests)",
    )
    arguments = parser.parse_args()

    raw: dict[str, Any] = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    thresholds = tuple(float(value) for value in arguments.thresholds.split(","))
    if not thresholds:
        raise ValueError("at least one threshold is required")
    if arguments.max_images is not None and arguments.max_images <= 0:
        raise ValueError("max-images must be positive")
    detector = TransformersZeroShotFirearmDetector(
        model_name=arguments.model,
        confidence_threshold=min(thresholds),
    )
    ground_truth: dict[str, tuple[BoundingBox, ...]] = {}
    predictions: dict[str, tuple[HighRiskDetection, ...]] = {}
    latencies_ms: list[float] = []
    prediction_records: list[dict[str, Any]] = []
    items = raw["items"]
    if arguments.max_images is not None:
        items = items[: arguments.max_images]
    for index, item in enumerate(items, start=1):
        image_id = str(item["imageId"])
        image_path = arguments.manifest.parent / str(item["imagePath"])
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"could not read evaluation image: {image_path}")
        started = perf_counter()
        predictions[image_id] = detector.detect(cast(NDArray[np.uint8], frame))
        latency_ms = (perf_counter() - started) * 1_000
        latencies_ms.append(latency_ms)
        ground_truth[image_id] = _deduplicate_boxes(
            tuple(
                _annotation_box(annotation, width=frame.shape[1], height=frame.shape[0])
                for annotation in item.get("annotations", [])
                if annotation["label"] in {"Handgun", "Rifle", "Shotgun"}
            )
        )
        prediction_records.append(
            {
                "imageId": image_id,
                "latencyMs": latency_ms,
                "width": frame.shape[1],
                "height": frame.shape[0],
                "groundTruth": item.get("annotations", []),
                "predictions": [
                    {
                        "score": detection.score,
                        "label": detection.label,
                        "boxPixels": _box_values(detection.box),
                    }
                    for detection in predictions[image_id]
                ],
            }
        )
        print(f"evaluated {index}/{len(items)}: {image_id} ({latency_ms:.0f} ms)")

    metrics = evaluate_thresholds(
        ground_truth,
        predictions,
        thresholds,
        iou_threshold=arguments.iou,
    )
    latency_values: NDArray[np.float64] = np.asarray(latencies_ms, dtype=np.float64)
    report = {
        "schemaVersion": "1.0",
        "model": detector.version,
        "manifest": str(arguments.manifest),
        "images": len(ground_truth),
        "positiveImages": sum(bool(boxes) for boxes in ground_truth.values()),
        "negativeImages": sum(not boxes for boxes in ground_truth.values()),
        "meanLatencyMs": float(latency_values.mean()) if latency_values.size else 0.0,
        "p95LatencyMs": (float(np.percentile(latency_values, 95)) if latency_values.size else 0.0),
        "thresholds": [asdict(row) for row in metrics],
        "predictionRecords": prediction_records,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _annotation_box(annotation: dict[str, Any], *, width: int, height: int) -> BoundingBox:
    x1, y1, x2, y2 = (float(value) for value in annotation["boxNormalized"])
    return BoundingBox(x1 * width, y1 * height, x2 * width, y2 * height)


def _box_values(box: BoundingBox) -> list[float]:
    return [box.x1, box.y1, box.x2, box.y2]


def _deduplicate_boxes(
    boxes: tuple[BoundingBox, ...], *, iou_threshold: float = 0.9
) -> tuple[BoundingBox, ...]:
    selected: list[BoundingBox] = []
    for box in boxes:
        if all(_iou(box, kept) < iou_threshold for kept in selected):
            selected.append(box)
    return tuple(selected)


if __name__ == "__main__":
    main()
