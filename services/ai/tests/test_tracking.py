from __future__ import annotations

from security_ai.domain import BoundingBox, Detection
from security_ai.tracking import ByteTrackPersonTracker


def test_bytetrack_preserves_identity_for_small_motion() -> None:
    tracker = ByteTrackPersonTracker(
        frame_rate=10,
        track_activation_threshold=0.5,
        minimum_consecutive_frames=1,
    )
    first = tracker.update((_detection(10, 10, 50, 100),), timestamp_seconds=0.0)
    second = tracker.update((_detection(12, 10, 52, 100),), timestamp_seconds=0.1)
    third = tracker.update((_detection(14, 10, 54, 100),), timestamp_seconds=0.2)

    assert first == ()
    assert len(second) == 1
    assert len(third) == 1
    assert second[0].track_id == third[0].track_id


def test_bytetrack_accepts_empty_frames() -> None:
    tracker = ByteTrackPersonTracker(frame_rate=10, minimum_consecutive_frames=1)
    assert tracker.update((), timestamp_seconds=0.0) == ()


def _detection(x1: float, y1: float, x2: float, y2: float) -> Detection:
    return Detection(box=BoundingBox(x1, y1, x2, y2), score=0.9)
