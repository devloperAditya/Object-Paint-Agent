#!/usr/bin/env bash
# Optional: download model weights for Object Paint Agent.
# Without these, the app runs in "lite" mode using GrabCut (no GPU/weights required).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Object Paint Agent - optional weight download"
echo "Model cache: ${MODEL_CACHE_DIR:-$PROJECT_ROOT/models}"
python scripts/download_weights.py "$@"
