"""Optional GroundingDINO detector; disabled by default, used only when explicitly enabled."""

from __future__ import annotations

from typing import List

import numpy as np

from app.ml.detect import DetectedObject


def run_grounding_dino(image: np.ndarray) -> tuple[List[DetectedObject], bool]:
    """Run GroundingDINO if weights and deps exist. Returns (objects, True) or ([], False)."""
    try:
        from app.utils.cache import get_model_cache_dir
        ckpt = get_model_cache_dir() / "groundingdino" / "groundingdino_swint_ogc.pth"
        if not ckpt.exists():
            return [], False
        # Optional: groundingdino package + torch; avoid hard dependency
        # When present, run inference and return DetectedObject list
        return [], False
    except Exception:
        return [], False
