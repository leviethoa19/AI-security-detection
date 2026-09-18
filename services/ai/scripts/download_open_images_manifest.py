"""Download only the Open Images pixels named by an approved manifest."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Download an Open Images manifest subset")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--workers", type=int, default=5)
    arguments = parser.parse_args()
    raw: dict[str, Any] = json.loads(arguments.manifest.read_text(encoding="utf-8"))

    def download(item: dict[str, Any]) -> str:
        image_id = str(item["imageId"])
        destination = (arguments.manifest.parent / str(item["imagePath"])).resolve()
        if destination.exists() and destination.stat().st_size > 0:
            return f"cached {image_id}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".jpg.part")
        url = f"https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg"
        with urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(destination)
        return f"downloaded {image_id} ({destination.stat().st_size} bytes)"

    with ThreadPoolExecutor(max_workers=arguments.workers) as executor:
        for result in executor.map(download, raw["items"]):
            print(result)


if __name__ == "__main__":
    main()
