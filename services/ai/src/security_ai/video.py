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
    HighRiskDetection,
    Point,
    ReplayConfiguration,
    ReplayScenario,
    TrackObservation,
    Zone,
)
from security_ai.evidence import EvidenceArtifact, RollingEvidenceRecorder, write_evidence_capture
from security_ai.high_risk import (
    HighRiskObjectDetector,
    TransformersZeroShotFirearmDetector,
    associate_high_risk_evidence,
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
    mean_high_risk_detection_ms: float
    effective_fps: float
    detected_person_boxes: int
    emitted_track_boxes: int
    emitted_events: int
    high_risk_detection_boxes: int


@dataclass(frozen=True, slots=True)
class VideoRunResult:
    events: list[dict[str, Any]]
    incidents: list[dict[str, Any]]
    evidence: list[EvidenceArtifact]
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
    evidence_dir: Path | None = None,
    evidence_pre_ms: int = 2_000,
    evidence_post_ms: int = 2_000,
    high_risk_detector: HighRiskObjectDetector | None = None,
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

    configuration = ReplayConfiguration(
        evidence_pre_ms=evidence_pre_ms,
        evidence_post_ms=evidence_post_ms,
        detector_version=detector.version,
        tracker_version=tracker.version,
        high_risk_detector_version=(
            high_risk_detector.version if high_risk_detector is not None else "disabled"
        ),
        configuration_version="video-default-v2",
    )
    scenario = ReplayScenario(
        scenario_id=scenario_id,
        camera_id=camera_id,
        started_at=started_at,
        armed=armed,
        zone=zone,
        configuration=configuration,
        frames=(),
    )
    engine = ReplayEngine(scenario)
    evidence_recorder = (
        RollingEvidenceRecorder(pre_event_ms=evidence_pre_ms, post_event_ms=evidence_post_ms)
        if evidence_dir is not None
        else None
    )
    events: list[dict[str, Any]] = []
    detection_times_ms: list[float] = []
    high_risk_detection_times_ms: list[float] = []
    input_frames = 0
    detection_count = 0
    track_count = 0
    high_risk_detection_count = 0
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
            if max_frames is not None and len(detection_times_ms) >= max_frames:
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
            high_risk_detections: tuple[HighRiskDetection, ...] = ()
            if high_risk_detector is not None:
                high_risk_started = perf_counter()
                high_risk_detections = high_risk_detector.detect(typed_frame)
                high_risk_detection_times_ms.append(
                    (perf_counter() - high_risk_started) * 1_000
                )
            associated_evidence = associate_high_risk_evidence(high_risk_detections, tracks)
            detection_count += len(detections)
            track_count += len(tracks)
            high_risk_detection_count += len(high_risk_detections)
            observation = FrameObservation(
                source_time_ms=source_time_ms,
                tracks=tracks,
                high_risk_evidence=associated_evidence,
            )
            annotated = _annotate(typed_frame, tracks, zone, high_risk_detections)
            writer.write(annotated)
            if evidence_recorder is not None:
                evidence_recorder.push(source_time_ms, annotated)
            frame_events = engine.process_frame(observation)
            events.extend(frame_events)
            if evidence_recorder is not None:
                for event in frame_events:
                    if event["eventType"] == "zone_intrusion":
                        evidence_recorder.trigger(event["incidentId"], source_time_ms)
    finally:
        writer.release()
        capture.release()

    elapsed = perf_counter() - run_started
    evidence: list[EvidenceArtifact] = []
    if evidence_recorder is not None and evidence_dir is not None:
        evidence = [
            write_evidence_capture(
                capture,
                output_dir=evidence_dir,
                fps=source_fps / frame_stride,
            )
            for capture in evidence_recorder.finalize()
        ]
    incidents = engine.incident_snapshots()
    durations: NDArray[np.float64] = np.asarray(detection_times_ms, dtype=np.float64)
    high_risk_durations: NDArray[np.float64] = np.asarray(
        high_risk_detection_times_ms, dtype=np.float64
    )
    metrics = VideoRunMetrics(
        model=detector.version,
        device=detector.device_name,
        tracker=tracker.version,
        input_frames=input_frames,
        processed_frames=len(detection_times_ms),
        source_fps=source_fps,
        mean_detection_ms=float(durations.mean()) if durations.size else 0.0,
        p95_detection_ms=float(np.percentile(durations, 95)) if durations.size else 0.0,
        mean_high_risk_detection_ms=(
            float(high_risk_durations.mean()) if high_risk_durations.size else 0.0
        ),
        effective_fps=len(detection_times_ms) / elapsed if elapsed else 0.0,
        detected_person_boxes=detection_count,
        emitted_track_boxes=track_count,
        emitted_events=len(events),
        high_risk_detection_boxes=high_risk_detection_count,
    )
    return VideoRunResult(events=events, incidents=incidents, evidence=evidence, metrics=metrics)


def _annotate(
    frame: NDArray[np.uint8],
    tracks: tuple[TrackObservation, ...],
    zone: Zone,
    high_risk_detections: tuple[HighRiskDetection, ...] = (),
) -> NDArray[np.uint8]:
    annotated = frame.copy()
    polygon: NDArray[np.int32] = np.asarray(
        [[round(point.x), round(point.y)] for point in zone.polygon], np.int32
    )
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
    for detection in high_risk_detections:
        box = detection.box
        start = (round(box.x1), round(box.y1))
        end = (round(box.x2), round(box.y2))
        cv2.rectangle(annotated, start, end, (0, 140, 255), 2)
        cv2.putText(
            annotated,
            f"potential firearm {detection.score:.2f}",
            (start[0], max(18, start[1] - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 140, 255),
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
    parser.add_argument("--output-incidents", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--model", choices=SUPPORTED_MODELS, default="ssdlite320")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--high-risk-model", choices=["owlv2-base"])
    parser.add_argument("--high-risk-confidence", type=float, default=0.1)
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
    high_risk_detector = (
        TransformersZeroShotFirearmDetector(
            confidence_threshold=arguments.high_risk_confidence,
        )
        if arguments.high_risk_model
        else None
    )
    result = process_video(
        input_path=arguments.input,
        output_video_path=arguments.output_video,
        detector=detector,
        tracker=tracker,
        zone=zone,
        frame_stride=arguments.frame_stride,
        max_frames=arguments.max_frames,
        evidence_dir=arguments.evidence_dir,
        high_risk_detector=high_risk_detector,
    )
    arguments.output_events.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_events.write_text(json.dumps(result.events, indent=2) + "\n", encoding="utf-8")
    arguments.output_metrics.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_metrics.write_text(
        json.dumps(asdict(result.metrics), indent=2) + "\n", encoding="utf-8"
    )
    if arguments.output_incidents:
        arguments.output_incidents.parent.mkdir(parents=True, exist_ok=True)
        arguments.output_incidents.write_text(
            json.dumps(result.incidents, indent=2) + "\n", encoding="utf-8"
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
