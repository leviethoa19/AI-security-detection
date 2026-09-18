"""Loading of deterministic scripted replay scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from security_ai.domain import (
    BoundingBox,
    FrameObservation,
    HighRiskEvidenceObservation,
    Point,
    ReplayConfiguration,
    ReplayScenario,
    TrackObservation,
    Zone,
)


def load_scenario(path: Path) -> ReplayScenario:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    config = raw.get("configuration", {})
    frames = tuple(
        FrameObservation(
            source_time_ms=frame["sourceTimeMs"],
            tracks=tuple(
                TrackObservation(
                    track_id=track["trackId"],
                    box=BoundingBox(*track["box"]),
                )
                for track in frame["tracks"]
            ),
            high_risk_evidence=tuple(
                HighRiskEvidenceObservation(
                    track_id=evidence["trackId"],
                    box=BoundingBox(*evidence["box"]),
                    score=evidence["score"],
                    label=evidence.get("label", "firearm_like"),
                )
                for evidence in frame.get("highRiskEvidence", [])
            ),
        )
        for frame in raw["frames"]
    )
    if tuple(frame.source_time_ms for frame in frames) != tuple(
        sorted(frame.source_time_ms for frame in frames)
    ):
        raise ValueError("scenario frames must be ordered by sourceTimeMs")

    return ReplayScenario(
        scenario_id=raw["scenarioId"],
        camera_id=raw["cameraId"],
        started_at=raw["startedAt"],
        armed=raw["armed"],
        zone=Zone(
            zone_id=raw["zone"]["zoneId"],
            polygon=tuple(Point(*point) for point in raw["zone"]["polygon"]),
        ),
        configuration=ReplayConfiguration(
            dwell_threshold_ms=config.get("dwellThresholdMs", 2_000),
            resolution_grace_ms=config.get("resolutionGraceMs", 1_000),
            evidence_pre_ms=config.get("evidencePreMs", 2_000),
            evidence_post_ms=config.get("evidencePostMs", 2_000),
            high_risk_window_ms=config.get("highRiskWindowMs", 1_500),
            high_risk_min_positive_frames=config.get("highRiskMinPositiveFrames", 3),
            high_risk_min_mean_score=config.get("highRiskMinMeanScore", 0.25),
            detector_version=config.get("detectorVersion", "scripted-v1"),
            tracker_version=config.get("trackerVersion", "scripted-v1"),
            high_risk_detector_version=config.get("highRiskDetectorVersion", "disabled"),
            risk_engine_version=config.get("riskEngineVersion", "rules-v1"),
            configuration_version=config.get("configurationVersion", "golden-default-v1"),
        ),
        frames=frames,
    )
