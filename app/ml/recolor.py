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


def recolor_masked_region(
    image: np.ndarray,
    mask: np.ndarray,
    target_hex: str,
    strength: float = 0.8,
) -> np.ndarray:
    """Recolor only the masked region with the target color (direct RGB).
    Original alpha is unchanged. Rest of image is untouched.
    - image: (H, W, 3) or (H, W, 4) uint8.
    - mask: (H, W) float in [0, 1].
    - target_hex: e.g. '#FF0000' (or rgba(...) from Gradio).
    - strength: 0--1 blend toward target (1 = solid target color in mask).
    Returns same shape as image, uint8.
    """
    if image.ndim == 2:
        image = np.stack([image] * 3 + [np.full_like(image, 255)], axis=-1)
    if image.shape[-1] == 3:
        alpha = np.full((*image.shape[:2], 1), 255, dtype=np.uint8)
        image = np.concatenate([image, alpha], axis=-1)

    rgb = image[:, :, :3].astype(np.float64) / 255.0
    alpha_orig = image[:, :, 3].copy()
    h, w = rgb.shape[:2]

    # Target color in RGB [0, 1], shape (3,)
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

    # Direct RGB: in masked region, blend original toward target by strength
    mask_3 = np.stack([mask_float] * 3, axis=-1)
    target_bc = np.broadcast_to(target_rgb, (h, w, 3))
    painted_rgb = rgb * (1 - strength * mask_3) + target_bc * (strength * mask_3)
    out_rgb = rgb * (1 - mask_3) + painted_rgb * mask_3
    out_rgb = (np.clip(out_rgb, 0, 1) * 255).astype(np.uint8)

    out = np.concatenate([out_rgb, alpha_orig[:, :, np.newaxis]], axis=-1)
    return out.astype(np.uint8)
