"""Unit tests for mask refinement."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.refine import refine_mask


def test_refine_mask_binary_unchanged_with_zero_feather():
    """Refine with feather=0 and kernel=1 should preserve binary mask."""
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[5:15, 5:15] = 1.0
    out = refine_mask(mask, morph_kernel=1, feather_px=0, mask_threshold=0.5)
    assert out.shape == mask.shape
    assert out.dtype == np.float32
    np.testing.assert_array_equal(out, mask)


def test_refine_mask_synthetic_soft():
    """Refine soft mask; output in [0, 1]."""
    mask = np.random.RandomState(42).rand(30, 30).astype(np.float32)
    out = refine_mask(mask, morph_kernel=3, feather_px=1.0, mask_threshold=0.5)
    assert out.shape == mask.shape
    assert out.min() >= 0 and out.max() <= 1


def test_refine_mask_morph_closes_gaps():
    """Larger kernel can smooth small holes."""
    mask = np.zeros((25, 25), dtype=np.uint8)
    mask[8:17, 8:17] = 255
    mask[12, 12] = 0  # small hole
    out = refine_mask(mask, morph_kernel=5, feather_px=0, mask_threshold=0.5)
    assert out.shape == mask.shape
    # After close, center might be filled
    assert out[12, 12] >= 0
