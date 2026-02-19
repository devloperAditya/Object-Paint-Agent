"""Gradio UI: single-page Object Paint Agent (rectangle selection, recolor, shadow)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import gradio as gr
import numpy as np

from app.ml.recolor import parse_color_to_rgb
from app.pipeline import (
    build_metadata,
    export_outputs,
    get_image_with_bbox_overlay,
    run_detection,
    run_expand_mask_shadow,
    run_recolor,
    run_refine,
    run_segment_rect,
)
from app.utils.bbox import draw_rect_overlay
from app.utils.cache import get_data_dir
from app.utils.image_io import load_image

MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", "1024"))
MAX_FILE_MB = 20
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DEFAULT_LEFT, DEFAULT_TOP = 15.0, 15.0
DEFAULT_RIGHT, DEFAULT_BOTTOM = 85.0, 85.0


def validate_upload(file: gr.File | str | list | None) -> tuple[str | None, np.ndarray | None]:
    if file is None:
        return "No file uploaded", None
    if isinstance(file, list):
        file = file[0] if file else None
    if file is None or (isinstance(file, str) and not file.strip()):
        return "No file uploaded", None
    if isinstance(file, dict) and "name" in file:
        path = Path(file["name"])
    elif isinstance(file, (str, Path)):
        path = Path(file)
    else:
        path = Path(getattr(file, "name", str(file)))
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return f"Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}", None
    if path.stat().st_size > MAX_FILE_MB * 1024 * 1024:
        return f"File too large (max {MAX_FILE_MB} MB)", None
    try:
        img = load_image(path, max_size=MAX_IMAGE_PIXELS, preserve_alpha=True)
        return None, img
    except Exception as e:
        return str(e), None


def _dropdown_update(choices: list, value=None):
    """Update Dropdown choices and value; avoid passing [] as value (Gradio warning)."""
    return gr.update(choices=choices, value=value)


def on_upload(file: gr.File | None, state: dict):
    err, img = validate_upload(file)
    if err:
        return state, None, err, _dropdown_update([]), "", DEFAULT_LEFT, DEFAULT_TOP, DEFAULT_RIGHT, DEFAULT_BOTTOM
    state = {
        "image": img,
        "detections": [],
        "selected_idx": None,
        "mask": None,
        "painted": None,
        "metadata": None,
        "segment_mode": "grabcut_rect",
        "detect_mode": "none",
    }
    hint = "Adjust the box below to cover your object, then click Generate mask."
    img_with_box = draw_rect_overlay(img, DEFAULT_LEFT, DEFAULT_TOP, DEFAULT_RIGHT, DEFAULT_BOTTOM)
    return (
        state, img_with_box, "", _dropdown_update([]), hint,
        DEFAULT_LEFT, DEFAULT_TOP, DEFAULT_RIGHT, DEFAULT_BOTTOM,
    )


def on_detect(state: dict, use_grounding_dino: bool):
    if state.get("image") is None:
        return state, None, _dropdown_update([]), "Upload an image first."
    img = state["image"]
    objs, mode, err = run_detection(img, use_grounding_dino=use_grounding_dino)
    state["detections"] = objs
    state["detect_mode"] = mode
    overlay = get_image_with_bbox_overlay(img, objs, None)
    labels = [f"{o.label} ({o.confidence:.2f})" for o in objs]
    if objs:
        msg = f"Detected {len(objs)} object(s). Or use the box sliders below."
    elif mode == "grounding_dino":
        msg = "Grounding DINO ran but found no objects. Use the box sliders to select the object, then Generate mask."
    elif err:
        msg = f"Detection failed: {err}. Check the console for details. Or use the box sliders to select the object, then Generate mask."
    else:
        msg = "No detector used. Enable 'Use Grounding DINO' and ensure the checkpoint is in models/groundingdino/ (see README). Or use the box sliders to select the object, then Generate mask."
    return state, overlay, _dropdown_update(labels), msg


def on_select_object(
    state: dict,
    choice: str | None,
    left: float,
    top: float,
    right: float,
    bottom: float,
):
    """Update state and overlay; when an object is selected, set sliders to its bbox (percent)."""
    img = state.get("image")
    if img is None or not state.get("detections"):
        return state, img, left, top, right, bottom
    objs = state["detections"]
    idx = None
    if choice and choice != "None":
        for i, o in enumerate(objs):
            if f"{o.label} ({o.confidence:.2f})" == choice:
                idx = i
                break
    state["selected_idx"] = idx
    overlay = get_image_with_bbox_overlay(state["image"], objs, idx)
    # When an object is selected, set sliders to its bbox so "Generate mask" uses that region
    h, w = img.shape[0], img.shape[1]
    if idx is not None and w > 0 and h > 0:
        x1, y1, x2, y2 = objs[idx].bbox
        left_pct = round((x1 / w) * 100, 1)
        top_pct = round((y1 / h) * 100, 1)
        right_pct = round((x2 / w) * 100, 1)
        bottom_pct = round((y2 / h) * 100, 1)
        return state, overlay, left_pct, top_pct, right_pct, bottom_pct
    return state, overlay, left, top, right, bottom


def on_generate_mask(state: dict, left: float, top: float, right: float, bottom: float,
                     morph_kernel: int, feather_px: float, mask_threshold: float):
    if state.get("image") is None:
        return state, None, "Upload an image first."
    if left >= right or top >= bottom:
        return state, None, "Invalid box: Left < Right and Top < Bottom."
    t0 = time.perf_counter()
    mask, seg_mode = run_segment_rect(state["image"], left, top, right, bottom)
    state["segment_mode"] = seg_mode
    mask = run_refine(mask, morph_kernel, feather_px, mask_threshold)
    state["mask"] = mask
    elapsed = time.perf_counter() - t0
    mask_preview = (np.clip(mask, 0, 1) * 255).astype(np.uint8)
    mask_preview = np.stack([mask_preview] * 3, axis=-1)
    return state, mask_preview, f"Mask generated in {elapsed:.2f}s."


def on_apply_recolor(
    state: dict, color_hex: str, recolor_strength: float,
    use_replace_color: bool, replace_color_hex: str, hue_tolerance_degrees: float,
    include_shadow: bool, shadow_extent_px: float, shadow_darkness: float,
):
    if state.get("image") is None:
        return state, None, "", "Upload an image first."
    if state.get("mask") is None:
        return state, None, "", "Generate a mask first."
    try:
        color_hex = (color_hex or "").strip() or "#FF0000"
        if not color_hex.startswith("#") and "rgba" not in color_hex.lower():
            color_hex = "#" + color_hex
    except Exception:
        color_hex = "#FF0000"
    source_hex = None
    if use_replace_color and replace_color_hex:
        source_hex = (replace_color_hex or "").strip()
        if source_hex and not source_hex.startswith("#") and "rgba" not in source_hex.lower():
            source_hex = "#" + source_hex
    mask = state["mask"]
    if include_shadow:
        mask = run_expand_mask_shadow(
            state["image"], mask,
            dilation_px=max(5, int(shadow_extent_px)),
            shadow_value_threshold=max(0.15, min(0.85, shadow_darkness)),
        )
    t0 = time.perf_counter()
    painted = run_recolor(
        state["image"], mask, color_hex, recolor_strength,
        source_color_hex=source_hex,
        hue_tolerance_degrees=max(5, min(90, hue_tolerance_degrees)),
    )
    elapsed = time.perf_counter() - t0
    state["painted"] = painted
    r, g, b = parse_color_to_rgb(color_hex)
    color_hex_display = f"#{r:02x}{g:02x}{b:02x}"
    selected = None
    if state.get("detections") and state.get("selected_idx") is not None:
        idx = state["selected_idx"]
        if 0 <= idx < len(state["detections"]):
            selected = state["detections"][idx].label
    meta = build_metadata(
        selected_object=selected, color_hex=color_hex_display,
        mode_detect=state.get("detect_mode", "none"),
        mode_segment=state.get("segment_mode", "grabcut_rect"),
        timings={"recolor_seconds": round(elapsed, 4)},
    )
    state["metadata"] = meta
    return state, painted, json.dumps(meta, indent=2), "Recolor applied."


def on_export(state: dict):
    if state.get("painted") is None or state.get("mask") is None or state.get("metadata") is None:
        return None, None, "", "Generate mask and apply recolor first."
    out_dir = get_data_dir()
    base = f"object_paint_{int(time.time())}"
    p1, p2, p3 = export_outputs(state["painted"], state["mask"], state["metadata"], out_dir, base_name=base)
    return str(p1), str(p2), str(p3), f"Exported to {out_dir}"


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Object Paint Agent") as app:
        gr.Markdown("# Object Paint Agent")
        gr.Markdown(
            "Upload an image, **adjust the green box** to cover the object, "
            "then **Generate mask** → pick a color → **Apply recolor**."
        )
        state = gr.State({})

        with gr.Row():
            with gr.Column(scale=1):
                upload = gr.File(label="Upload image (PNG/JPG)", file_types=[".png", ".jpg", ".jpeg"])
                upload_status = gr.Textbox(label="Status", interactive=False)
                img_display = gr.Image(label="Image — selection box below", type="numpy")
                gr.Markdown("**Object box** (percent)")
                with gr.Row():
                    left_slider = gr.Slider(0, 100, value=DEFAULT_LEFT, step=1, label="Left %")
                    top_slider = gr.Slider(0, 100, value=DEFAULT_TOP, step=1, label="Top %")
                with gr.Row():
                    right_slider = gr.Slider(0, 100, value=DEFAULT_RIGHT, step=1, label="Right %")
                    bottom_slider = gr.Slider(0, 100, value=DEFAULT_BOTTOM, step=1, label="Bottom %")
                gen_mask_btn = gr.Button("Generate mask")
                mask_status = gr.Textbox(label="Mask", interactive=False)
                color_picker = gr.ColorPicker(label="Paint color (hex)", value="#E53935", elem_id="paint_color_picker")
                recolor_btn = gr.Button("Apply recolor")
                recolor_status = gr.Textbox(label="Recolor", interactive=False)

                with gr.Accordion("Recolor only a specific color", open=False):
                    gr.Markdown(
                        "Only when you want to change **one** color on the object (e.g. yellow body → red, beak unchanged). "
                        "Pixels matching the **color below** are changed to the **Paint color** above. For the **whole object** in the paint color, leave this **unchecked**."
                    )
                    use_replace_color = gr.Checkbox(value=False, label="Only recolor pixels matching the color below (→ Paint color above)")
                    replace_color_picker = gr.ColorPicker(label="Color in image to replace (e.g. yellow)", value="#FFEB3B", elem_id="replace_color_picker")
                    hue_tolerance_slider = gr.Slider(5, 60, value=28, step=1, label="Color match tolerance (degrees) — use 25–35 for yellow body not orange beak; higher for one-color objects")

                with gr.Accordion("Include shadow in recolor", open=False):
                    gr.Markdown("Expand mask to include the object's cast shadow.")
                    include_shadow_check = gr.Checkbox(value=False, label="Include shadow in recolor")
                    shadow_extent_slider = gr.Slider(5, 50, value=20, step=1, label="Shadow extent (pixels)")
                    shadow_darkness_slider = gr.Slider(0.15, 0.85, value=0.5, step=0.05, label="Shadow darkness")

                with gr.Accordion("Optional: Detect objects", open=False):
                    detect_btn = gr.Button("Detect objects")
                    use_grounding = gr.Checkbox(value=False, label="Use Grounding DINO")
                    detect_status = gr.Textbox(label="Detection", interactive=False)
                    object_dropdown = gr.Dropdown(label="Detected objects", choices=[], value=None, allow_custom_value=False)

                with gr.Accordion("Advanced options", open=False):
                    feather_px = gr.Slider(0, 5, value=2, step=0.5, label="Feather (px)")
                    morph_kernel = gr.Slider(1, 9, value=3, step=2, label="Morph kernel (odd)")
                    recolor_strength = gr.Slider(0.1, 1.0, value=0.8, step=0.1, label="Recolor strength")
                    mask_threshold = gr.Slider(0.0, 1.0, value=0.5, step=0.05, label="Mask threshold")

            with gr.Column(scale=1):
                painted_display = gr.Image(label="Painted image (PNG)", type="numpy")
                mask_preview = gr.Image(label="Mask preview", type="numpy")
                metadata_json = gr.JSON(label="Metadata")
                export_btn = gr.Button("Export / Save")
                export_status = gr.Textbox(label="Export", interactive=False)
                d1 = gr.File(label="Download painted PNG", visible=True, interactive=False)
                d2 = gr.File(label="Download mask PNG", visible=True, interactive=False)
                d3 = gr.File(label="Download metadata JSON", visible=True, interactive=False)

        upload.change(on_upload, [upload, state], [state, img_display, upload_status, object_dropdown, detect_status, left_slider, top_slider, right_slider, bottom_slider])

        def update_rect(s, l, t, r, b):
            if s.get("image") is None:
                return None
            return draw_rect_overlay(s["image"], l, t, r, b)

        for sl in [left_slider, top_slider, right_slider, bottom_slider]:
            sl.change(update_rect, [state, left_slider, top_slider, right_slider, bottom_slider], [img_display])

        gen_mask_btn.click(
            on_generate_mask,
            [state, left_slider, top_slider, right_slider, bottom_slider, morph_kernel, feather_px, mask_threshold],
            [state, mask_preview, mask_status],
        )

        recolor_btn.click(
            on_apply_recolor,
            [
                state, color_picker, recolor_strength,
                use_replace_color, replace_color_picker, hue_tolerance_slider,
                include_shadow_check, shadow_extent_slider, shadow_darkness_slider,
            ],
            [state, painted_display, metadata_json, recolor_status],
        )

        export_btn.click(lambda s: on_export(s), [state], [d1, d2, d3, export_status])

        detect_btn.click(on_detect, [state, use_grounding], [state, img_display, object_dropdown, detect_status])
        object_dropdown.change(
            on_select_object,
            [state, object_dropdown, left_slider, top_slider, right_slider, bottom_slider],
            [state, img_display, left_slider, top_slider, right_slider, bottom_slider],
        )

    return app
