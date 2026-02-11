#!/usr/bin/env python3
"""Sample run: create a tiny test image and run pipeline (GrabCut path, no weights)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.recolor import recolor_masked_region
from app.ml.refine import refine_mask
from app.ml.segment import segment_from_points
from app.utils.image_io import ensure_rgba, save_image


def main():
    # Tiny 32x32 RGBA image
    h, w = 32, 32
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, :3] = 128
    img[:, :, 3] = 255
    # Simple "object": center rectangle
    img[8:24, 8:24, :3] = 200
    img = ensure_rgba(img)

    # Points: foreground in center, background at corners
    fg_points = [(16, 16)]
    bg_points = [(2, 2), (30, 2), (2, 30), (30, 30)]

    mask, mode = segment_from_points(img, fg_points, bg_points, use_sam=False)
    assert mode == "grabcut"
    mask = refine_mask(mask, morph_kernel=3, feather_px=1.0, mask_threshold=0.5)
    out = recolor_masked_region(img, mask, "#FF0000", strength=0.8)

    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_image(out, out_dir / "sample_run_output.png")
    print("Sample run OK: data/sample_run_output.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
