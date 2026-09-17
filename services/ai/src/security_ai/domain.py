"""Domain types for deterministic replay and later live inference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def foot_point(self) -> Point:
        """Use the bottom-center of a person box for floor-zone membership."""

        return Point(x=(self.x1 + self.x2) / 2, y=self.y2)


@dataclass(frozen=True, slots=True)
class TrackObservation:
    track_id: str
    box: BoundingBox


@dataclass(frozen=True, slots=True)
class Detection:
    box: BoundingBox
    score: float
    class_id: int = 1


@dataclass(frozen=True, slots=True)
class FrameObservation:
    source_time_ms: int
    tracks: tuple[TrackObservation, ...]


@dataclass(frozen=True, slots=True)
class Zone:
    zone_id: str
    polygon: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class ReplayConfiguration:
    dwell_threshold_ms: int = 2_000
    resolution_grace_ms: int = 1_000
    evidence_pre_ms: int = 2_000
    evidence_post_ms: int = 2_000
    detector_version: str = "scripted-v1"
    tracker_version: str = "scripted-v1"
    risk_engine_version: str = "rules-v1"
    configuration_version: str = "golden-default-v1"


@dataclass(frozen=True, slots=True)
class ReplayScenario:
    scenario_id: str
    camera_id: str
    started_at: str
    armed: bool
    zone: Zone
    configuration: ReplayConfiguration
    frames: tuple[FrameObservation, ...]
