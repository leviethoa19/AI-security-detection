"""Batch event evaluation using the production replay engine."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from security_ai.contracts import validate_evaluation_manifest
from security_ai.replay import ReplayEngine
from security_ai.scenarios import load_scenario


@dataclass(frozen=True, slots=True)
class GroundTruthEvent:
    event_type: str
    track_id: str
    onset_time_ms: int
    window_end_ms: int
    failure_category: str | None = None


def match_events(
    predictions: list[dict[str, Any]],
    ground_truth: tuple[GroundTruthEvent, ...],
) -> list[dict[str, Any]]:
    """Greedily match event predictions inside annotated incident windows."""

    unmatched = set(range(len(ground_truth)))
    rows: list[dict[str, Any]] = []
    for prediction in sorted(predictions, key=lambda item: int(item["sourceTimeMs"])):
        source_time_ms = int(prediction["sourceTimeMs"])
        candidates = [
            (index, abs(source_time_ms - ground_truth[index].onset_time_ms))
            for index in unmatched
            if prediction["eventType"] == ground_truth[index].event_type
            and prediction["trackId"] == ground_truth[index].track_id
            and ground_truth[index].onset_time_ms
            <= source_time_ms
            <= ground_truth[index].window_end_ms
        ]
        if candidates:
            selected, _ = min(candidates, key=lambda item: item[1])
            expected = ground_truth[selected]
            unmatched.remove(selected)
            rows.append(
                _outcome_row(
                    outcome="TP",
                    event_type=expected.event_type,
                    track_id=expected.track_id,
                    source_time_ms=source_time_ms,
                    onset_time_ms=expected.onset_time_ms,
                    failure_category=None,
                )
            )
        else:
            duplicate = any(
                prediction["eventType"] == expected.event_type
                and prediction["trackId"] == expected.track_id
                and expected.onset_time_ms <= source_time_ms <= expected.window_end_ms
                for expected in ground_truth
            )
            rows.append(
                _outcome_row(
                    outcome="FP",
                    event_type=str(prediction["eventType"]),
                    track_id=str(prediction["trackId"]),
                    source_time_ms=source_time_ms,
                    onset_time_ms=None,
                    failure_category="duplicate_event" if duplicate else "unexpected_event",
                )
            )
    for index in sorted(unmatched):
        expected = ground_truth[index]
        rows.append(
            _outcome_row(
                outcome="FN",
                event_type=expected.event_type,
                track_id=expected.track_id,
                source_time_ms=None,
                onset_time_ms=expected.onset_time_ms,
                failure_category=expected.failure_category or "missed_event",
            )
        )
    return rows


def _outcome_row(
    *,
    outcome: str,
    event_type: str,
    track_id: str,
    source_time_ms: int | None,
    onset_time_ms: int | None,
    failure_category: str | None,
) -> dict[str, Any]:
    delay_ms = (
        source_time_ms - onset_time_ms
        if source_time_ms is not None and onset_time_ms is not None
        else None
    )
    return {
        "outcome": outcome,
        "eventType": event_type,
        "trackId": track_id,
        "sourceTimeMs": source_time_ms,
        "onsetTimeMs": onset_time_ms,
        "delayMs": delay_ms,
        "failureCategory": failure_category,
    }


def run_evaluation(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_evaluation_manifest(raw)
    _validate_manifest_semantics(raw)
    event_types = set(raw["eventTypes"])
    outcomes: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    total_duration_ms = sum(int(item["durationMs"]) for item in raw["scenarios"])

    for item in raw["scenarios"]:
        scenario_path = manifest_path.parent / str(item["scenarioPath"])
        scenario = load_scenario(scenario_path)
        if scenario.scenario_id != item["scenarioId"]:
            raise ValueError(f"scenarioId mismatch for {scenario_path}")
        truth = tuple(
            GroundTruthEvent(
                event_type=value["eventType"],
                track_id=value["trackId"],
                onset_time_ms=value["onsetTimeMs"],
                window_end_ms=value["windowEndMs"],
                failure_category=value.get("failureCategory"),
            )
            for value in item["groundTruth"]
            if value["eventType"] in event_types
        )
        variants = {
            "frame_baseline": replace(
                scenario,
                configuration=replace(
                    scenario.configuration,
                    high_risk_min_positive_frames=1,
                    configuration_version="evaluation-frame-baseline-v1",
                ),
            ),
            "temporal_system": scenario,
        }
        for variant, configured_scenario in variants.items():
            emitted = [
                event
                for event in ReplayEngine(configured_scenario).run()
                if event["eventType"] in event_types
            ]
            for event in emitted:
                predictions.append(
                    {
                        "variant": variant,
                        "scenarioId": item["scenarioId"],
                        "eventType": event["eventType"],
                        "trackId": event["trackId"],
                        "sourceTimeMs": event["sourceTimeMs"],
                        "riskLevel": event["riskLevel"],
                    }
                )
            for row in match_events(emitted, truth):
                outcomes.append(
                    {
                        "variant": variant,
                        "scenarioId": item["scenarioId"],
                        "split": item["split"],
                        "durationMs": item["durationMs"],
                        **item["subgroups"],
                        **row,
                    }
                )

    outcome_frame = pd.DataFrame(outcomes)
    prediction_frame = pd.DataFrame(predictions)
    metrics_frame = _metrics(outcome_frame, total_duration_ms)
    subgroup_frame = _subgroup_metrics(outcome_frame, raw["scenarios"])
    output_dir.mkdir(parents=True, exist_ok=True)
    outcome_frame.to_csv(output_dir / "event-outcomes.csv", index=False)
    prediction_frame.to_csv(output_dir / "predictions.csv", index=False)
    metrics_frame.to_csv(output_dir / "metrics.csv", index=False)
    subgroup_frame.to_csv(output_dir / "subgroup-metrics.csv", index=False)
    _write_plot(metrics_frame, output_dir / "variant-comparison.png")
    report = _build_report(raw, metrics_frame, subgroup_frame, outcome_frame)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    summary = {
        "schemaVersion": "1.0",
        "datasetId": raw["datasetId"],
        "manifest": str(manifest_path),
        "scenarioCount": len(raw["scenarios"]),
        "totalDurationMs": total_duration_ms,
        "variants": {
            "frame_baseline": {"highRiskMinPositiveFrames": 1},
            "temporal_system": {"highRiskMinPositiveFrames": 3},
        },
        "metrics": metrics_frame.to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _validate_manifest_semantics(raw: dict[str, Any]) -> None:
    groups: dict[str, str] = {}
    scenario_ids: set[str] = set()
    for scenario in raw["scenarios"]:
        scenario_id = str(scenario["scenarioId"])
        if scenario_id in scenario_ids:
            raise ValueError(f"duplicate scenarioId: {scenario_id}")
        scenario_ids.add(scenario_id)
        group, split = str(scenario["splitGroup"]), str(scenario["split"])
        if group in groups and groups[group] != split:
            raise ValueError(f"splitGroup {group} appears in multiple splits")
        groups[group] = split
        for event in scenario["groundTruth"]:
            if event["windowEndMs"] < event["onsetTimeMs"]:
                raise ValueError(f"ground-truth window ends before onset in {scenario_id}")
            if event["windowEndMs"] > scenario["durationMs"]:
                raise ValueError(f"ground-truth window exceeds duration in {scenario_id}")


def _metrics(frame: pd.DataFrame, total_duration_ms: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, group in frame.groupby("variant", sort=True):
        counts = group["outcome"].value_counts()
        true_positives = int(counts.get("TP", 0))
        false_positives = int(counts.get("FP", 0))
        false_negatives = int(counts.get("FN", 0))
        y_true = [1] * true_positives + [0] * false_positives + [1] * false_negatives
        y_pred = [1] * true_positives + [1] * false_positives + [0] * false_negatives
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="binary", zero_division=0
        )
        delays = group.loc[group["outcome"] == "TP", "delayMs"].dropna()
        rows.append(
            {
                "variant": variant,
                "truePositives": true_positives,
                "falsePositives": false_positives,
                "falseNegatives": false_negatives,
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "falseAlertsPerCameraHour": false_positives / (total_duration_ms / 3_600_000),
                "meanDetectionDelayMs": float(delays.mean()) if not delays.empty else None,
                "duplicateAlerts": int((group["failureCategory"] == "duplicate_event").sum()),
            }
        )
    return pd.DataFrame(rows)


def _subgroup_metrics(frame: pd.DataFrame, scenarios: list[dict[str, Any]]) -> pd.DataFrame:
    subgroup_names = sorted({name for item in scenarios for name in item["subgroups"]})
    rows: list[dict[str, Any]] = []
    for subgroup_name in subgroup_names:
        values = sorted({str(item["subgroups"][subgroup_name]) for item in scenarios})
        for variant in ("frame_baseline", "temporal_system"):
            for value in values:
                scenario_ids = {
                    item["scenarioId"]
                    for item in scenarios
                    if item["subgroups"][subgroup_name] == value
                }
                group = frame[
                    (frame["variant"] == variant) & frame["scenarioId"].isin(scenario_ids)
                ]
                counts = group["outcome"].value_counts()
                tp, fp, fn = (int(counts.get(name, 0)) for name in ("TP", "FP", "FN"))
                rows.append(
                    {
                        "variant": variant,
                        "subgroup": subgroup_name,
                        "value": value,
                        "scenarioCount": len(scenario_ids),
                        "truePositives": tp,
                        "falsePositives": fp,
                        "falseNegatives": fn,
                        "precision": tp / (tp + fp) if tp + fp else None,
                        "recall": tp / (tp + fn) if tp + fn else None,
                    }
                )
    return pd.DataFrame(rows)


def _write_plot(metrics: pd.DataFrame, path: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(path.parent / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plot = metrics.set_index("variant")[["precision", "recall", "f1"]].plot.bar(
        ylim=(0, 1), rot=0, title="Controlled event-level comparison"
    )
    plot.set_ylabel("Score")
    plot.figure.tight_layout()
    plot.figure.savefig(path, dpi=160)
    plt.close(plot.figure)


def _build_report(
    manifest: dict[str, Any],
    metrics: pd.DataFrame,
    subgroups: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> str:
    lines = [
        "# Controlled event evaluation",
        "",
        f"Dataset: `{manifest['datasetId']}` ({len(manifest['scenarios'])} scenarios).",
        "",
        "This report validates event semantics on scripted observations. It does not measure",
        "real-world detector generalization.",
        "",
        "## Variant metrics",
        "",
        _markdown_table(metrics),
        "",
        "## Subgroup metrics",
        "",
        _markdown_table(subgroups),
        "",
        "## Errors",
        "",
    ]
    errors = outcomes[outcomes["outcome"] != "TP"]
    if errors.empty:
        lines.append("No false-positive or false-negative events in this controlled set.")
    else:
        lines.append(
            _markdown_table(errors[["variant", "scenarioId", "outcome", "failureCategory"]])
        )
    lines.extend(
        [
            "",
            "False-alerts-per-hour is extrapolated from a very short controlled timeline and",
            "must not be interpreted as a deployment estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    columns = list(frame.columns)
    rendered = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame.itertuples(index=False, name=None):
        rendered.append("| " + " | ".join(_format_cell(value) for value in row) + " |")
    return "\n".join(rendered)


def _format_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled event-level evaluation")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    summary = run_evaluation(arguments.manifest, arguments.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
