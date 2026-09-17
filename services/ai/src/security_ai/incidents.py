"""Materialize incident snapshots and explainable timelines from event streams."""

from __future__ import annotations

from typing import Any

from security_ai.contracts import validate_incident_snapshot
from security_ai.domain import ReplayConfiguration


def build_incident_snapshots(
    events: list[dict[str, Any]], configuration: ReplayConfiguration
) -> list[dict[str, Any]]:
    """Fold versioned events into one current snapshot per opened incident."""

    snapshots: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = event["eventType"]
        incident_id = event["incidentId"]
        if event_type == "person_observed":
            continue
        snapshot = snapshots.get(incident_id)
        if snapshot is None:
            if event_type != "zone_intrusion":
                continue
            snapshot = _open_snapshot(event, configuration)
            snapshots[incident_id] = snapshot
        else:
            _apply_event(snapshot, event)

    result = list(snapshots.values())
    for snapshot in result:
        validate_incident_snapshot(snapshot)
    return result


def _open_snapshot(
    event: dict[str, Any], configuration: ReplayConfiguration
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "incidentId": event["incidentId"],
        "cameraId": event["cameraId"],
        "trackId": event["trackId"],
        "zoneId": event["zoneId"],
        "status": "active",
        "currentRiskLevel": event["riskLevel"],
        "peakRiskLevel": event["riskLevel"],
        "openedAt": event["occurredAt"],
        "updatedAt": event["occurredAt"],
        "resolvedAt": None,
        "openedSourceTimeMs": event["sourceTimeMs"],
        "updatedSourceTimeMs": event["sourceTimeMs"],
        "resolvedSourceTimeMs": None,
        "reasonCodes": list(event["reasonCodes"]),
        "timeline": [_timeline_entry(event)],
        "components": dict(event["components"]),
        "configuration": {
            "dwellThresholdMs": configuration.dwell_threshold_ms,
            "resolutionGraceMs": configuration.resolution_grace_ms,
            "evidencePreMs": configuration.evidence_pre_ms,
            "evidencePostMs": configuration.evidence_post_ms,
            "highRiskWindowMs": configuration.high_risk_window_ms,
            "highRiskMinPositiveFrames": configuration.high_risk_min_positive_frames,
            "highRiskMinMeanScore": configuration.high_risk_min_mean_score,
        },
    }


def _apply_event(snapshot: dict[str, Any], event: dict[str, Any]) -> None:
    snapshot["updatedAt"] = event["occurredAt"]
    snapshot["updatedSourceTimeMs"] = event["sourceTimeMs"]
    snapshot["currentRiskLevel"] = event["riskLevel"]
    snapshot["peakRiskLevel"] = max(snapshot["peakRiskLevel"], event["riskLevel"])
    snapshot["timeline"].append(_timeline_entry(event))
    for reason_code in event["reasonCodes"]:
        if reason_code not in snapshot["reasonCodes"]:
            snapshot["reasonCodes"].append(reason_code)

    if event["eventType"] == "incident_resolved":
        snapshot["status"] = "resolved"
        snapshot["resolvedAt"] = event["occurredAt"]
        snapshot["resolvedSourceTimeMs"] = event["sourceTimeMs"]
    elif event["riskLevel"] >= 3:
        snapshot["status"] = "escalated"


def _timeline_entry(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "eventId": event["eventId"],
        "eventType": event["eventType"],
        "riskLevel": event["riskLevel"],
        "occurredAt": event["occurredAt"],
        "sourceTimeMs": event["sourceTimeMs"],
        "reasonCodes": list(event["reasonCodes"]),
    }
