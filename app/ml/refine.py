"""Mask refinement: morphological ops, feathering, and shadow expansion."""

from __future__ import annotations

import cv2
import numpy as np


def refine_mask(
    mask: np.ndarray,
    morph_kernel: int = 3,
    feather_px: float = 2.0,
    mask_threshold: float = 0.5,
) -> np.ndarray:
    """Refine a binary or soft mask with morphological close/open and Gaussian feather."""
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


def expand_mask_to_include_shadow(
    image: np.ndarray,
    mask: np.ndarray,
    dilation_px: int = 20,
    shadow_value_threshold: float = 0.5,
) -> np.ndarray:
    """Expand the object mask to include nearby dark pixels (cast shadow)."""
    if mask.ndim > 2:
        mask = mask.squeeze()
    mask_float = np.clip(np.asarray(mask, dtype=np.float64), 0, 1)
    h, w = mask_float.shape[:2]
    binary = (mask_float >= 0.5).astype(np.uint8) * 255

    k = max(3, min(51, int(dilation_px) * 2 + 1) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    dilated = cv2.dilate(binary, kernel)
    ring = np.clip(dilated.astype(np.int32) - binary.astype(np.int32), 0, 255).astype(np.uint8)

    rgb = image[:, :, :3] if image.shape[-1] >= 3 else image
    if rgb.ndim == 2:
        gray = rgb
    else:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    v = gray.astype(np.float64) / 255.0
    thresh = max(0.1, min(0.9, shadow_value_threshold))
    dark = (v <= thresh).astype(np.uint8) * 255
    shadow_mask = ((ring > 0) & (dark > 0)).astype(np.float64)
    combined = np.clip(mask_float + shadow_mask, 0, 1).astype(np.float32)
    return combined
