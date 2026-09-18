# M4 firearm-like baseline results

## Outcome

The zero-shot OWLv2 model is useful as a measured integration baseline, but it is too
slow and not accurate enough to be the final detector. Confidence 0.40 is the selected
prototype operating point. Supervised fine-tuning with hard-negative mining is justified
for M6.

## Reproducible setup

- Model: `google/owlv2-base-patch16-ensemble`, Apache-2.0 safetensors
- Prompts: handgun, pistol, revolver, rifle, shotgun
- Data: Open Images V7 validation, acquired 2026-09-17
- Sample: 50 positive images and 50 human-verified Weapon-negative images
- Source annotations: 112 boxes; 91 objects after IoU 0.90 deduplication for the unified
  `firearm_like` class
- Prediction post-processing: class-agnostic NMS at IoU 0.50
- Matching: greedy score order at IoU 0.50
- Runtime: PyTorch 2.13.0 CPU build, no CUDA
- Data integrity: 100/100 images readable, with per-image SHA-256 and license metadata

Images, model weights, metadata files, manifests, and raw predictions remain in ignored
local directories. They are not committed to Git.

## Threshold sweep

| Confidence | TP | FP | FN | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.05 | 83 | 1,580 | 8 | 0.050 | 0.912 | 0.095 |
| 0.10 | 81 | 643 | 10 | 0.112 | 0.890 | 0.199 |
| 0.15 | 77 | 345 | 14 | 0.182 | 0.846 | 0.300 |
| 0.20 | 74 | 208 | 17 | 0.262 | 0.813 | 0.397 |
| 0.30 | 70 | 77 | 21 | 0.476 | 0.769 | 0.588 |
| **0.40** | **61** | **24** | **30** | **0.718** | **0.670** | **0.693** |
| 0.50 | 40 | 5 | 51 | 0.889 | 0.440 | 0.588 |

Threshold 0.40 maximizes F1 in the fixed sweep. At image level, it detects at least one
object in 42/50 positive images (84%) and produces detections in 1/50 verified-negative
images (2%). Threshold 0.50 removes detections from all 50 negative images, but positive
image coverage falls to 27/50 (54%). The prototype therefore uses 0.40 and relies on the
existing person association, armed-zone context, and three-frame temporal persistence to
prevent one uncertain frame from creating a Risk 4 incident.

Mean inference latency was 24.04 seconds per image and P95 was 26.59 seconds. These are
end-to-end detector measurements from the local CPU run, not general hardware claims.

## Error analysis at confidence 0.40

- Small objects were the clearest miss group: 1/7 objects occupying less than 1% of the
  image were matched (14%). Medium objects reached 20/26 (77%), and large objects 40/58
  (69%).
- Occluded objects reached 12/23 (52%) versus 49/68 (72%) for non-occluded objects.
- Source labels retained after unified-box deduplication reached 12/12 for Handgun,
  43/66 for Rifle, and 6/13 for Shotgun. This class breakdown is directional because
  overlapping Rifle/Shotgun annotations are collapsed into one product class.
- The eight fully missed positive images included toy/depiction scenes, long weapons with
  fragmented or poorly aligned boxes, small weapons, and weapons partly occluded by a
  person or surrounding equipment.
- The only verified-negative image with a detection contained a dark rectangular
  chest-mounted accessory on a person in camouflage, a useful hard-negative pattern.
- Most remaining object-level false positives occurred inside positive images: multiple
  partially overlapping hypotheses or poorly localized weapon parts failed the IoU match.

## Decision and limitations

M6 fine-tuning is justified. It should train a smaller supervised detector on an
image-ID-grouped training split, add hard negatives such as radios, tools, toy weapons,
and dark handheld objects, and emphasize small and occluded examples. Quantization or a
smaller backbone must also be benchmarked because the zero-shot CPU latency is unsuitable
for video.

This 100-image subset was used to choose the threshold, so it is development evidence—not
an untouched final test set. M6 must preserve a separate test split before making any
generalization claim. Open Images labels can be incomplete or hierarchical, and the
verified-negative set does not represent every indoor false-alarm condition. Temporal
incident precision must still be measured on video after the detector is improved.
