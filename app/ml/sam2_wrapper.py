"""Optional SAM2 predictor; lazy load and only if weights exist."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

_sam2_predictor = None


def _get_sam2_predictor():
    global _sam2_predictor
    if _sam2_predictor is not None:
        return _sam2_predictor
    from app.utils.cache import get_model_cache_dir
    import os
    checkpoint = get_model_cache_dir() / "sam2" / "sam2_hiera_tiny.pt"
    if not checkpoint.exists():
        return None
    try:
        # Optional: segment-anything-2 or similar; keep import inside to avoid hard dep
        from segment_anything import sam_model_registry, SamPredictor
        import torch
        model = sam_model_registry["vit_t"](checkpoint=str(checkpoint))
        model.eval()
        _sam2_predictor = SamPredictor(model)
        return _sam2_predictor
    except Exception:
        return None


def sam2_predict_from_points(
    image: np.ndarray,
    fg_points: List[Tuple[int, int]],
    bg_points: List[Tuple[int, int]],
) -> np.ndarray | None:
    """Run SAM predictor with point prompts. Returns mask [0,1] or None if unavailable."""
    predictor = _get_sam2_predictor()
    if predictor is None:
        return None
    try:
        import torch
        rgb = image[:, :, :3] if image.shape[-1] >= 3 else image
        predictor.set_image(rgb)
        coords = np.array([(x, y) for (y, x) in fg_points] + [(x, y) for (y, x) in bg_points], dtype=np.int32)
        labels = np.array([1] * len(fg_points) + [0] * len(bg_points), dtype=np.int32)
        masks, _, _ = predictor.predict(point_coords=coords, point_labels=labels, multimask_output=False)
        mask = masks[0].astype(np.float32)
        return mask
    except Exception:
        return None
