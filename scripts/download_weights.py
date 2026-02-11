#!/usr/bin/env python3
"""Download optional model weights for SAM and GroundingDINO (CPU-friendly options)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.cache import get_model_cache_dir


def main():
    parser = argparse.ArgumentParser(description="Download optional weights for Object Paint Agent")
    parser.add_argument("--sam", action="store_true", help="Download SAM (segment-anything) tiny weights")
    parser.add_argument("--grounding-dino", action="store_true", help="Download GroundingDINO weights")
    parser.add_argument("--all", action="store_true", help="Download all optional weights")
    args = parser.parse_args()

    base = get_model_cache_dir()
    if args.all:
        args.sam = True
        args.grounding_dino = True

    if not (args.sam or args.grounding_dino):
        print("No targets specified. Use --sam, --grounding-dino, or --all.")
        print("Without weights, the app uses GrabCut for segmentation (no download needed).")
        return 0

    if args.sam:
        sam_dir = base / "sam2"
        sam_dir.mkdir(parents=True, exist_ok=True)
        ckpt = sam_dir / "sam2_hiera_tiny.pt"
        if ckpt.exists():
            print(f"SAM checkpoint already exists: {ckpt}")
        else:
            print("SAM weights: install segment-anything and download manually.")
            print("  pip install segment-anything")
            print("  See: https://github.com/facebookresearch/segment-anything#model-checkpoints")
            print(f"  Place vit_t checkpoint in: {sam_dir}")

    if args.grounding_dino:
        gd_dir = base / "groundingdino"
        gd_dir.mkdir(parents=True, exist_ok=True)
        ckpt = gd_dir / "groundingdino_swint_ogc.pth"
        if ckpt.exists():
            print(f"GroundingDINO checkpoint already exists: {ckpt}")
        else:
            print("GroundingDINO: install groundingdino and download weights manually.")
            print(f"  Place checkpoint in: {gd_dir}")

    print(f"Model cache dir: {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
