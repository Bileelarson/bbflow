"""Premium image generator — STUB.

Wire your own provider here. Reads prompt + params from env, emits JSON to stdout.

Env input:
  LEO_PROMPT    : str (required)
  LEO_QUANTITY  : int (1-4)
  LEO_MODEL     : str (model id from catalog)
  LEO_STYLE     : str (style preset id)
  LEO_WIDTH     : int (px)
  LEO_HEIGHT    : int (px)
  LEO_NEGATIVE  : str (negative prompt)

Output JSON to stdout:
  Success: {"ok": true, "gen_id": "...", "files": ["/abs/path/img.png", ...], "prompt": "..."}
  Failure: {"ok": false, "error": "..."}
"""
import json
import sys

print(json.dumps({
    "ok": False,
    "error": "Premium image engine not configured. Edit bot/gen_image_one.py to wire your provider.",
}))
sys.exit(0)
