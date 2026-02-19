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
) -> tuple[List[DetectedObject], str, str | None]:
    """Run object detection if enabled and weights present.
    Returns (list of DetectedObject, mode_used: 'grounding_dino' | 'none', error_message or None).
    """
    if use_grounding_dino:
        objs, ok, err = _grounding_dino_detect(image)
        if ok:
            return objs, "grounding_dino", None
        return [], "none", err
    return [], "none", None


def _grounding_dino_detect(image: np.ndarray) -> tuple[List[DetectedObject], bool, str | None]:
    """Optional GroundingDINO; returns ([], False, error_message) if unavailable."""
    try:
        from app.ml.grounding_dino_wrapper import run_grounding_dino
        objs, ok, err = run_grounding_dino(image)
        return objs, ok, err
    except Exception as e:
        import traceback
        traceback.print_exc()
        return [], False, str(e)
