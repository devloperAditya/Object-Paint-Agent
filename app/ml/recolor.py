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
    # Hex: #RRGGBB or RRGGBB (6 hex chars); or 8-char #RRGGBBAA / #AARRGGBB — use first 6 as RRGGBB
    hex_part = s.lstrip("#") if s.startswith("#") else s
    if len(hex_part) >= 6 and all(c in "0123456789abcdefABCDEF" for c in hex_part[:6]):
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
    min_saturation: int = 0,
    min_value: int = 0,
) -> np.ndarray:
    """Within object_mask, return a float mask [0,1] of pixels similar to source_color (HSV hue).
    Uses min_saturation=0, min_value=0 so shaded and cast-shadow areas are included when hue matches.
    """
    bgr = (np.clip(image_rgb, 0, 1) * 255).astype(np.uint8)[:, :, ::-1]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0].astype(np.float64), hsv[:, :, 1], hsv[:, :, 2]

    r, g, b = parse_color_to_rgb(source_color_hex)
    src_bgr = np.array([[[b, g, r]]], dtype=np.uint8)
    src_hsv = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2HSV)
    h0 = float(src_hsv[0, 0, 0])
    tol = max(1.0, min(90.0, hue_tolerance_degrees))

    d = np.abs(H - h0)
    hue_diff = np.minimum(d, 180.0 - d)
    # Full 1.0 inside tol*1.2 so main object is uniformly recolored; soft falloff only at outer edge (reduces patchiness)
    full_zone = tol * 1.2
    falloff_end = tol * 1.8
    hue_ok = np.where(hue_diff <= full_zone, 1.0, np.clip(1.0 - (hue_diff - full_zone) / (falloff_end - full_zone), 0.0, 1.0))
    sat_ok = (S >= min_saturation).astype(np.float64)
    val_ok = (V >= min_value).astype(np.float64)
    color_mask = hue_ok * sat_ok * val_ok
    # Include very dark pixels (cast shadow) in the mask so shadow gets recolored when "Include shadow" is on
    shadow_v_threshold = 35
    in_shadow = (V.astype(np.float64) < shadow_v_threshold) * object_mask
    color_mask = np.clip(color_mask + in_shadow, 0, 1)
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

    # Explicit R,G,B 0-255 from parser so channel order is never wrong
    r_t, g_t, b_t = parse_color_to_rgb(target_hex)
    target_rgb = np.array([r_t, g_t, b_t], dtype=np.float64) / 255.0
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

    # Where mask is strong, use full recolor to avoid patchy blend; only soften at edges
    mask_full = np.where(mask_float >= 0.5, 1.0, mask_float * 2.0)
    mask_float = np.clip(mask_full, 0, 1)

    # Use HSV and preserve original Value (brightness) so shaded parts get the target hue but stay dark
    bgr = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)[:, :, ::-1]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    H_orig = hsv[:, :, 0].astype(np.float64)
    S_orig = hsv[:, :, 1].astype(np.float64)
    V_orig = hsv[:, :, 2].astype(np.float64)

    # Single-pixel BGR for OpenCV: use explicit R,G,B so hue is correct (red -> H≈0, not yellow H≈30)
    target_bgr = np.array([[[b_t, g_t, r_t]]], dtype=np.uint8)
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)
    H_t = float(target_hsv[0, 0, 0])
    S_t = float(target_hsv[0, 0, 1])
    # V_t not used; we keep original V to preserve shading

    # Hue is circular (0 and 179 both red); interpolate along shortest path
    hue_diff = H_t - H_orig
    hue_diff = np.where(hue_diff > 89.5, hue_diff - 180.0, hue_diff)
    hue_diff = np.where(hue_diff < -89.5, hue_diff + 180.0, hue_diff)
    # Shift hue fully to paint color; wrap to [0,179] so gray/silver (H≈0) → blue doesn't clip to red
    new_H = (H_orig + hue_diff * mask_float + 180.0) % 180.0
    new_H = np.clip(new_H, 0, 179)
    new_S = S_orig + (S_t - S_orig) * strength * mask_float
    # Keep original brightness; lift only cast shadow (V very low) so paint is visible, not object shading (slots/edges)
    shadow_v_lift_threshold = 18.0
    min_v_visible = 28.0
    new_V = np.where(
        (mask_float > 0.1) & (V_orig < shadow_v_lift_threshold),
        np.maximum(V_orig, min_v_visible * mask_float),
        V_orig,
    )

    new_hsv = np.stack([np.clip(new_H, 0, 179), np.clip(new_S, 0, 255), np.clip(new_V, 0, 255)], axis=-1).astype(np.uint8)
    new_bgr = cv2.cvtColor(new_hsv, cv2.COLOR_HSV2BGR)
    painted_rgb = (new_bgr[:, :, ::-1].astype(np.float64) / 255.0)

    mask_3 = np.stack([mask_float] * 3, axis=-1)
    out_rgb = rgb * (1 - mask_3) + painted_rgb * mask_3
    out_rgb = (np.clip(out_rgb, 0, 1) * 255).astype(np.uint8)

    out = np.concatenate([out_rgb, alpha_orig[:, :, np.newaxis]], axis=-1)
    return out.astype(np.uint8)
