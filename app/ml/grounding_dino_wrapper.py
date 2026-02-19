"""Optional GroundingDINO detector; disabled by default, used only when explicitly enabled."""

from __future__ import annotations

import io
import re
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import List

import numpy as np

from app.ml.detect import DetectedObject

_CONFIG_PATH = Path(__file__).resolve().parent / "groundingdino_config" / "GroundingDINO_SwinT_OGC.py"
_model_cache: tuple | None = None


def _get_model():
    """Lazy-load GroundingDINO model. Returns (model, device) or (None, None) if unavailable."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    try:
        from app.utils.cache import get_model_cache_dir
        import torch
        ckpt = get_model_cache_dir() / "groundingdino" / "groundingdino_swint_ogc.pth"
        if not ckpt.exists() or not _CONFIG_PATH.exists():
            return (None, None)
        devnull = io.StringIO()
        with warnings.catch_warnings(), redirect_stdout(devnull), redirect_stderr(devnull):
            warnings.simplefilter("ignore", category=FutureWarning)
            warnings.simplefilter("ignore", category=SyntaxWarning)
            warnings.filterwarnings("ignore", message=".*custom C\\+\\+ ops.*CPU")
            warnings.filterwarnings("ignore", message=".*meshgrid.*indexing")
            warnings.filterwarnings("ignore", message=".*timm\\.models\\.layers.*")
            warnings.filterwarnings("ignore", message=".*UNEXPECTED.*")
            from groundingdino.util.slconfig import SLConfig
            from groundingdino.models import build_model
            from groundingdino.util.utils import clean_state_dict
            args = SLConfig.fromfile(str(_CONFIG_PATH))
            args.device = "cuda" if torch.cuda.is_available() else "cpu"
            model = build_model(args)
        checkpoint = torch.load(str(ckpt), map_location="cpu")
        with redirect_stdout(devnull), redirect_stderr(devnull):
            model.load_state_dict(clean_state_dict(checkpoint["model"]), strict=False)
        model.eval()
        device = args.device
        _model_cache = (model, device)
        return _model_cache
    except Exception:
        import traceback
        traceback.print_exc()
        raise


def _transform_image(image_pil):
    """Apply same transform as GroundingDINO demo (RandomResize 800, max 1333, ToTensor, Normalize)."""
    import groundingdino.datasets.transforms as T
    transform = T.Compose([
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    image_tensor, _ = transform(image_pil, None)
    return image_tensor


def _get_grounding_output(model, image_tensor, caption, box_threshold, text_threshold, device):
    """Run model forward and return (boxes normalized xywh, list of 'phrase (0.xx)' strings)."""
    import torch
    from groundingdino.util.utils import get_phrases_from_posmap

    caption = caption.lower().strip()
    if not caption.endswith("."):
        caption = caption + "."
    model = model.to(device)
    image_tensor = image_tensor.to(device)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=FutureWarning)
        with torch.no_grad():
            outputs = model(image_tensor[None], captions=[caption])
    logits = outputs["pred_logits"].sigmoid()[0]
    boxes = outputs["pred_boxes"][0]
    filt_mask = logits.max(dim=1)[0] > box_threshold
    logits_filt = logits[filt_mask].cpu()
    boxes_filt = boxes[filt_mask].cpu()
    tokenizer = model.tokenizer
    tokenized = tokenizer(caption)
    pred_phrases = []
    for logit, _ in zip(logits_filt, boxes_filt):
        pred_phrase = get_phrases_from_posmap(logit > text_threshold, tokenized, tokenizer)
        pred_phrases.append(pred_phrase + f"({str(logit.max().item())[:4]})")
    return boxes_filt, pred_phrases


def _parse_phrase(phrase: str) -> tuple[str, float]:
    """Extract label and confidence from 'label (0.xx)'."""
    match = re.search(r"\s*\(([0-9.]+)\)\s*$", phrase)
    if match:
        conf = float(match.group(1))
        label = phrase[: match.start()].strip()
        return label or "object", conf
    return phrase.strip() or "object", 0.0


def _boxes_xywh_norm_to_xyxy_pixels(boxes_xywh_norm, w: int, h: int):
    """Convert normalized (0-1) xywh (cx, cy, w, h) to pixel xyxy (x1, y1, x2, y2), clipped to image."""
    import torch
    boxes = boxes_xywh_norm * torch.tensor([w, h, w, h], dtype=boxes_xywh_norm.dtype)
    cx, cy, bw, bh = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    x1 = (cx - bw / 2).clamp(min=0, max=w)
    y1 = (cy - bh / 2).clamp(min=0, max=h)
    x2 = (cx + bw / 2).clamp(min=0, max=w)
    y2 = (cy + bh / 2).clamp(min=0, max=h)
    return list(zip(x1.tolist(), y1.tolist(), x2.tolist(), y2.tolist()))


def run_grounding_dino(image: np.ndarray) -> tuple[List[DetectedObject], bool, str | None]:
    """Run GroundingDINO if weights and deps exist. Returns (objects, True, None) or ([], False, error)."""
    try:
        from PIL import Image
        from app.utils.cache import get_model_cache_dir
        model, device = _get_model()
        if model is None:
            ckpt = get_model_cache_dir() / "groundingdino" / "groundingdino_swint_ogc.pth"
            if not ckpt.exists():
                return [], False, f"Checkpoint not found at {ckpt}. Place groundingdino_swint_ogc.pth there."
            if not _CONFIG_PATH.exists():
                return [], False, f"Config not found at {_CONFIG_PATH}."
            return [], False, "Model failed to load (see console for traceback)."
        h, w = image.shape[0], image.shape[1]
        rgb = image[:, :, :3] if image.shape[-1] >= 3 else image
        image_pil = Image.fromarray(rgb)
        image_tensor = _transform_image(image_pil)
        # Broad caption and lower thresholds to detect more objects (bottles, baskets, etc.)
        boxes_filt, pred_phrases = _get_grounding_output(
            model, image_tensor,
            caption=(
                "object . thing . person . animal . food . furniture . vehicle . "
                "bottle . container . drink . cup . mug . bag . basket . fruit . "
                "book . pen . glasses ."
            ),
            box_threshold=0.25,
            text_threshold=0.2,
            device=device,
        )
        if len(boxes_filt) == 0:
            return [], True, None
        xyxy_list = _boxes_xywh_norm_to_xyxy_pixels(boxes_filt, w, h)
        out = []
        for (x1, y1, x2, y2), phrase in zip(xyxy_list, pred_phrases):
            label, conf = _parse_phrase(phrase)
            out.append(DetectedObject(label=label, confidence=conf, bbox=(x1, y1, x2, y2)))
        return out, True, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return [], False, str(e)
