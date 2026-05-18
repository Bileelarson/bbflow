"""Premium video generator — STUB.

Wire your own provider here. Reads prompt + params from env, emits JSON to stdout.

Env input:
  LEO_PROMPT       : str (required)
  LEO_VIDEO_MODEL  : str (e.g. "kling-v3", "wan-2.1")
  LEO_DURATION     : int (seconds)
  LEO_ASPECT       : str (e.g. "16:9", "9:16", "1:1")

Output JSON to stdout:
  Success: {"ok": true, "gen_id": "...", "files": ["/abs/path/video.mp4"], "prompt": "..."}
  Failure: {"ok": false, "error": "..."}
"""
import json
import sys

print(json.dumps({
    "ok": False,
    "error": "Premium video engine not configured. Edit bot/gen_video_one.py to wire your provider.",
}))
sys.exit(0)
