# Data workspace

Dataset contents are intentionally excluded from Git.

Future dataset manifests must record source, license, acquisition date, checksum, split group, scenario attributes, and annotation version. Splits should be grouped by source video or recording session to prevent adjacent-frame leakage.

Only licensed public data and consented controlled recordings may be used. Real weapons are neither required nor encouraged for controlled recordings.

## M4 firearm baseline

The approved public-data candidate is a bounded Open Images V7 validation subset:

- `/m/0gxl3` — Handgun
- `/m/06c54` — Rifle
- `/m/06nrc` — Shotgun
- `/m/083kb` — Weapon, used for human-verified negative examples

Open Images annotations are CC BY 4.0. Images are listed by Open Images as CC BY 2.0, but the project must preserve each image's author, source, landing page, and license URL and verify those fields before redistribution. Dataset pixels and downloaded metadata stay under ignored `data/raw/` or `data/interim/` paths.

`security-ai-open-images-manifest` converts the official box, image-label, and image-metadata CSV files into a deterministic evaluation manifest. It selects positive firearm boxes, reliable Weapon-negative images, attribution fields, split groups, and checksums without committing the images.
