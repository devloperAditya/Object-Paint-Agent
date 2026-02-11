"""Model and data cache directories."""

from __future__ import annotations

import os
from pathlib import Path


def get_model_cache_dir() -> Path:
    """Return models cache directory; create if needed."""
    base = os.environ.get("MODEL_CACHE_DIR", os.path.join(os.getcwd(), "models"))
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """Return data directory for runtime outputs; create if needed."""
    base = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path
