"""Premium engine catalog loader (stub).

The real bot uses an external image/video provider for premium tier. This
module exposes the static catalog (model list + style preset list) the bot
shows to premium users.

To wire your own provider: drop JSON files under `data/catalog/`:
  - models_clean.json  → list of {id, name, description?}
  - presets_clean.json → list of {id, name, description?}

Empty catalog is fine — bot will fall back to hardcoded defaults in
klein_bot.py (POPULAR_MODELS / STYLE_PRESETS / VIDEO_MODELS).
"""
import json
from pathlib import Path

from config import CATALOG_DIR


def load_catalog() -> dict:
    models_path = CATALOG_DIR / "models_clean.json"
    presets_path = CATALOG_DIR / "presets_clean.json"
    return {
        "models": json.loads(models_path.read_text()) if models_path.exists() else [],
        "presets": json.loads(presets_path.read_text()) if presets_path.exists() else [],
    }
