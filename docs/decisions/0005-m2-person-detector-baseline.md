# ADR 0005: M2 person-detector baseline

- **Status:** Accepted
- **Date:** 2026-09-16

## Decision

Use Torchvision SSDLite320 MobileNetV3 as the initial person-detection baseline and keep low-resolution Faster R-CNN MobileNetV3 as a comparison candidate. Use the maintained standalone `trackers` package for ByteTrack.

## Evidence

On the controlled Penn-Fudan smoke clip, using CPU inference and a 0.5 threshold:

| Candidate | Mean latency | P95 latency | Effective detector FPS | Person boxes |
|---|---:|---:|---:|---:|
| SSDLite320 MobileNetV3 | 48.6 ms | 57.4 ms | 20.6 | 16 |
| Faster R-CNN MobileNetV3 320 FPN | 61.0 ms | 71.2 ms | 16.4 | 16 |

The measurement used two warm-up frames followed by eight measured frames from the same controlled clip. It is a runtime smoke benchmark, not an accuracy study.

## Rationale

Both candidates emitted the same count on this fixture, while SSDLite was approximately 20% faster and its official weights are much smaller. The adapter boundary preserves the ability to change this choice after diverse event-level evaluation.

## Licensing note

Torchvision code is BSD-licensed, but pretrained weights can inherit terms from their training data. Dataset and weight suitability must still be reviewed before any commercial use. The current use is a local portfolio prototype using COCO-pretrained weights and a public pedestrian sample.

