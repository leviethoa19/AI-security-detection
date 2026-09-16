from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from security_ai.domain import BoundingBox, Detection, Point, TrackObservation, Zone
from security_ai.video import process_video


class ScriptedDetector:
    version = "scripted-detector-test"
    device_name = "cpu"

    def detect(self, frame: NDArray[np.uint8]) -> tuple[Detection, ...]:
        return (Detection(BoundingBox(30, 10, 60, 80), 0.9),)


class ScriptedTracker:
    version = "scripted-tracker-test"

    def update(
        self,
        detections: tuple[Detection, ...],
        *,
        frame: NDArray[np.uint8] | None = None,
        timestamp_seconds: float | None = None,
    ) -> tuple[TrackObservation, ...]:
        return tuple(
            TrackObservation(str(index + 1), item.box) for index, item in enumerate(detections)
        )


def test_video_pipeline_writes_overlay_and_events(tmp_path: Path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "annotated.mp4"
    _write_fixture_video(input_path)
    zone = Zone(
        zone_id="test-zone",
        polygon=(Point(20, 20), Point(90, 20), Point(90, 90), Point(20, 90)),
    )

    result = process_video(
        input_path=input_path,
        output_video_path=output_path,
        detector=ScriptedDetector(),
        tracker=ScriptedTracker(),
        zone=zone,
        max_frames=4,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert result.metrics.processed_frames == 4
    assert result.metrics.detected_person_boxes == 4
    assert [event["eventType"] for event in result.events[:2]] == [
        "person_observed",
        "zone_intrusion",
    ]


def _write_fixture_video(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (100, 100))
    assert writer.isOpened()
    for value in range(6):
        frame = np.full((100, 100, 3), value * 20, dtype=np.uint8)
        writer.write(frame)
    writer.release()
