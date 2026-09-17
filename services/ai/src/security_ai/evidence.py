"""Bounded pre/post-event frame buffering and local evidence artifacts."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class BufferedFrame:
    source_time_ms: int
    image: NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class EvidenceCapture:
    incident_id: str
    trigger_source_time_ms: int
    frames: tuple[BufferedFrame, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    incident_id: str
    clip_path: str
    thumbnail_path: str
    manifest_path: str
    started_source_time_ms: int
    ended_source_time_ms: int
    frame_count: int
    complete: bool


@dataclass(slots=True)
class _ActiveCapture:
    incident_id: str
    trigger_source_time_ms: int
    frames: list[BufferedFrame]


class RollingEvidenceRecorder:
    """Keep only a bounded rolling buffer until an incident requests evidence."""

    def __init__(self, *, pre_event_ms: int = 2_000, post_event_ms: int = 2_000) -> None:
        if pre_event_ms < 0 or post_event_ms < 0:
            raise ValueError("evidence windows cannot be negative")
        self._pre_event_ms = pre_event_ms
        self._post_event_ms = post_event_ms
        self._buffer: deque[BufferedFrame] = deque()
        self._active: dict[str, _ActiveCapture] = {}
        self._completed: list[EvidenceCapture] = []
        self._triggered: set[str] = set()
        self._last_source_time_ms: int | None = None

    def push(self, source_time_ms: int, image: NDArray[np.uint8]) -> None:
        if self._last_source_time_ms is not None and source_time_ms < self._last_source_time_ms:
            raise ValueError("evidence frames must be ordered by source_time_ms")
        frame = BufferedFrame(source_time_ms=source_time_ms, image=image.copy())
        self._buffer.append(frame)
        cutoff = source_time_ms - self._pre_event_ms
        while self._buffer and self._buffer[0].source_time_ms < cutoff:
            self._buffer.popleft()

        completed_ids: list[str] = []
        for incident_id, capture in self._active.items():
            deadline = capture.trigger_source_time_ms + self._post_event_ms
            if source_time_ms > capture.trigger_source_time_ms and source_time_ms <= deadline:
                capture.frames.append(frame)
            if source_time_ms >= deadline:
                self._completed.append(self._freeze(capture, complete=True))
                completed_ids.append(incident_id)
        for incident_id in completed_ids:
            del self._active[incident_id]
        self._last_source_time_ms = source_time_ms

    def trigger(self, incident_id: str, source_time_ms: int) -> bool:
        """Start one capture per incident; return False for duplicate triggers."""

        if incident_id in self._triggered:
            return False
        if self._last_source_time_ms is not None and source_time_ms > self._last_source_time_ms:
            raise ValueError("trigger time cannot be ahead of the latest buffered frame")
        frames = [frame for frame in self._buffer if frame.source_time_ms <= source_time_ms]
        capture = _ActiveCapture(incident_id, source_time_ms, frames)
        self._triggered.add(incident_id)
        if self._post_event_ms == 0:
            self._completed.append(self._freeze(capture, complete=True))
        else:
            self._active[incident_id] = capture
        return True

    def drain_completed(self) -> list[EvidenceCapture]:
        completed = self._completed
        self._completed = []
        return completed

    def finalize(self) -> list[EvidenceCapture]:
        completed = self.drain_completed()
        completed.extend(self._freeze(capture, complete=False) for capture in self._active.values())
        self._active.clear()
        return completed

    @staticmethod
    def _freeze(capture: _ActiveCapture, *, complete: bool) -> EvidenceCapture:
        return EvidenceCapture(
            incident_id=capture.incident_id,
            trigger_source_time_ms=capture.trigger_source_time_ms,
            frames=tuple(capture.frames),
            complete=complete,
        )


def write_evidence_capture(
    capture: EvidenceCapture, *, output_dir: Path, fps: float
) -> EvidenceArtifact:
    if not capture.frames:
        raise ValueError("cannot write an evidence capture without frames")
    if fps <= 0:
        raise ValueError("evidence fps must be positive")

    incident_dir = output_dir / capture.incident_id
    incident_dir.mkdir(parents=True, exist_ok=True)
    clip_path = incident_dir / "evidence.mp4"
    thumbnail_path = incident_dir / "thumbnail.jpg"
    manifest_path = incident_dir / "manifest.json"
    height, width = capture.frames[0].image.shape[:2]
    writer = cv2.VideoWriter(
        str(clip_path),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise ValueError(f"could not create evidence clip: {clip_path}")
    try:
        for frame in capture.frames:
            if frame.image.shape[:2] != (height, width):
                raise ValueError("all evidence frames must have the same dimensions")
            writer.write(frame.image)
    finally:
        writer.release()

    thumbnail_frame = min(
        capture.frames,
        key=lambda frame: abs(frame.source_time_ms - capture.trigger_source_time_ms),
    )
    if not cv2.imwrite(str(thumbnail_path), thumbnail_frame.image):
        raise ValueError(f"could not create evidence thumbnail: {thumbnail_path}")

    artifact = EvidenceArtifact(
        incident_id=capture.incident_id,
        clip_path=str(clip_path),
        thumbnail_path=str(thumbnail_path),
        manifest_path=str(manifest_path),
        started_source_time_ms=capture.frames[0].source_time_ms,
        ended_source_time_ms=capture.frames[-1].source_time_ms,
        frame_count=len(capture.frames),
        complete=capture.complete,
    )
    manifest = {
        "schemaVersion": "1.0",
        "incidentId": artifact.incident_id,
        "triggerSourceTimeMs": capture.trigger_source_time_ms,
        "startedSourceTimeMs": artifact.started_source_time_ms,
        "endedSourceTimeMs": artifact.ended_source_time_ms,
        "frameCount": artifact.frame_count,
        "complete": artifact.complete,
        "clip": clip_path.name,
        "thumbnail": thumbnail_path.name,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return artifact
