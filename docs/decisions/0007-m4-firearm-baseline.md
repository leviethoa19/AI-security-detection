# ADR 0007: Firearm-like evidence baseline

- **Status:** Accepted as baseline; replacement training approved for M6
- **Date:** 2026-09-17

## Decision

Use `google/owlv2-base-patch16-ensemble` through Hugging Face Transformers as the first zero-shot firearm-like detector. Keep it behind a small adapter so Grounding DINO or a fine-tuned detector can replace it without changing tracking, temporal risk, or evaluation code.

Use only the Open Images V7 validation split for the first bounded evaluation subset. Map Handgun (`/m/0gxl3`), Rifle (`/m/06c54`), and Shotgun (`/m/06nrc`) to the product's single `firearm_like` evidence class. Use human-verified negative Weapon (`/m/083kb`) labels for hard negatives.

## Rationale

- OWLv2 is a text-conditioned PyTorch detector supported directly by Transformers.
- The selected model is Apache 2.0 and provides safetensors weights of approximately 620 MB.
- The adapter can prompt several firearm terms without pretending they are separate reliable product classes.
- Open Images provides official bounding boxes, verified negative labels, and subset download tooling.
- The bounded validation subset avoids claiming results from unverified web images or an undocumented community dataset.

## Safety and licensing constraints

- Outputs are named `firearm_like` and displayed as “potential firearm”; they are not certainty claims.
- Risk 4 requires persistent evidence associated with a tracked person inside an armed zone.
- A single positive frame cannot escalate an incident.
- Open Images annotations are CC BY 4.0. Images are listed as CC BY 2.0, but attribution and license metadata must be preserved and verified per image.
- Model weights, images, generated predictions, and evaluation artifacts remain outside Git.

## Measurement gate

This ADR selects what to measure, not a production model. The baseline is accepted only after the threshold sweep reports precision, recall, F1, latency, false-positive groups, and missed-object groups on the recorded manifest. Fine-tuning remains undecided until those errors are reviewed.

## Measurement outcome

The bounded experiment selected a confidence threshold of 0.40 after class-agnostic
NMS. It reached 0.718 precision, 0.670 recall, and 0.693 F1 at IoU 0.50 on 91
deduplicated firearm-like objects. At image level it detected evidence in 42 of 50
positive images and produced evidence in 1 of 50 verified-negative images.

This model remains a baseline rather than a production choice. Mean CPU inference was
24.0 seconds per image, and error review exposed weak small-object, occlusion, shotgun,
and localization behavior. M6 will therefore train or fine-tune a smaller supervised
detector with hard-negative mining. The present subset remains development evidence;
M6 must use image-ID-grouped training data and an untouched test split for final claims.
