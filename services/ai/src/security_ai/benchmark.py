"""Repeatable detector latency benchmark over the same video frames."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from numpy.typing import NDArray

from security_ai.detection import SUPPORTED_MODELS, TorchvisionPersonDetector


@dataclass(frozen=True, slots=True)
class BenchmarkRow:
    model: str
    device: str
    frames: int
    warmup_frames: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    effective_fps: float
    person_boxes: int


def benchmark_video(
    video_path: Path,
    *,
    models: tuple[str, ...] = SUPPORTED_MODELS,
    frames: int = 30,
    warmup_frames: int = 3,
    confidence_threshold: float = 0.5,
) -> list[BenchmarkRow]:
    sampled_frames = _load_frames(video_path, frames + warmup_frames)
    if len(sampled_frames) <= warmup_frames:
        raise ValueError("video does not contain enough frames for the requested warmup")

    results: list[BenchmarkRow] = []
    for model_name in models:
        detector = TorchvisionPersonDetector(
            model_name,
            confidence_threshold=confidence_threshold,
        )
        for frame in sampled_frames[:warmup_frames]:
            detector.detect(frame)

        durations: list[float] = []
        person_boxes = 0
        for frame in sampled_frames[warmup_frames:]:
            started = perf_counter()
            person_boxes += len(detector.detect(frame))
            durations.append((perf_counter() - started) * 1_000)

        values: NDArray[np.float64] = np.asarray(durations, dtype=np.float64)
        mean_ms = float(values.mean())
        results.append(
            BenchmarkRow(
                model=detector.version,
                device=detector.device_name,
                frames=len(durations),
                warmup_frames=warmup_frames,
                mean_ms=mean_ms,
                median_ms=float(np.median(values)),
                p95_ms=float(np.percentile(values, 95)),
                effective_fps=1_000 / mean_ms,
                person_boxes=person_boxes,
            )
        )
    return results


def _load_frames(path: Path, limit: int) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"could not open video: {path}")
    frames: list[np.ndarray] = []
    try:
        while len(frames) < limit:
            readable, frame = capture.read()
            if not readable:
                break
            frames.append(frame)
    finally:
        capture.release()
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark person detector candidates")
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--warmup-frames", type=int, default=3)
    arguments = parser.parse_args()

    rows = benchmark_video(
        arguments.video,
        frames=arguments.frames,
        warmup_frames=arguments.warmup_frames,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BenchmarkRow.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in writer.fieldnames})


if __name__ == "__main__":
    main()
