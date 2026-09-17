# M4 firearm-like baseline experiment

## Fixed inputs

- Model: `google/owlv2-base-patch16-ensemble`
- Model license: Apache 2.0
- Weight format: safetensors
- Weight size: approximately 620 MB
- Prompts: handgun, pistol, revolver, rifle, shotgun
- Dataset: bounded Open Images V7 validation subset
- Positive classes: Handgun, Rifle, Shotgun
- Hard negatives: human-verified negative Weapon labels
- Matching: greedy score order at IoU 0.50
- Threshold sweep: 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50

## Reproducibility rules

1. Preserve the official image ID as the split group.
2. Record source URL, landing page, author, license URL, annotation version, acquisition date, and SHA-256.
3. Do not commit pixels, weights, predictions, or reports containing private media.
4. Run inference once at the lowest threshold, then evaluate all operating thresholds from the same predictions.
5. Report positive and negative image counts plus mean and P95 latency.
6. Manually categorize false positives and false negatives before deciding on fine-tuning.

## Required outputs

- Machine-readable threshold table
- Selected operating threshold and rationale
- Precision, recall, F1, TP, FP, and FN at each threshold
- Mean and P95 inference latency
- Failure groups such as small object, occlusion, depiction, low light, confusing handheld object, and unassociated object
- Explicit `fine-tuning justified` or `fine-tuning not yet justified` conclusion

No numeric quality claim is made until the approved external artifacts are downloaded and the experiment is run.
