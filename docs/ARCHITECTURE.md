# Architecture

## Components and data flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐     ┌─────────┐
│ Upload      │────▶│ Detect       │────▶│ Segment     │────▶│ Refine   │────▶│ Recolor │
│ (PNG/JPG)   │     │ (optional)   │     │ (points)     │     │ (morph   │     │ (LAB)   │
│             │     │              │     │ SAM/GrabCut  │     │ +feather)│     │         │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────┘     └─────────┘
       │                     │                    │                  │               │
       ▼                     ▼                    ▼                  ▼               ▼
  app/utils/            app/ml/              app/ml/            app/ml/          app/ml/
  image_io.py           detect.py            segment.py         refine.py        recolor.py
```

- **Upload**: `app/utils/image_io` loads image, enforces max size (e.g. 1024 px), and ensures RGBA.
- **Detect**: Optional GroundingDINO in `app/ml/detect`; returns list of (label, confidence, bbox). Disabled by default on CPU.
- **Segment**: User foreground/background points → `app/ml/segment` → SAM2 (if weights) or GrabCut. Returns float mask [0,1].
- **Refine**: `app/ml/refine` applies morphological close/open and optional Gaussian feather.
- **Recolor**: `app/ml/recolor` uses LAB: keeps L, shifts A/B toward target hex; composites only inside mask; alpha unchanged.
- **Export**: Painted PNG, mask PNG, metadata JSON written under `data/` (or `DATA_DIR`).

## UI (Gradio)

Single-page `app/ui.py`: upload, optional detect, image with bbox overlay and dropdown, click-to-add points, generate mask, color picker, advanced options (feather, morph kernel, strength, threshold), output panel with downloads.

## Serving

`app/main.py` builds a FastAPI app, adds `GET /health`, and mounts the Gradio app at `/`. Served with uvicorn; `PORT` env (default 7860).

## Modes

- **Mode 1 (default)**: Point-based segmentation (SAM if weights, else GrabCut). No detection required.
- **Mode 2 (optional)**: GroundingDINO + SAM for "detect then segment"; must be explicitly enabled and requires weights.
