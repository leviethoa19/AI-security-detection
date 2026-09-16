# M1 deterministic walking skeleton

## Purpose

This slice proves product semantics without allowing detector errors to obscure state-machine defects. A scenario provides timestamps and already-tracked person boxes. The replay engine converts them to explainable, versioned events.

```text
scripted track boxes
        |
        v
bottom-center zone test
        |
        v
entry / dwell / exit context
        |
        v
incident lifecycle and risk
        |
        v
shared-contract validation
        |
        v
deterministic JSON events
```

## Golden scenario

| Source time | Observation | Result |
|---:|---|---|
| 0 ms | Track 7 outside zone | Person observed, risk 1 |
| 500 ms | Track 7 enters armed zone | Zone intrusion, risk 2 |
| 1500 ms | Track 7 remains for threshold | Extended presence, risk 3 |
| 2500 ms | Track 7 leaves | Resolution grace begins |
| 3500 ms | Track remains outside | Incident resolved, risk 0 |

All four events retain one incident identifier. Event identifiers, incident identifiers, and timestamps are deterministic for a given scenario.

## Tested edge behavior

- A polygon boundary counts as inside.
- Continuous presence emits one intrusion, not one per frame.
- Re-entry during the resolution grace period keeps the same incident.
- Re-entry after resolution opens a new incident identifier.
- A missing track resolves after the grace period.
- Entering a zone while unarmed does not open an intrusion.

## Deliberate limitation

Track IDs are provided by the scenario. Milestone 2 supplies real detection and tracking adapters; the event engine remains unchanged.
