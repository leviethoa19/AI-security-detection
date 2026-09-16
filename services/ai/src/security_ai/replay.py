"""Deterministic replay engine for product-semantics validation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from security_ai.contracts import validate_incident_event
from security_ai.domain import ReplayConfiguration, ReplayScenario, TrackObservation
from security_ai.geometry import point_in_polygon
from security_ai.scenarios import load_scenario


@dataclass(slots=True)
class _TrackState:
    episode_number: int
    incident_id: UUID
    last_seen_ms: int
    observed_emitted: bool = False
    inside: bool = False
    inside_since_ms: int | None = None
    outside_since_ms: int | None = None
    intrusion_active: bool = False
    dwell_emitted: bool = False


class ReplayEngine:
    """Convert scripted track observations into versioned incident events."""

    def __init__(self, scenario: ReplayScenario) -> None:
        self._scenario = scenario
        self._started_at = _parse_utc(scenario.started_at)
        self._tracks: dict[str, _TrackState] = {}
        self._events: list[dict[str, Any]] = []

    def run(self) -> list[dict[str, Any]]:
        for frame in self._scenario.frames:
            observed_ids = {track.track_id for track in frame.tracks}
            for track in frame.tracks:
                self._observe(track, frame.source_time_ms)
            self._advance_unobserved(observed_ids, frame.source_time_ms)
        return list(self._events)

    def _observe(self, observation: TrackObservation, now_ms: int) -> None:
        state = self._tracks.get(observation.track_id)
        if state is None:
            state = self._new_state(observation.track_id, now_ms, episode_number=1)
            self._tracks[observation.track_id] = state

        state.last_seen_ms = now_ms
        if not state.observed_emitted:
            self._emit(
                state=state,
                track_id=observation.track_id,
                event_type="person_observed",
                risk_level=1,
                source_time_ms=now_ms,
                reason_codes=["person_present"],
                zone_id=None,
            )
            state.observed_emitted = True

        inside = point_in_polygon(observation.box.foot_point, self._scenario.zone)
        if not self._scenario.armed:
            state.inside = inside
            return

        if inside:
            self._handle_inside(observation.track_id, state, now_ms)
        else:
            self._handle_outside(state, now_ms)

    def _handle_inside(self, track_id: str, state: _TrackState, now_ms: int) -> None:
        if not state.inside:
            if not state.intrusion_active:
                if state.observed_emitted and state.outside_since_ms is not None:
                    state.episode_number += 1
                    state.incident_id = self._incident_id(track_id, state.episode_number)
                state.intrusion_active = True
                state.dwell_emitted = False
                self._emit(
                    state=state,
                    track_id=track_id,
                    event_type="zone_intrusion",
                    risk_level=2,
                    source_time_ms=now_ms,
                    reason_codes=["person_present", "armed_zone_entry"],
                    zone_id=self._scenario.zone.zone_id,
                )
            state.inside_since_ms = now_ms
            state.outside_since_ms = None
            state.inside = True

        assert state.inside_since_ms is not None
        dwell_ms = now_ms - state.inside_since_ms
        if not state.dwell_emitted and dwell_ms >= self._scenario.configuration.dwell_threshold_ms:
            self._emit(
                state=state,
                track_id=track_id,
                event_type="extended_presence",
                risk_level=3,
                source_time_ms=now_ms,
                reason_codes=["dwell_threshold_exceeded"],
                zone_id=self._scenario.zone.zone_id,
            )
            state.dwell_emitted = True

    def _handle_outside(self, state: _TrackState, now_ms: int) -> None:
        if state.inside:
            state.inside = False
            state.inside_since_ms = None
            state.outside_since_ms = now_ms
        self._maybe_resolve(state, now_ms)

    def _advance_unobserved(self, observed_ids: set[str], now_ms: int) -> None:
        for track_id, state in self._tracks.items():
            if track_id in observed_ids:
                continue
            if state.inside:
                state.inside = False
                state.inside_since_ms = None
                state.outside_since_ms = state.last_seen_ms
            self._maybe_resolve(state, now_ms)

    def _maybe_resolve(self, state: _TrackState, now_ms: int) -> None:
        if not state.intrusion_active or state.outside_since_ms is None:
            return
        if now_ms - state.outside_since_ms < self._scenario.configuration.resolution_grace_ms:
            return

        track_id = next(key for key, value in self._tracks.items() if value is state)
        self._emit(
            state=state,
            track_id=track_id,
            event_type="incident_resolved",
            risk_level=0,
            source_time_ms=now_ms,
            reason_codes=["track_left_scene", "resolution_grace_elapsed"],
            zone_id=self._scenario.zone.zone_id,
        )
        state.intrusion_active = False
        state.dwell_emitted = False

    def _new_state(self, track_id: str, now_ms: int, episode_number: int) -> _TrackState:
        return _TrackState(
            episode_number=episode_number,
            incident_id=self._incident_id(track_id, episode_number),
            last_seen_ms=now_ms,
        )

    def _incident_id(self, track_id: str, episode_number: int) -> UUID:
        seed = f"{self._scenario.scenario_id}:{track_id}:episode:{episode_number}"
        return uuid5(NAMESPACE_URL, seed)

    def _emit(
        self,
        *,
        state: _TrackState,
        track_id: str,
        event_type: str,
        risk_level: int,
        source_time_ms: int,
        reason_codes: list[str],
        zone_id: str | None,
    ) -> None:
        event_number = len(self._events) + 1
        event_id = uuid5(
            NAMESPACE_URL,
            f"{self._scenario.scenario_id}:event:{event_number}:{event_type}:{track_id}",
        )
        config: ReplayConfiguration = self._scenario.configuration
        occurred_at = (self._started_at + timedelta(milliseconds=source_time_ms)).isoformat()
        event: dict[str, Any] = {
            "schemaVersion": "1.0",
            "eventId": str(event_id),
            "incidentId": str(state.incident_id),
            "cameraId": self._scenario.camera_id,
            "trackId": track_id,
            "zoneId": zone_id,
            "eventType": event_type,
            "riskLevel": risk_level,
            "occurredAt": occurred_at.replace("+00:00", "Z"),
            "sourceTimeMs": source_time_ms,
            "armed": self._scenario.armed,
            "reasonCodes": reason_codes,
            "components": {
                "detector": config.detector_version,
                "tracker": config.tracker_version,
                "riskEngine": config.risk_engine_version,
                "configuration": config.configuration_version,
            },
        }
        validate_incident_event(event)
        self._events.append(event)


def replay(path: Path) -> list[dict[str, Any]]:
    return ReplayEngine(load_scenario(path)).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay scripted security observations")
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    events = replay(arguments.scenario)
    rendered = json.dumps(events, indent=2) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("startedAt must include a timezone")
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    main()
