# M5 controlled event-level study

## Question

Does three-frame temporal persistence suppress transient firearm-like evidence without
missing persistent evidence in the controlled scenario suite?

## Setup

- Six scripted, four-second scenarios; 24 seconds total
- Three positive persistent-evidence incidents
- Three negatives: transient evidence, sparse evidence, and no evidence
- Shared detector/tracker observations, zone logic, risk engine, and event matcher
- Frame baseline: one positive frame required
- Temporal system: three positive frames within 1.5 seconds
- Subgroups: evidence pattern, lighting condition, and occlusion condition

One command reproduces the full artifact bundle:

```sh
python -m security_ai.evaluation \
  services/ai/tests/fixtures/evaluation/manifest.json \
  --output-dir work/m5-controlled-study
```

## Results

| Variant | TP | FP | FN | Precision | Recall | F1 | Mean delay |
|---|---:|---:|---:|---:|---:|---:|---:|
| Frame baseline | 3 | 2 | 0 | 0.60 | 1.00 | 0.75 | 0 ms |
| Temporal system | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1,167 ms |

Both variants detected all three persistent events and produced no duplicate alerts. The
frame baseline also escalated transient and sparse noise. Temporal persistence removed
both controlled false alerts at the cost of approximately 1.17 seconds mean escalation
delay.

The extrapolated frame-baseline value of 300 false alerts per camera-hour is mathematically
correct for this 24-second suite but is not a deployment estimate. The suite deliberately
concentrates failure cases to verify semantics.

## Conclusion

The controlled result supports retaining three-frame persistence for the prototype. It
does not establish real-video precision or recall. After M6, the same manifest contract
and batch evaluator will be applied to image-ID-grouped annotated video with an untouched
test split.
