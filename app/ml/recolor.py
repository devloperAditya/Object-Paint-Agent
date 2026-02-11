"""Recolor masked region using LAB; preserve luminance and original alpha."""

from __future__ import annotations

import re

import cv2
import numpy as np


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex string (e.g. '#FF0000') to (R, G, B) 0-255."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def parse_color_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert hex or CSS rgba(...) to (R, G, B) 0-255. Handles Gradio ColorPicker output."""
    if not value or not isinstance(value, str):
        return (255, 0, 0)  # fallback red
    s = value.strip()
    # Gradio sometimes sends "#rgba(r,g,b,a)" — strip leading # so rgba regex can match
    if s.startswith("#") and "rgba" in s.lower():
        s = s.lstrip("#").strip()
    # Hex: #RRGGBB or RRGGBB (exactly 6 hex chars)
    hex_part = s.lstrip("#") if s.startswith("#") else s
    if len(hex_part) == 6 and all(c in "0123456789abcdefABCDEF" for c in hex_part):
        return tuple(int(hex_part[i : i + 2], 16) for i in (0, 2, 4))
    # CSS rgba(r, g, b, a) or rgb(r, g, b)
    m = re.match(r"rgba?\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)", s)
    if m:
        r, g, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if r <= 1 and g <= 1 and b <= 1:
            r, g, b = r * 255, g * 255, b * 255
        return (int(round(min(255, max(0, r)))), int(round(min(255, max(0, g)))), int(round(min(255, max(0, b)))))
    try:
        return hex_to_rgb(s)
    except ValueError:
        return (255, 0, 0)


def _build_color_match_mask(
    image_rgb: np.ndarray,
    object_mask: np.ndarray,
    source_color_hex: str,
    hue_tolerance_degrees: float,
    min_saturation: int = 20,
    min_value: int = 20,
) -> np.ndarray:
    """Within object_mask, return a float mask [0,1] of pixels similar to source_color (HSV hue).
    Used to recolor only e.g. yellow body while keeping red beak.
    - hue_tolerance_degrees: hue range ± this (in 0-360 scale); OpenCV H is 0-180 so we use half.
    """
    bgr = (np.clip(image_rgb, 0, 1) * 255).astype(np.uint8)[:, :, ::-1]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0].astype(np.float64), hsv[:, :, 1], hsv[:, :, 2]

    r, g, b = parse_color_to_rgb(source_color_hex)
    src_bgr = np.array([[[b, g, r]]], dtype=np.uint8)
    src_hsv = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2HSV)
    h0 = float(src_hsv[0, 0, 0])
    # OpenCV H is 0-180; tolerance in degrees 0-360 -> half in 0-180
    tol = max(1.0, min(90.0, hue_tolerance_degrees)) / 2.0

    # Hue distance with wraparound (0-180 circle)
    d = np.abs(H - h0)
    hue_diff = np.minimum(d, 180.0 - d)
    hue_ok = (hue_diff <= tol).astype(np.float64)
    sat_ok = (S >= min_saturation).astype(np.float64)
    val_ok = (V >= min_value).astype(np.float64)
    color_mask = hue_ok * sat_ok * val_ok
    return np.clip(object_mask * color_mask, 0, 1).astype(np.float32)


def recolor_masked_region(
    image: np.ndarray,
    mask: np.ndarray,
    target_hex: str,
    strength: float = 0.8,
    source_color_hex: str | None = None,
    hue_tolerance_degrees: float = 25.0,
) -> np.ndarray:
    """Recolor only the masked region with the target color (direct RGB).
    If source_color_hex is set, only pixels within the mask that match that color
    (e.g. yellow) are recolored; other parts (e.g. red beak) stay unchanged.
    - source_color_hex: color in the object to replace (e.g. yellow #FFEB3B).
    - hue_tolerance_degrees: how close the pixel hue must be to source (e.g. 25).
    """
    if image.ndim == 2:
        image = np.stack([image] * 3 + [np.full_like(image, 255)], axis=-1)
    if image.shape[-1] == 3:
        alpha = np.full((*image.shape[:2], 1), 255, dtype=np.uint8)
        image = np.concatenate([image, alpha], axis=-1)

    rgb = image[:, :, :3].astype(np.float64) / 255.0
    alpha_orig = image[:, :, 3].copy()
    h, w = rgb.shape[:2]

    target_rgb = np.array(parse_color_to_rgb(target_hex), dtype=np.float64) / 255.0
    target_rgb = np.clip(target_rgb, 0, 1)

    mask_float = np.asarray(mask, dtype=np.float64)
    if mask_float.ndim > 2:
        mask_float = mask_float.squeeze()
    if mask_float.ndim == 1:
        if mask_float.size == h * w:
            mask_float = mask_float.reshape(h, w)
        else:
            mask_float = np.zeros((h, w), dtype=np.float64)
    if mask_float.shape[0] != h or mask_float.shape[1] != w:
        mask_float = cv2.resize(
            mask_float,
            (w, h),
            interpolation=cv2.INTER_LINEAR,
        )
    if mask_float.size > 0 and mask_float.max() > 1.5:
        mask_float = mask_float / 255.0
    mask_float = np.clip(mask_float, 0, 1)

    # Optionally restrict to pixels matching a source color (e.g. only yellow in the duck)
    if source_color_hex:
        mask_float = _build_color_match_mask(
            rgb,
            mask_float,
            source_color_hex,
            hue_tolerance_degrees=hue_tolerance_degrees,
        )

    mask_3 = np.stack([mask_float] * 3, axis=-1)
    target_bc = np.broadcast_to(target_rgb, (h, w, 3))
    painted_rgb = rgb * (1 - strength * mask_3) + target_bc * (strength * mask_3)
    out_rgb = rgb * (1 - mask_3) + painted_rgb * mask_3
    out_rgb = (np.clip(out_rgb, 0, 1) * 255).astype(np.uint8)

    out = np.concatenate([out_rgb, alpha_orig[:, :, np.newaxis]], axis=-1)
    return out.astype(np.uint8)
