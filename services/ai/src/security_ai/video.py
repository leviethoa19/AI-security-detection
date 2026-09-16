"""Prerecorded-video vertical slice: detect, track, annotate, and reason."""

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

from security_ai.detection import SUPPORTED_MODELS, PersonDetector, TorchvisionPersonDetector
from security_ai.domain import (
    FrameObservation,
    Point,
    ReplayConfiguration,
    ReplayScenario,
    TrackObservation,
    Zone,
)
from security_ai.replay import ReplayEngine
from security_ai.tracking import ByteTrackPersonTracker, PersonTracker


@dataclass(frozen=True, slots=True)
class VideoRunMetrics:
    model: str
    device: str
    tracker: str
    input_frames: int
    processed_frames: int
    source_fps: float
    mean_detection_ms: float
    p95_detection_ms: float
    effective_fps: float
    detected_person_boxes: int
    emitted_track_boxes: int
    emitted_events: int


@dataclass(frozen=True, slots=True)
class VideoRunResult:
    events: list[dict[str, Any]]
    metrics: VideoRunMetrics


def process_video(
    *,
    input_path: Path,
    output_video_path: Path,
    detector: PersonDetector,
    tracker: PersonTracker,
    zone: Zone,
    camera_id: str = "camera-demo-01",
    scenario_id: str = "video-replay",
    started_at: str = "2026-01-01T00:00:00Z",
    armed: bool = True,
    frame_stride: int = 1,
    max_frames: int | None = None,
) -> VideoRunResult:
    if frame_stride < 1:
        raise ValueError("frame_stride must be at least 1")
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise ValueError(f"could not open video: {input_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        source_fps / frame_stride,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise ValueError(f"could not create output video: {output_video_path}")

    observations: list[FrameObservation] = []
    detection_times_ms: list[float] = []
    input_frames = 0
    detection_count = 0
    track_count = 0
    run_started = perf_counter()
    try:
        while True:
            readable, frame = capture.read()
            if not readable:
                break
            current_index = input_frames
            input_frames += 1
            if current_index % frame_stride != 0:
                continue
            if max_frames is not None and len(observations) >= max_frames:
                break

            typed_frame = cast(NDArray[np.uint8], frame)
            source_time_ms = round(current_index / source_fps * 1_000)
            detection_started = perf_counter()
            detections = detector.detect(typed_frame)
            detection_times_ms.append((perf_counter() - detection_started) * 1_000)
            tracks = tracker.update(
                detections,
                frame=typed_frame,
                timestamp_seconds=source_time_ms / 1_000,
            )
            detection_count += len(detections)
            track_count += len(tracks)
            observations.append(FrameObservation(source_time_ms=source_time_ms, tracks=tracks))
            writer.write(_annotate(typed_frame, tracks, zone))
    finally:
        writer.release()
        capture.release()

    elapsed = perf_counter() - run_started
    scenario = ReplayScenario(
        scenario_id=scenario_id,
        camera_id=camera_id,
        started_at=started_at,
        armed=armed,
        zone=zone,
        configuration=ReplayConfiguration(
            detector_version=detector.version,
            tracker_version=tracker.version,
            configuration_version="video-default-v1",
        ),
        frames=tuple(observations),
    )
    events = ReplayEngine(scenario).run()
    durations = np.asarray(detection_times_ms, dtype=np.float64)
    metrics = VideoRunMetrics(
        model=detector.version,
        device=detector.device_name,
        tracker=tracker.version,
        input_frames=input_frames,
        processed_frames=len(observations),
        source_fps=source_fps,
        mean_detection_ms=float(durations.mean()) if durations.size else 0.0,
        p95_detection_ms=float(np.percentile(durations, 95)) if durations.size else 0.0,
        effective_fps=len(observations) / elapsed if elapsed else 0.0,
        detected_person_boxes=detection_count,
        emitted_track_boxes=track_count,
        emitted_events=len(events),
    )
    return VideoRunResult(events=events, metrics=metrics)


def _annotate(
    frame: NDArray[np.uint8], tracks: tuple[TrackObservation, ...], zone: Zone
) -> NDArray[np.uint8]:
    annotated = frame.copy()
    polygon = np.asarray([[round(point.x), round(point.y)] for point in zone.polygon], np.int32)
    cv2.polylines(annotated, [polygon], isClosed=True, color=(0, 200, 255), thickness=2)
    for track in tracks:
        box = track.box
        start = (round(box.x1), round(box.y1))
        end = (round(box.x2), round(box.y2))
        cv2.rectangle(annotated, start, end, (50, 220, 50), 2)
        cv2.putText(
            annotated,
            f"person #{track.track_id}",
            (start[0], max(18, start[1] - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (50, 220, 50),
            2,
            cv2.LINE_AA,
        )
    return annotated


def main() -> None:
    parser = argparse.ArgumentParser(description="Run person detection and tracking on a video")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-video", type=Path, required=True)
    parser.add_argument("--output-events", type=Path, required=True)
    parser.add_argument("--output-metrics", type=Path, required=True)
    parser.add_argument("--model", choices=SUPPORTED_MODELS, default="ssdlite320")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument(
        "--zone",
        default="0.5,0.5;0.95,0.5;0.95,0.95;0.5,0.95",
        help="normalized polygon x,y pairs separated by semicolons",
    )
    arguments = parser.parse_args()

    width, height, fps = _video_properties(arguments.input)
    zone = _parse_normalized_zone(arguments.zone, width, height)
    detector = TorchvisionPersonDetector(
        arguments.model,
        confidence_threshold=arguments.confidence,
    )
    tracker = ByteTrackPersonTracker(frame_rate=fps / arguments.frame_stride)
    result = process_video(
        input_path=arguments.input,
        output_video_path=arguments.output_video,
        detector=detector,
        tracker=tracker,
        zone=zone,
        frame_stride=arguments.frame_stride,
        max_frames=arguments.max_frames,
    )
    arguments.output_events.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_events.write_text(json.dumps(result.events, indent=2) + "\n", encoding="utf-8")
    arguments.output_metrics.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_metrics.write_text(
        json.dumps(asdict(result.metrics), indent=2) + "\n", encoding="utf-8"
    )


def _video_properties(path: Path) -> tuple[int, int, float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"could not open video: {path}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    capture.release()
    return width, height, fps


def _parse_normalized_zone(value: str, width: int, height: int) -> Zone:
    points: list[Point] = []
    for pair in value.split(";"):
        x_text, y_text = pair.split(",", maxsplit=1)
        x, y = float(x_text), float(y_text)
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("normalized zone coordinates must be in [0, 1]")
        points.append(Point(x=x * width, y=y * height))
    return Zone(zone_id="protected-zone", polygon=tuple(points))


if __name__ == "__main__":
    main()
