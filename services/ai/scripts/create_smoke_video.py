"""Create a deterministic short video from one permitted pedestrian image."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--fps", type=float, default=10.0)
    arguments = parser.parse_args()

    image = cv2.imread(str(arguments.image))
    if image is None:
        raise ValueError(f"could not read image: {arguments.image}")
    height, width = image.shape[:2]
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(arguments.output),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        arguments.fps,
        (width, height),
    )
    if not writer.isOpened():
        raise ValueError(f"could not create video: {arguments.output}")
    try:
        for index in range(arguments.frames):
            offset = round(6 * np.sin(index / arguments.frames * 2 * np.pi))
            transform = np.float32([[1, 0, offset], [0, 1, 0]])
            frame = cv2.warpAffine(image, transform, (width, height), borderMode=cv2.BORDER_REFLECT)
            writer.write(frame)
    finally:
        writer.release()


if __name__ == "__main__":
    main()
