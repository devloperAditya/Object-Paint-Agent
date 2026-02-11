"""Unit tests for recolor: preserve outside region and alpha."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.recolor import hex_to_rgb, recolor_masked_region


def test_hex_to_rgb():
    assert hex_to_rgb("#FF0000") == (255, 0, 0)
    assert hex_to_rgb("#00FF00") == (0, 255, 0)
    assert hex_to_rgb("FF0000") == (255, 0, 0)


def test_recolor_preserves_outside_region():
    """Pixels outside mask must be unchanged."""
    h, w = 32, 32
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, 0] = 100
    img[:, :, 1] = 120
    img[:, :, 2] = 140
    img[:, :, 3] = 255
    mask = np.zeros((h, w), dtype=np.float32)
    mask[10:22, 10:22] = 1.0  # only center is mask
    out = recolor_masked_region(img, mask, "#FF0000", strength=0.9)
    # Outside: (0,0), (5,5), (30,30) must match original
    np.testing.assert_array_equal(out[0, 0], img[0, 0])
    np.testing.assert_array_equal(out[5, 5], img[5, 5])
    np.testing.assert_array_equal(out[30, 30], img[30, 30])


def test_recolor_preserves_alpha_exactly():
    """Output alpha must equal input alpha everywhere."""
    h, w = 24, 24
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, :3] = 50
    img[:, :, 3] = 200  # non-full alpha
    mask = np.ones((h, w), dtype=np.float32)  # full mask
    out = recolor_masked_region(img, mask, "#0000FF", strength=1.0)
    np.testing.assert_array_equal(out[:, :, 3], img[:, :, 3])


def test_recolor_deterministic():
    """Same inputs must produce same output."""
    np.random.seed(123)
    img = np.random.randint(0, 256, (16, 16, 4), dtype=np.uint8)
    img[:, :, 3] = 255
    mask = (np.random.rand(16, 16) > 0.5).astype(np.float32)
    out1 = recolor_masked_region(img, mask, "#E53935", strength=0.8)
    out2 = recolor_masked_region(img, mask, "#E53935", strength=0.8)
    np.testing.assert_array_equal(out1, out2)
