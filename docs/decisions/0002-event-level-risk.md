# ADR 0002: Event-level, explainable risk

- **Status:** Accepted
- **Date:** 2026-09-16

## Decision

Treat incidents, rather than frames, as the primary product and evaluation unit. Begin with deterministic, explainable temporal rules, reason codes, hysteresis, cooldowns, and a documented incident state machine.

## Consequences

- A single high detector score cannot create a high-risk incident by itself.
- Tests can isolate product logic from model quality with scripted detections.
- Model-level metrics remain diagnostic; event precision, recall, false alerts per camera-hour, duplicates, and delay are primary.

