# M2 detector smoke benchmark

## Question

Which official Torchvision mobile detector is the better starting point for local person tracking on the available CPU runtime?

## Fixture

- Source: Penn-Fudan Pedestrian Database sample image
- Derived input: deterministic 40-frame, 10 FPS clip with a small horizontal translation
- Measured frames: 8 after 2 warm-up frames
- Confidence threshold: 0.5
- Device: CPU (`torch 2.13.0+cpu`, `torchvision 0.28.0+cpu`)

## Results

| Candidate | Mean | Median | P95 | FPS | Boxes |
|---|---:|---:|---:|---:|---:|
| SSDLite320 MobileNetV3 | 48.64 ms | 53.31 ms | 57.37 ms | 20.56 | 16 |
| Faster R-CNN MobileNetV3 320 FPN | 61.02 ms | 62.67 ms | 71.23 ms | 16.39 | 16 |

## Full-pipeline SSDLite run

- Processed frames: 40
- Mean detection latency: 46.70 ms
- P95 detection latency: 58.07 ms
- Effective end-to-end processing rate: 19.66 FPS
- Person detections: 80
- Tracked boxes: 78
- Validated events: 6 (two people: observed, intrusion, extended presence)

## Interpretation

SSDLite is the current baseline because it preserved the observed person count while offering higher throughput. The clip repeats one scene, so these results do not establish accuracy, robustness, or generalization. Those claims require the diverse evaluation set planned for Milestone 5.

## Reproduction

Run `security_ai.benchmark` against the same local smoke clip. Model weights and raw/derived dataset files stay outside Git; the result table is preserved in `outputs/m2-detector-benchmark.csv`.
