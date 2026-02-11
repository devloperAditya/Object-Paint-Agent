"""Mask refinement: morphological ops and feathering."""

from __future__ import annotations

import cv2
import numpy as np


def refine_mask(
    mask: np.ndarray,
    morph_kernel: int = 3,
    feather_px: float = 2.0,
    mask_threshold: float = 0.5,
) -> np.ndarray:
    """Refine a binary or soft mask with morphological close/open and Gaussian feather.
    - morph_kernel: odd int 1--9 for open/close.
    - feather_px: Gaussian blur sigma (0 = no feather).
    - mask_threshold: binarize soft mask at this value (0--1).
    Returns float mask in [0, 1] with same shape as input.
    """
    if mask.ndim > 2:
        mask = mask.squeeze()
    if mask.dtype != np.uint8:
        binary = (np.asarray(mask, dtype=np.float64) >= mask_threshold).astype(np.uint8) * 255
    else:
        binary = (mask >= int(255 * mask_threshold)).astype(np.uint8) * 255

    k = max(1, morph_kernel if morph_kernel % 2 == 1 else morph_kernel + 1)
    k = min(9, k)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    if feather_px > 0:
        sigma = max(0.5, feather_px)
        ksize = int(6 * sigma + 1) | 1
        ksize = min(ksize, min(binary.shape[:2]) | 1)
        blurred = cv2.GaussianBlur(binary.astype(np.float32) / 255.0, (ksize, ksize), sigma)
        return np.clip(blurred, 0, 1).astype(np.float32)

    return (binary.astype(np.float32) / 255.0).astype(np.float32)
