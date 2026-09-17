from __future__ import annotations

from pathlib import Path

from security_ai.open_images import build_manifest


def test_manifest_preserves_class_mapping_negatives_and_provenance(tmp_path: Path) -> None:
    boxes = tmp_path / "boxes.csv"
    labels = tmp_path / "labels.csv"
    metadata = tmp_path / "metadata.csv"
    boxes.write_text(
        "ImageID,LabelName,XMin,YMin,XMax,YMax,IsOccluded,IsTruncated,IsDepiction\n"
        "positive,/m/0gxl3,0.1,0.2,0.3,0.4,0,1,0\n",
        encoding="utf-8",
    )
    labels.write_text(
        "ImageID,LabelName,Confidence\nnegative,/m/083kb,0\n",
        encoding="utf-8",
    )
    metadata.write_text(
        "ImageID,OriginalURL,OriginalLandingURL,License,Author,Title\n"
        "positive,https://images/positive,https://pages/positive,https://license,Ada,One\n"
        "negative,https://images/negative,https://pages/negative,https://license,Lin,Two\n",
        encoding="utf-8",
    )

    manifest = build_manifest(
        boxes_csv=boxes,
        labels_csv=labels,
        metadata_csv=metadata,
        image_dir=Path("raw/open-images-v7/validation"),
        acquisition_date="2026-09-17",
        max_positive_images=10,
        max_negative_images=10,
    )

    assert [item["imageId"] for item in manifest["items"]] == ["positive", "negative"]
    assert manifest["items"][0]["annotations"][0]["label"] == "Handgun"
    assert manifest["items"][0]["annotations"][0]["truncated"] is True
    assert manifest["items"][1]["verifiedWeaponNegative"] is True
    assert manifest["items"][1]["author"] == "Lin"
