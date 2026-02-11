"""Segmentation: SAM2 (if weights) or GrabCut from user points."""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np


def _grabcut_from_points(
    image: np.ndarray,
    fg_points: List[Tuple[int, int]],
    bg_points: List[Tuple[int, int]],
    seed_radius: int = 5,
) -> np.ndarray:
    """Run GrabCut with foreground/background point seeds. Returns float mask [0, 1].
    Each point is expanded to a small circle (seed_radius) so GrabCut has enough seed area.
    """
    h, w = image.shape[:2]
    mask = np.full((h, w), cv2.GC_BGD, dtype=np.uint8)
    r = max(1, seed_radius)

    for py, px in fg_points:
        if 0 <= px < w and 0 <= py < h:
            y0, y1 = max(0, py - r), min(h, py + r + 1)
            x0, x1 = max(0, px - r), min(w, px + r + 1)
            mask[y0:y1, x0:x1] = cv2.GC_FGD
    for py, px in bg_points:
        if 0 <= px < w and 0 <= py < h:
            y0, y1 = max(0, py - r), min(h, py + r + 1)
            x0, x1 = max(0, px - r), min(w, px + r + 1)
            mask[y0:y1, x0:x1] = cv2.GC_BGD

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    rgb = image[:, :, :3] if image.shape[-1] >= 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.grabCut(rgb, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    out = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    return out


def _sam2_from_points(
    image: np.ndarray,
    fg_points: List[Tuple[int, int]],
    bg_points: List[Tuple[int, int]],
) -> np.ndarray | None:
    """If SAM2 is available and weights are present, run predictor and return mask; else None."""
    try:
        from app.ml.sam2_wrapper import sam2_predict_from_points
        return sam2_predict_from_points(image, fg_points, bg_points)
    except Exception:
        return None


def segment_from_points(
    image: np.ndarray,
    fg_points: List[Tuple[int, int]],
    bg_points: List[Tuple[int, int]],
    use_sam: bool = True,
) -> tuple[np.ndarray, str]:
    """Segment object from foreground/background points.
    Returns (mask float [0,1], mode_used: 'sam2' | 'grabcut').
    """
    if use_sam:
        sam_mask = _sam2_from_points(image, fg_points, bg_points)
        if sam_mask is not None:
            return sam_mask, "sam2"
    return _grabcut_from_points(image, fg_points, bg_points), "grabcut"


def _grabcut_from_rect(
    image: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
) -> np.ndarray:
    """Run GrabCut with a bounding box (rect). Returns float mask [0, 1]."""
    img_h, img_w = image.shape[:2]
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x))
    h = max(1, min(h, img_h - y))
    rect = (x, y, w, h)
    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    rgb = image[:, :, :3] if image.shape[-1] >= 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.grabCut(rgb, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    out = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    return out


def segment_from_rect(
    image: np.ndarray,
    left_pct: float,
    top_pct: float,
    right_pct: float,
    bottom_pct: float,
) -> tuple[np.ndarray, str]:
    """Segment using a bounding box as percentages (0-100). Returns (mask, 'grabcut_rect')."""
    h, w = image.shape[:2]
    x = int(round(left_pct / 100.0 * w))
    y = int(round(top_pct / 100.0 * h))
    x2 = int(round(right_pct / 100.0 * w))
    y2 = int(round(bottom_pct / 100.0 * h))
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    x2 = max(x + 1, min(x2, w))
    y2 = max(y + 1, min(y2, h))
    box_w = x2 - x
    box_h = y2 - y
    mask = _grabcut_from_rect(image, x, y, box_w, box_h)
    return mask, "grabcut_rect"
