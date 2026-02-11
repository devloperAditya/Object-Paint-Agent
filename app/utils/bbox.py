"""Bounding box overlay drawing on images."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def draw_bbox_overlay(
    image: np.ndarray,
    boxes: List[Tuple[float, float, float, float]],
    labels: List[str] | None = None,
    highlight_index: int | None = None,
    color_highlight: Tuple[int, int, int] = (0, 255, 0),
    color_default: Tuple[int, int, int] = (255, 200, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Draw bounding boxes on a copy of the image. Boxes are (x1, y1, x2, y2) in pixels.
    If highlight_index is set, that box is drawn with color_highlight; others with color_default.
    """
    import cv2

    out = np.ascontiguousarray(np.asarray(image, dtype=np.uint8).copy())
    if out.shape[-1] == 4:
        canvas = np.ascontiguousarray(out[:, :, :3].copy())
    else:
        canvas = np.ascontiguousarray(out.copy())

    for i, (x1, y1, x2, y2) in enumerate(boxes):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        color = color_highlight if (highlight_index is not None and i == highlight_index) else color_default
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        if labels and i < len(labels):
            cv2.putText(
                canvas,
                labels[i],
                (x1, max(y1 - 5, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
    if out.shape[-1] == 4:
        out[:, :, :3] = canvas
    else:
        out[:] = canvas
    return out


def draw_rect_overlay(
    image: np.ndarray,
    left_pct: float,
    top_pct: float,
    right_pct: float,
    bottom_pct: float,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 3,
) -> np.ndarray:
    """Draw a single rectangle on a copy of the image. Coords as percentage 0-100."""
    import cv2

    # Ensure contiguous layout for OpenCV (PIL-loaded arrays can be non-contiguous)
    out = np.ascontiguousarray(np.asarray(image, dtype=np.uint8).copy())
    h, w = out.shape[:2]
    x1 = int(round(left_pct / 100.0 * w))
    y1 = int(round(top_pct / 100.0 * h))
    x2 = int(round(right_pct / 100.0 * w))
    y2 = int(round(bottom_pct / 100.0 * h))
    x1, x2 = max(0, min(x1, w)), max(0, min(x2, w))
    y1, y2 = max(0, min(y1, h)), max(0, min(y2, h))
    if x1 >= x2 or y1 >= y2:
        return out
    # OpenCV requires a contiguous buffer; slice views can be incompatible
    if out.shape[-1] == 4:
        canvas = np.ascontiguousarray(out[:, :, :3].copy())
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        out[:, :, :3] = canvas
    else:
        canvas = np.ascontiguousarray(out.copy())
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        out[:] = canvas
    return out


def draw_points_overlay(
    image: np.ndarray,
    fg_points: list[tuple[int, int]],
    bg_points: list[tuple[int, int]],
    radius: int = 14,
    color_fg: tuple[int, int, int] = (0, 255, 0),
    color_bg: tuple[int, int, int] = (255, 0, 0),
    thickness: int = 4,
) -> np.ndarray:
    """Draw foreground (green) and background (red) points on a copy of the image.
    Points are (row, col) = (y, x) in pixel coordinates.
    """
    import cv2

    out = np.ascontiguousarray(np.asarray(image, dtype=np.uint8).copy())
    if out.shape[-1] == 4:
        canvas = np.ascontiguousarray(out[:, :, :3].copy())
    else:
        canvas = np.ascontiguousarray(out.copy())
    for (py, px) in fg_points:
        cv2.circle(canvas, (int(px), int(py)), radius, color_fg, thickness)
    for (py, px) in bg_points:
        cv2.circle(canvas, (int(px), int(py)), radius, color_bg, thickness)
    if out.shape[-1] == 4:
        out[:, :, :3] = canvas
    else:
        out[:] = canvas
    return out
