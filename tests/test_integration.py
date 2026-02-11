"""Integration test: full pipeline on tiny image with GrabCut (no external weights)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ml.recolor import recolor_masked_region
from app.ml.refine import refine_mask
from app.ml.segment import segment_from_points
from app.utils.image_io import ensure_rgba, save_image


def test_pipeline_grabcut_tiny_image(tmp_path):
    """Run detect/segment/refine/recolor on a tiny image without any model weights."""
    h, w = 40, 40
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, :3] = 100
    img[:, :, 3] = 255
    img[10:30, 10:30, :3] = 180  # "object" in center
    img = ensure_rgba(img)

    fg_points = [(20, 20)]
    bg_points = [(2, 2), (38, 38)]

    mask, mode = segment_from_points(img, fg_points, bg_points, use_sam=False)
    assert mode == "grabcut"
    assert mask.shape == (h, w)
    assert mask.min() >= 0 and mask.max() <= 1

    refined = refine_mask(mask, morph_kernel=3, feather_px=1.0, mask_threshold=0.5)
    assert refined.shape == (h, w)

    painted = recolor_masked_region(img, refined, "#FF0000", strength=0.8)
    assert painted.shape == img.shape
    assert painted.dtype == np.uint8
    # Alpha unchanged
    np.testing.assert_array_equal(painted[:, :, 3], img[:, :, 3])

    save_image(painted, tmp_path / "painted.png")
    assert (tmp_path / "painted.png").exists()
