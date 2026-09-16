"""Detector adapters with model-neutral outputs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import cv2
import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor, nn
from torchvision.models.detection import (  # type: ignore[import-untyped]
    FasterRCNN_MobileNet_V3_Large_320_FPN_Weights,
    SSDLite320_MobileNet_V3_Large_Weights,
    fasterrcnn_mobilenet_v3_large_320_fpn,
    ssdlite320_mobilenet_v3_large,
)

from security_ai.domain import BoundingBox, Detection

SUPPORTED_MODELS = ("ssdlite320", "fasterrcnn_mobilenet_320")


class PersonDetector(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def device_name(self) -> str: ...

    def detect(self, frame: NDArray[np.uint8]) -> tuple[Detection, ...]: ...


class TorchvisionPersonDetector:
    """COCO person detector backed by an official Torchvision model."""

    def __init__(
        self,
        model_name: str = "ssdlite320",
        *,
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be in [0, 1]")
        self._model_name = model_name
        self._confidence_threshold = confidence_threshold
        self._device = _resolve_device(device)
        self._model, self._transform = self._load_model(model_name)
        self._model.to(self._device).eval()

    @property
    def version(self) -> str:
        return f"torchvision-{self._model_name}"

    @property
    def device_name(self) -> str:
        return str(self._device)

    def detect(self, frame: NDArray[np.uint8]) -> tuple[Detection, ...]:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("expected a BGR frame with shape (height, width, 3)")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1)
        image = self._transform(tensor).to(self._device)
        with torch.inference_mode():
            raw = self._model([image])[0]

        detections: list[Detection] = []
        for box, label, score in zip(raw["boxes"], raw["labels"], raw["scores"], strict=True):
            numeric_score = float(score.item())
            if numeric_score < self._confidence_threshold or int(label.item()) != 1:
                continue
            x1, y1, x2, y2 = (float(value) for value in box.tolist())
            detections.append(
                Detection(
                    box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    score=numeric_score,
                )
            )
        return tuple(detections)

    @staticmethod
    def _load_model(model_name: str) -> tuple[nn.Module, Callable[[Tensor], Tensor]]:
        if model_name == "ssdlite320":
            weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
            return ssdlite320_mobilenet_v3_large(weights=weights), weights.transforms()
        if model_name == "fasterrcnn_mobilenet_320":
            weights = FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT
            return fasterrcnn_mobilenet_v3_large_320_fpn(weights=weights), weights.transforms()
        supported = ", ".join(SUPPORTED_MODELS)
        raise ValueError(f"unsupported model {model_name!r}; choose one of: {supported}")


def _resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is not available")
    if requested not in {"cpu", "cuda"}:
        raise ValueError("device must be one of: auto, cpu, cuda")
    return torch.device(requested)
