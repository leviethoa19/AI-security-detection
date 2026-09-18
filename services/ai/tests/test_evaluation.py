from __future__ import annotations

from pathlib import Path

import pytest

from security_ai.evaluation import GroundTruthEvent, match_events, run_evaluation

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "evaluation"


def test_event_matching_reports_true_false_and_missed_events() -> None:
    truth = (
        GroundTruthEvent("high_risk_evidence", "person-1", 0, 1500),
        GroundTruthEvent("high_risk_evidence", "person-2", 2000, 3000),
    )
    predictions = [
        {"eventType": "high_risk_evidence", "trackId": "person-1", "sourceTimeMs": 1000},
        {"eventType": "high_risk_evidence", "trackId": "person-1", "sourceTimeMs": 1200},
        {"eventType": "high_risk_evidence", "trackId": "noise", "sourceTimeMs": 500},
    ]

    rows = match_events(predictions, truth)

    assert [row["outcome"] for row in rows] == ["FP", "TP", "FP", "FN"]
    assert next(row for row in rows if row["outcome"] == "TP")["delayMs"] == 1000
    assert any(row["failureCategory"] == "duplicate_event" for row in rows)


def test_controlled_study_reproduces_variant_metrics(tmp_path: Path) -> None:
    summary = run_evaluation(FIXTURE_DIR / "manifest.json", tmp_path)
    metrics = {row["variant"]: row for row in summary["metrics"]}

    assert summary["scenarioCount"] == 6
    assert metrics["frame_baseline"]["precision"] == pytest.approx(0.6)
    assert metrics["frame_baseline"]["recall"] == 1.0
    assert metrics["frame_baseline"]["falseAlertsPerCameraHour"] == pytest.approx(300)
    assert metrics["temporal_system"]["precision"] == 1.0
    assert metrics["temporal_system"]["recall"] == 1.0
    assert metrics["temporal_system"]["duplicateAlerts"] == 0
    for name in (
        "event-outcomes.csv",
        "predictions.csv",
        "metrics.csv",
        "subgroup-metrics.csv",
        "summary.json",
        "report.md",
        "variant-comparison.png",
    ):
        assert (tmp_path / name).is_file()
