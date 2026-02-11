"""Object detection: optional GroundingDINO; disabled by default on CPU."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class DetectedObject:
    """Single detected object with label, confidence, and bbox (x1, y1, x2, y2)."""
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]


def detect_objects(
    image: np.ndarray,
    use_grounding_dino: bool = False,
) -> tuple[List[DetectedObject], str]:
    """Run object detection if enabled and weights present.
    Returns (list of DetectedObject, mode_used: 'grounding_dino' | 'none').
    """
    if use_grounding_dino:
        objs, ok = _grounding_dino_detect(image)
        if ok:
            return objs, "grounding_dino"
    return [], "none"


def _grounding_dino_detect(image: np.ndarray) -> tuple[List[DetectedObject], bool]:
    """Optional GroundingDINO; returns ([], False) if unavailable."""
    try:
        from app.ml.grounding_dino_wrapper import run_grounding_dino
        return run_grounding_dino(image)
    except Exception:
        return [], False
