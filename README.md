# Object Paint Agent

Production-grade Gradio demo: detect objects, segment with points (SAM or GrabCut), and recolor only the selected region while preserving alpha and leaving the rest of the image unchanged.

**CPU-only compatible.** Works out of the box in "lite" mode (GrabCut) with no model downloads. Optional: SAM and GroundingDINO for better segmentation and detection.

## Quickstart

### With uv (recommended)

```bash
uv sync
uv run python -m app.main
```

Open http://localhost:7860

### With pip

```bash
pip install -e .
python -m app.main
```

### Docker

```bash
docker compose up --build
```

Runs on port 7860. Health check: `GET /health`.

## How selection works

1. **Upload** a PNG or JPG (alpha is preserved for PNG).
2. **Detect objects** (optional): if you have GroundingDINO weights, use this to get a list of objects and bboxes; otherwise skip and use manual selection.
3. **Manual selection**: set "Click mode" to Foreground or Background, then click on the image to add points. Add a few foreground points on the object and (optionally) background points outside. Click **Generate mask** to segment (uses SAM if weights are present, otherwise GrabCut).
4. **Paint color**: choose a hex color and click **Apply recolor**. Only the masked region is recolored (LAB space, luminance preserved); the rest of the image and alpha are unchanged.
5. **Export**: save the painted PNG, mask preview, and metadata JSON.

## Troubleshooting weights

- **No weights**: The app uses GrabCut for segmentation. No download needed.
- **SAM**: For point-based segmentation, place SAM (e.g. segment-anything) checkpoint in `models/sam2/` and install `segment-anything` if you use the optional wrapper. See `scripts/download_weights.py`.
- **GroundingDINO**: Detection is disabled by default. To enable: (1) install PyTorch in this project (`uv pip install torch torchvision` or `pip install -e ".[detect]"`); (2) clone [GroundingDINO](https://github.com/IDEA-Research/GroundingDINO) anywhere and install it into this project’s env with **no build isolation** so the build sees torch: `uv pip install -e "C:\path\to\GroundingDINO" --no-build-isolation` (or with pip: `pip install -e "C:\path\to\GroundingDINO" --no-build-isolation` from the project dir); (3) place `groundingdino_swint_ogc.pth` in `models/groundingdino/`; (4) enable "Use Grounding DINO" in the UI.

## Project layout

```
app/           # Gradio UI + pipeline
app/ml/        # detect, segment, refine, recolor
app/utils/     # image I/O, bbox overlay, cache
scripts/       # download_weights, sample run
tests/         # pytest unit + integration
docs/          # ARCHITECTURE, AWS_DEPLOYMENT, SECURITY, OPS
```

## License

MIT
