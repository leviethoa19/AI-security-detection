"""Tracking adapters that convert detections into stable track observations."""

from __future__ import annotations

from typing import Protocol

import numpy as np
import supervision as sv
from numpy.typing import NDArray
from trackers import ByteTrackTracker

from security_ai.domain import BoundingBox, Detection, TrackObservation


class PersonTracker(Protocol):
    @property
    def version(self) -> str: ...

    def update(
        self,
        detections: tuple[Detection, ...],
        *,
        frame: NDArray[np.uint8] | None = None,
        timestamp_seconds: float | None = None,
    ) -> tuple[TrackObservation, ...]: ...


class ByteTrackPersonTracker:
    """Adapter over the maintained standalone ByteTrack implementation."""

    def __init__(
        self,
        *,
        frame_rate: float,
        track_activation_threshold: float = 0.5,
        lost_track_buffer: int = 30,
        minimum_consecutive_frames: int = 1,
    ) -> None:
        self._tracker = ByteTrackTracker(
            frame_rate=frame_rate,
            track_activation_threshold=track_activation_threshold,
            high_conf_det_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_consecutive_frames=minimum_consecutive_frames,
        )

    @property
    def version(self) -> str:
        return "bytetrack-trackers-2.6"

    def update(
        self,
        detections: tuple[Detection, ...],
        *,
        frame: NDArray[np.uint8] | None = None,
        timestamp_seconds: float | None = None,
    ) -> tuple[TrackObservation, ...]:
        if detections:
            xyxy = np.asarray(
                [[item.box.x1, item.box.y1, item.box.x2, item.box.y2] for item in detections],
                dtype=np.float32,
            )
            confidence = np.asarray([item.score for item in detections], dtype=np.float32)
            class_id = np.asarray([item.class_id for item in detections], dtype=int)
        else:
            xyxy = np.empty((0, 4), dtype=np.float32)
            confidence = np.empty((0,), dtype=np.float32)
            class_id = np.empty((0,), dtype=int)

        tracked = self._tracker.update(
            sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id),
            timestamp=timestamp_seconds,
        )
        if tracked.tracker_id is None:
            return ()

        observations: list[TrackObservation] = []
        for box, track_id in zip(tracked.xyxy, tracked.tracker_id, strict=True):
            if int(track_id) < 0:
                continue
            observations.append(
                TrackObservation(
                    track_id=str(int(track_id)),
                    box=BoundingBox(*(float(value) for value in box)),
                )
            )
        return tuple(observations)
