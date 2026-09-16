# Milestone status

## M0 — Foundation and reproducibility

**Status:** Complete

- [x] Monorepo boundaries documented
- [x] Python AI package established
- [x] TypeScript shared-contract package established
- [x] Versioned incident-event JSON Schema
- [x] Shared valid fixture tested in Python and TypeScript
- [x] Python linting, strict type checking, and tests
- [x] TypeScript strict checking and tests
- [x] Continuous-integration workflow
- [x] Secrets, data, model, and evidence exclusions
- [x] Initial architecture decision records

## M1 — Deterministic replay walking skeleton

**Status:** Complete

Scripted detections now flow through geometry, zone context, temporal logic, risk levels, and incident lifecycle handling to deterministic, schema-validated JSON output.

- [x] Scripted replay scenario loader
- [x] Bottom-center person-box zone membership
- [x] Boundary-inclusive polygon geometry
- [x] Armed-zone entry event
- [x] Dwell escalation
- [x] Resolution grace period
- [x] Continuous-incident duplicate suppression
- [x] Re-entry behavior before and after resolution
- [x] Missing-track resolution
- [x] Unarmed behavior
- [x] Deterministic identifiers and timestamps
- [x] Command-line replay entry point
- [x] Golden scenario and unit/integration tests

## M2 — Person detection, tracking, and zones

**Status:** Complete

Real person detections now flow through ByteTrack, polygon-zone context, the tested temporal engine, and an annotated-video writer.

- [x] Model-neutral detector protocol
- [x] Official Torchvision SSDLite and Faster R-CNN candidates
- [x] Maintained ByteTrack adapter
- [x] Prerecorded-video pipeline
- [x] Configurable normalized polygon zone
- [x] Track and zone overlays
- [x] Runtime and latency metrics
- [x] Controlled CPU benchmark
- [x] Real person detections produce validated incidents
- [x] Annotated demonstration video

The controlled smoke benchmark selected SSDLite as the current baseline: 48.6 ms mean detector latency (~20.6 FPS) versus 61.0 ms (~16.4 FPS) for low-resolution Faster R-CNN. Both produced 16 person boxes across the eight measured frames. These numbers measure runtime on one repeated pedestrian scene, not generalization or accuracy.

## M3 — Temporal risk and incident evidence

**Status:** Next

The next slice will make the replay engine incrementally streamable, add explicit incident snapshots and timelines, and introduce the rolling pre/post-event evidence buffer without changing risk semantics.

## M4–M9

Not started. See [PROJECT_PLAN.md](PROJECT_PLAN.md) and the approved detailed plan for their exit gates.
