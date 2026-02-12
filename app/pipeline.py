"""End-to-end pipeline: load -> detect/select -> segment -> refine -> recolor -> export."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.detect import DetectedObject, detect_objects
from app.ml.recolor import recolor_masked_region
from app.ml.refine import expand_mask_to_include_shadow, refine_mask
from app.ml.segment import segment_from_rect
from app.utils.bbox import draw_bbox_overlay
from app.utils.image_io import ensure_rgba, get_image_size, save_image


def run_detection(image: np.ndarray, use_grounding_dino: bool) -> tuple[list[DetectedObject], str]:
    """Run detector; return (objects, mode)."""
    return detect_objects(image, use_grounding_dino=use_grounding_dino)


def run_segment_rect(
    image: np.ndarray,
    left_pct: float,
    top_pct: float,
    right_pct: float,
    bottom_pct: float,
) -> tuple[np.ndarray, str]:
    """Segment from bounding box (percent 0-100); return (mask, mode)."""
    return segment_from_rect(image, left_pct, top_pct, right_pct, bottom_pct)


def run_refine(
    mask: np.ndarray,
    morph_kernel: int,
    feather_px: float,
    mask_threshold: float,
) -> np.ndarray:
    """Refine mask; return float mask [0,1]."""
    return refine_mask(mask, morph_kernel, feather_px, mask_threshold)


def run_expand_mask_shadow(
    image: np.ndarray,
    mask: np.ndarray,
    dilation_px: int = 20,
    shadow_value_threshold: float = 0.5,
) -> np.ndarray:
    """Expand mask to include nearby dark pixels (cast shadow)."""
    return expand_mask_to_include_shadow(
        image, mask,
        dilation_px=dilation_px,
        shadow_value_threshold=shadow_value_threshold,
    )


def run_recolor(
    image: np.ndarray,
    mask: np.ndarray,
    target_hex: str,
    strength: float,
    source_color_hex: str | None = None,
    hue_tolerance_degrees: float = 25.0,
) -> np.ndarray:
    """Recolor masked region; optionally only where pixel color matches source_color_hex."""
    return recolor_masked_region(
        image,
        mask,
        target_hex,
        strength=strength,
        source_color_hex=source_color_hex,
        hue_tolerance_degrees=hue_tolerance_degrees,
    )


def build_metadata(
    selected_object: str | None,
    color_hex: str,
    mode_detect: str,
    mode_segment: str,
    timings: dict[str, float],
) -> dict[str, Any]:
    """Build export metadata JSON."""
    return {
        "selected_object": selected_object,
        "color_hex": color_hex,
        "detection_mode": mode_detect,
        "segmentation_mode": mode_segment,
        "timings_seconds": timings,
    }


def export_outputs(
    painted: np.ndarray,
    mask: np.ndarray,
    metadata: dict[str, Any],
    out_dir: Path,
    base_name: str = "output",
) -> tuple[Path, Path, Path]:
    """Save painted PNG, mask PNG, and metadata JSON."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    painted_path = out_dir / f"{base_name}_painted.png"
    mask_path = out_dir / f"{base_name}_mask.png"
    meta_path = out_dir / f"{base_name}_metadata.json"
    save_image(painted, painted_path)
    mask_uint8 = (np.clip(mask, 0, 1) * 255).astype(np.uint8)
    save_image(ensure_rgba(np.stack([mask_uint8] * 3 + [mask_uint8], axis=-1)), mask_path)
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    return (painted_path, mask_path, meta_path)


def get_image_with_bbox_overlay(
    image: np.ndarray,
    objects: list[DetectedObject],
    highlight_index: int | None,
) -> np.ndarray:
    """Return image with bboxes drawn; highlight selected object."""
    if not objects:
        return image
    boxes = [obj.bbox for obj in objects]
    labels = [f"{obj.label} ({obj.confidence:.2f})" for obj in objects]
    return draw_bbox_overlay(image, boxes, labels=labels, highlight_index=highlight_index)
