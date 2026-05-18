"""Centralized config loader. Reads from environment variables / .env file.

Place a `.env` next to this file (see `.env.example`) or export env vars before
launching the bot. All sensitive values MUST come from env — never commit them.
"""
import os
from pathlib import Path

# Optional .env loading (no hard dep — falls back to os.environ if python-dotenv missing)
try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except ImportError:
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int_set(key: str, default: str = "") -> set[int]:
    """Parse a comma-separated list of integer Telegram IDs."""
    raw = _env(key, default)
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                out.add(int(part))
            except ValueError:
                pass
    return out


# --- Paths ---
ROOT_DIR = Path(__file__).resolve().parent.parent
BOT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(_env("IMAJIN_DATA_DIR", str(ROOT_DIR / "data")))
OUT_DIR = Path(_env("IMAJIN_OUT_DIR", str(DATA_DIR / "out")))
ASSETS_DIR = Path(_env("IMAJIN_ASSETS_DIR", str(ROOT_DIR / "assets")))

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(_env("IMAJIN_DB_PATH", str(DATA_DIR / "users.db")))
QRIS_PATH = Path(_env("IMAJIN_QRIS_PATH", str(ASSETS_DIR / "qris.jpg")))

# --- Telegram ---
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = _env_int_set("ADMIN_TELEGRAM_IDS")

# --- Engine: Free tier (OpenAI-compatible image API) ---
# Default points at a local 9router; replace with any OpenAI-compatible image
# endpoint (OpenAI direct, OpenRouter image gen, custom router, etc.)
FREE_API_BASE = _env("FREE_API_BASE", "http://127.0.0.1:20128/v1")
FREE_API_KEY = _env("FREE_API_KEY")
FREE_IMAGE_MODEL = _env("FREE_IMAGE_MODEL", "cx/gpt-5.4-image")

# Prompt enhancement / random prompt LLM (chat completions)
PROMPT_LLM_BASE = _env("PROMPT_LLM_BASE", "http://127.0.0.1:20128/v1")
PROMPT_LLM_KEY = _env("PROMPT_LLM_KEY")
PROMPT_ENHANCE_MODEL = _env("PROMPT_ENHANCE_MODEL", "kr/claude-haiku-4.5")
PROMPT_RANDOM_MODEL = _env("PROMPT_RANDOM_MODEL", "kr/deepseek-3.2")

# --- Engine: Premium tier (pluggable) ---
# These point at subprocess scripts the bot runs to generate premium content.
# Default stubs return "not implemented" — wire your own engine. See
# bot/gen_image_one.py / gen_video_one.py / check_balance_one.py for the
# JSON-stdout contract.
GEN_IMAGE_PREMIUM_PY = _env("GEN_IMAGE_PREMIUM_PY", str(BOT_DIR / "gen_image_one.py"))
GEN_VIDEO_PREMIUM_PY = _env("GEN_VIDEO_PREMIUM_PY", str(BOT_DIR / "gen_video_one.py"))
CHECK_BALANCE_PY = _env("CHECK_BALANCE_PY", str(BOT_DIR / "check_balance_one.py"))
GEN_IMAGE_FREE_PY = _env("GEN_IMAGE_FREE_PY", str(BOT_DIR / "gen_image_free.py"))

# --- Catalog (model/preset lists for premium engine) ---
# JSON files; bot loads on startup. Optional — empty list works.
CATALOG_DIR = Path(_env("IMAJIN_CATALOG_DIR", str(DATA_DIR / "catalog")))
CATALOG_DIR.mkdir(parents=True, exist_ok=True)


def validate() -> list[str]:
    """Return list of missing required env vars (call at startup)."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not ADMIN_IDS:
        missing.append("ADMIN_TELEGRAM_IDS")
    return missing
