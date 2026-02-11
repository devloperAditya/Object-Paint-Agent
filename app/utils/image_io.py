"""Image I/O with RGBA preservation and size limits."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


def get_image_size(image: np.ndarray) -> Tuple[int, int]:
    """Return (height, width) of image."""
    h, w = image.shape[:2]
    return (int(h), int(w))


def ensure_rgba(image: np.ndarray) -> np.ndarray:
    """Convert to RGBA if needed; preserve existing alpha."""
    if image.ndim == 2:
        out = np.stack([image, image, image, np.full_like(image, 255)], axis=-1)
        return out.astype(np.uint8)
    if image.shape[-1] == 3:
        alpha = np.full((*image.shape[:2], 1), 255, dtype=image.dtype)
        out = np.concatenate([image, alpha], axis=-1)
        return out.astype(np.uint8)
    return image.astype(np.uint8)


def load_image(
    path: str | Path,
    max_size: int = 1024,
    preserve_alpha: bool = True,
) -> np.ndarray:
    """Load image from path; optionally resize; return RGBA uint8 array (H, W, 4)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    pil = Image.open(path).convert("RGBA" if preserve_alpha else "RGB")
    arr = np.array(pil)

    if preserve_alpha and arr.shape[-1] == 3:
        arr = ensure_rgba(arr)

    h, w = arr.shape[:2]
    if max_size > 0 and (h > max_size or w > max_size):
        scale = min(max_size / h, max_size / w)
        new_w, new_h = int(w * scale), int(h * scale)
        pil_resized = pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        arr = np.array(pil_resized)

    return ensure_rgba(arr)


def save_image(image: np.ndarray, path: str | Path) -> None:
    """Save image as PNG; preserve alpha. Expects (H, W, 3) or (H, W, 4) uint8."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if image.ndim == 2:
        image = ensure_rgba(image)
    elif image.shape[-1] == 3:
        image = ensure_rgba(image)
    pil = Image.fromarray(image.astype(np.uint8))
    pil.save(path, format="PNG")


def resize_for_processing(image: np.ndarray, max_size: int) -> np.ndarray:
    """Resize image so that max dimension is <= max_size; preserve aspect and alpha."""
    h, w = image.shape[:2]
    if max_size <= 0 or (h <= max_size and w <= max_size):
        return image
    scale = min(max_size / h, max_size / w)
    new_w, new_h = int(w * scale), int(h * scale)
    pil = Image.fromarray(image.astype(np.uint8))
    pil = pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return np.array(pil)
