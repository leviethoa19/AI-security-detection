# ADR 0008: Event-window evaluation and controlled baseline comparison

- **Status:** Accepted
- **Date:** 2026-09-18

## Decision

Evaluate product behavior at event level by matching replayed events to annotated time
windows, grouped by event type and track. Use the same replay engine for every experiment
variant. Compare a one-frame high-risk baseline with the three-frame temporal system by
changing one configuration field only.

Store evaluation definitions in a shared JSON Schema with scenario-level `splitGroup`,
split, duration, subgroup metadata, and ground truth. Produce raw prediction/outcome CSVs,
aggregate metrics, subgroup metrics, a machine-readable snapshot, a Markdown report, and
a comparison plot from one command.

## Rationale

- Time windows tolerate expected event delay without hiding duplicate alerts.
- A shared engine prevents evaluation behavior from drifting away from product behavior.
- Group-level splits prevent related clips or scenario variants leaking across partitions.
- Pandas supports auditable tables, NumPy-backed aggregation, and scikit-learn provides
  standard precision/recall/F1 calculations.

## Limits

The first M5 dataset is scripted and validates semantics, determinism, and reporting. It
does not estimate real-world detector accuracy or deployment false-alert rates. The same
evaluator must later run on annotated video scenarios after M6.
