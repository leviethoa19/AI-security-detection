"""Build a provenance-preserving Open Images firearm evaluation manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FIREARM_CLASSES = {
    "/m/0gxl3": "Handgun",
    "/m/06c54": "Rifle",
    "/m/06nrc": "Shotgun",
}
WEAPON_CLASS_MID = "/m/083kb"


def build_manifest(
    *,
    boxes_csv: Path,
    labels_csv: Path,
    metadata_csv: Path,
    image_dir: Path,
    acquisition_date: str,
    max_positive_images: int,
    max_negative_images: int,
) -> dict[str, Any]:
    annotations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with boxes_csv.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            label = FIREARM_CLASSES.get(row["LabelName"])
            if label is None:
                continue
            annotations[row["ImageID"]].append(
                {
                    "label": label,
                    "classMid": row["LabelName"],
                    "boxNormalized": [
                        float(row["XMin"]),
                        float(row["YMin"]),
                        float(row["XMax"]),
                        float(row["YMax"]),
                    ],
                    "occluded": row["IsOccluded"] == "1",
                    "truncated": row["IsTruncated"] == "1",
                    "depiction": row["IsDepiction"] == "1",
                }
            )

    positive_ids = sorted(annotations)[:max_positive_images]
    negative_candidates: set[str] = set()
    with labels_csv.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["LabelName"] == WEAPON_CLASS_MID and row["Confidence"] == "0":
                negative_candidates.add(row["ImageID"])
    negative_ids = sorted(negative_candidates - set(annotations))[:max_negative_images]
    selected_ids = set(positive_ids) | set(negative_ids)

    metadata: dict[str, dict[str, str]] = {}
    with metadata_csv.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["ImageID"] in selected_ids:
                metadata[row["ImageID"]] = row

    items = [
        _manifest_item(
            image_id,
            image_dir=image_dir,
            metadata=metadata.get(image_id, {}),
            annotations=annotations.get(image_id, []),
        )
        for image_id in positive_ids + negative_ids
    ]
    return {
        "schemaVersion": "1.0",
        "dataset": "Open Images V7",
        "split": "validation",
        "acquisitionDate": acquisition_date,
        "annotationLicense": "CC BY 4.0",
        "annotationSource": "https://storage.googleapis.com/openimages/web/download_v7.html",
        "imageLicensePolicy": (
            "Each image is listed as CC BY 2.0 by Open Images; preserve and verify each "
            "item's license and attribution metadata before redistribution."
        ),
        "classMapping": FIREARM_CLASSES,
        "negativeClassMid": WEAPON_CLASS_MID,
        "items": items,
    }


def _manifest_item(
    image_id: str,
    *,
    image_dir: Path,
    metadata: dict[str, str],
    annotations: list[dict[str, Any]],
) -> dict[str, Any]:
    image_path = image_dir / f"{image_id}.jpg"
    return {
        "imageId": image_id,
        "imagePath": str(image_path),
        "splitGroup": image_id,
        "sourceUrl": metadata.get("OriginalURL"),
        "landingPageUrl": metadata.get("OriginalLandingURL"),
        "licenseUrl": metadata.get("License"),
        "author": metadata.get("Author"),
        "title": metadata.get("Title"),
        "sha256": _sha256(image_path) if image_path.exists() else None,
        "verifiedWeaponNegative": not annotations,
        "annotations": annotations,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Open Images firearm manifest")
    parser.add_argument("--boxes-csv", type=Path, required=True)
    parser.add_argument("--labels-csv", type=Path, required=True)
    parser.add_argument("--metadata-csv", type=Path, required=True)
    parser.add_argument("--image-dir", type=Path, required=True)
    parser.add_argument("--acquisition-date", required=True)
    parser.add_argument("--max-positive-images", type=int, default=50)
    parser.add_argument("--max-negative-images", type=int, default=50)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = build_manifest(
        boxes_csv=arguments.boxes_csv,
        labels_csv=arguments.labels_csv,
        metadata_csv=arguments.metadata_csv,
        image_dir=arguments.image_dir,
        acquisition_date=arguments.acquisition_date,
        max_positive_images=arguments.max_positive_images,
        max_negative_images=arguments.max_negative_images,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
