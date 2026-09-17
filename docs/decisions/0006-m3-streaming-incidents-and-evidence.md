# ADR 0006: Streaming incidents and bounded local evidence

- **Status:** Accepted
- **Date:** 2026-09-17

## Decision

Process tracked observations incrementally through the same deterministic engine used by batch replay. Materialize an incident snapshot from its versioned event timeline, and start one bounded pre/post-event evidence capture when an armed-zone intrusion opens an incident.

Evidence consists of a short annotated clip, a trigger-adjacent thumbnail, and a JSON manifest. It remains local until the secure backend milestone. The recorder holds only the configured rolling window before an incident and stops after the post-event window.

## Consequences

- Batch replay and future live input share one state machine.
- Every incident exposes current and peak risk, status, reason codes, timeline, component versions, and the exact temporal configuration.
- Repeated events for the same incident cannot create duplicate evidence sets.
- A source ending early produces an explicitly incomplete evidence manifest rather than silently claiming a full post-event window.
- Generated media stays outside Git and continuous video is not uploaded or retained by this feature.
