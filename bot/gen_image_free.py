"""Free-tier image gen via OpenAI-compatible image API.

Connects to any OpenAI-compatible `/v1/images/generations` endpoint that
streams Server-Sent Events with `b64_json` payloads (e.g. local 9router,
OpenAI direct).

Args (env):
  LEO_PROMPT   : str (required)
  LEO_QUANTITY : int (default 1, max 4)

Output JSON to stdout: {ok, gen_id, files: [path...], prompt}
"""
import base64
import json
import os
import re
import subprocess
import sys
import time

# Add bot/ to path so config import works when run as subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FREE_API_BASE, FREE_API_KEY, FREE_IMAGE_MODEL, OUT_DIR

PROMPT = os.environ.get("LEO_PROMPT", "").strip()
try:
    QUANTITY = max(1, min(4, int(os.environ.get("LEO_QUANTITY", "1"))))
except ValueError:
    QUANTITY = 1


def emit(obj):
    print(json.dumps(obj))
    sys.stdout.flush()


if not PROMPT:
    emit({"ok": False, "error": "no prompt"})
    sys.exit(0)

if not FREE_API_KEY:
    emit({"ok": False, "error": "FREE_API_KEY not configured"})
    sys.exit(0)

ENDPOINT = f"{FREE_API_BASE.rstrip('/')}/images/generations"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def gen_one(idx: int):
    """Generate 1 image. Returns (png_path, error_msg). One of them is None."""
    ts = int(time.time())
    slug = re.sub(r"[^a-z0-9]+", "_", PROMPT.lower())[:40].strip("_") or "img"
    sse_path = OUT_DIR / f"img_{ts}_{slug}_{idx}.sse"
    png_path = OUT_DIR / f"img_{ts}_{slug}_{idx}.png"

    payload = {
        "model": FREE_IMAGE_MODEL,
        "prompt": PROMPT,
        "n": 1,
        "size": "auto",
        "quality": "auto",
        "background": "auto",
        "image_detail": "high",
        "output_format": "png",
    }

    cmd = [
        "curl", "-sS", "-N", "-X", "POST",
        ENDPOINT,
        "-H", "Content-Type: application/json",
        "-H", f"Authorization: Bearer {FREE_API_KEY}",
        "-H", "Accept: text/event-stream",
        "--max-time", "240",
        "-d", json.dumps(payload),
    ]

    try:
        with open(sse_path, "w") as out:
            proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, timeout=260)
        if proc.returncode != 0:
            return None, f"curl exit {proc.returncode}: {proc.stderr.decode()[:200]}"
    except subprocess.TimeoutExpired:
        return None, "engine timeout (240s)"
    except Exception as e:
        return None, f"curl failed: {e}"

    # Parse SSE — find last b64_json + capture errors
    try:
        with open(sse_path) as f:
            body = f.read()
    except Exception as e:
        return None, f"read sse: {e}"

    last_b64 = None
    last_error = None
    for block in re.split(r"\n\n+", body):
        block = block.strip()
        if not block:
            continue
        event_match = re.search(r"event:\s*(\S+)", block)
        data_match = re.search(r"data:\s*(\{.*\})", block, re.DOTALL)
        if not data_match:
            continue
        try:
            obj = json.loads(data_match.group(1))
        except Exception:
            continue
        event_name = event_match.group(1) if event_match else ""

        if event_name == "error":
            last_error = obj.get("message") or obj.get("error") or str(obj)
            continue

        data = obj.get("data") or []
        if isinstance(data, list):
            for it in data:
                if isinstance(it, dict) and it.get("b64_json"):
                    last_b64 = it["b64_json"]
        if obj.get("b64_json"):
            last_b64 = obj["b64_json"]

    # Cleanup SSE log
    try:
        os.remove(sse_path)
    except Exception:
        pass

    if not last_b64:
        if last_error:
            msg = str(last_error)
            if "entitled" in msg.lower() or "plus/pro required" in msg.lower():
                friendly = (
                    "Engine sedang sibuk atau prompt tidak didukung. "
                    "Silakan coba prompt yang lebih spesifik."
                )
            elif "not return an image" in msg.lower():
                friendly = (
                    "Prompt tidak menghasilkan gambar. "
                    "Silakan coba prompt deskripsi visual yang lebih jelas."
                )
            elif "moderation" in msg.lower() or "policy" in msg.lower():
                friendly = "Prompt ditolak content policy. Silakan ganti prompt."
            else:
                friendly = f"Engine error: {msg[:100]}"
            return None, friendly
        return None, "Engine tidak menghasilkan gambar. Silakan coba prompt lain."

    try:
        png_bytes = base64.b64decode(last_b64)
        with open(png_path, "wb") as f:
            f.write(png_bytes)
    except Exception as e:
        return None, f"decode png: {e}"

    return str(png_path), None


# Loop N times sequentially (API only supports n=1)
files = []
last_err = None
for i in range(QUANTITY):
    png, err = gen_one(i)
    if png:
        files.append(png)
    else:
        last_err = err
        break  # stop on first error

if not files:
    emit({"ok": False, "error": last_err or "unknown error"})
    sys.exit(0)

emit({
    "ok": True,
    "gen_id": f"free_{int(time.time())}",
    "files": files,
    "prompt": PROMPT,
    "engine": "free_tier",
    "requested": QUANTITY,
    "delivered": len(files),
})
