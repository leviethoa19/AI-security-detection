from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from security_ai.contracts import validate_incident_event
from security_ai.domain import BoundingBox, FrameObservation, TrackObservation
from security_ai.replay import ReplayEngine, replay
from security_ai.scenarios import load_scenario

FIXTURES = Path(__file__).parent / "fixtures"


def test_entry_dwell_exit_golden_scenario() -> None:
    events = replay(FIXTURES / "entry_dwell_exit.json")

    assert [event["eventType"] for event in events] == [
        "person_observed",
        "zone_intrusion",
        "extended_presence",
        "incident_resolved",
    ]
    assert [event["sourceTimeMs"] for event in events] == [0, 500, 1500, 3500]
    assert [event["riskLevel"] for event in events] == [1, 2, 3, 0]
    assert len({event["incidentId"] for event in events}) == 1
    for event in events:
        validate_incident_event(event)


def test_replay_is_deterministic() -> None:
    path = FIXTURES / "entry_dwell_exit.json"
    assert replay(path) == replay(path)


def test_incremental_processing_matches_batch_replay() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    engine = ReplayEngine(replace(scenario, frames=()))

    streamed = [event for frame in scenario.frames for event in engine.process_frame(frame)]

    assert streamed == ReplayEngine(scenario).run()
    assert engine.events == streamed


def test_incremental_processing_rejects_out_of_order_frames() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    engine = ReplayEngine(replace(scenario, frames=()))
    engine.process_frame(_frame(500, inside=True))

    try:
        engine.process_frame(_frame(499, inside=True))
    except ValueError as error:
        assert "ordered" in str(error)
    else:
        raise AssertionError("out-of-order frame was accepted")


def test_incident_snapshot_contains_timeline_and_peak_risk() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    engine = ReplayEngine(scenario)
    engine.run()

    snapshots = engine.incident_snapshots()

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot["status"] == "resolved"
    assert snapshot["currentRiskLevel"] == 0
    assert snapshot["peakRiskLevel"] == 3
    assert [entry["eventType"] for entry in snapshot["timeline"]] == [
        "zone_intrusion",
        "extended_presence",
        "incident_resolved",
    ]


def test_continuous_intrusion_is_not_duplicated() -> None:
    events = replay(FIXTURES / "entry_dwell_exit.json")
    assert sum(event["eventType"] == "zone_intrusion" for event in events) == 1


def test_reentry_during_resolution_grace_keeps_one_incident() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    scenario = replace(
        scenario,
        frames=(
            _frame(0, inside=False),
            _frame(500, inside=True),
            _frame(1_500, inside=False),
            _frame(2_000, inside=True),
            _frame(3_000, inside=True),
        ),
    )

    events = ReplayEngine(scenario).run()
    assert [event["eventType"] for event in events] == [
        "person_observed",
        "zone_intrusion",
        "extended_presence",
    ]
    assert len({event["incidentId"] for event in events}) == 1


def test_reentry_after_resolution_starts_new_incident() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    scenario = replace(
        scenario,
        frames=(
            _frame(0, inside=False),
            _frame(500, inside=True),
            _frame(1_000, inside=False),
            _frame(2_000, inside=False),
            _frame(2_500, inside=True),
        ),
    )

    events = ReplayEngine(scenario).run()
    intrusions = [event for event in events if event["eventType"] == "zone_intrusion"]
    assert len(intrusions) == 2
    assert intrusions[0]["incidentId"] != intrusions[1]["incidentId"]


def test_unarmed_zone_entry_does_not_open_intrusion() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    scenario = replace(scenario, armed=False)

    events = ReplayEngine(scenario).run()
    assert [event["eventType"] for event in events] == ["person_observed"]


def test_missing_track_resolves_after_grace() -> None:
    scenario = load_scenario(FIXTURES / "entry_dwell_exit.json")
    scenario = replace(
        scenario,
        frames=(
            _frame(0, inside=True),
            FrameObservation(source_time_ms=500, tracks=()),
            FrameObservation(source_time_ms=1_000, tracks=()),
        ),
    )

    events = ReplayEngine(scenario).run()
    assert [event["eventType"] for event in events] == [
        "person_observed",
        "zone_intrusion",
        "incident_resolved",
    ]


def _frame(source_time_ms: int, *, inside: bool) -> FrameObservation:
    box = BoundingBox(60, 20, 80, 70) if inside else BoundingBox(0, 0, 20, 40)
    return FrameObservation(
        source_time_ms=source_time_ms,
        tracks=(TrackObservation(track_id="7", box=box),),
    )
