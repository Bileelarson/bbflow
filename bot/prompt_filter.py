"""Prompt sanity filter + auto-enhancer.

Returns: (allowed, prompt_to_use, reason_if_rejected)

Reject reasons:
  - "nsfw"        → explicit sexual content
  - "violent"     → graphic violence
  - "too_short"   → < 2 meaningful words
  - "public_figure" (warning, not reject)

Auto-enhance: kalau prompt < 3 word + bukan NSFW → expand pakai LLM.
"""
import re

import requests

from config import (
    PROMPT_LLM_BASE,
    PROMPT_LLM_KEY,
    PROMPT_ENHANCE_MODEL,
    PROMPT_RANDOM_MODEL,
)

ROUTER = f"{PROMPT_LLM_BASE.rstrip('/')}/chat/completions"

# Indonesian + English NSFW keywords (lowercase)
NSFW_WORDS = {
    # Sexual organs / acts (Indo)
    "kontol", "memek", "ngentot", "ngentod", "ngocok", "ngaceng", "tetek",
    "puting", "pepek", "bokep", "bokeb", "telanjang", "bugil", "bugel",
    # Sexual context
    "porno", "porn", "sex", "nude", "naked", "topless", "lingerie",
    "bikini", "thong", "bdsm", "fetish", "erotic",
    # Slang sexual
    "horny", "kinky", "ngewe", "colmek",
}

# Public figure / politik (Indonesia) — warn only
PUBLIC_FIGURES_ID = {
    "prabowo", "jokowi", "megawati", "anies", "ganjar", "amin",
    "puan", "luhut", "erlangga", "airlangga", "ridwan kamil",
    "fadli zon", "sandiaga", "agus", "ahy",
    "trump", "biden", "putin", "xi jinping", "modi",
}

# Hate / extremist
HATE_WORDS = {
    "nazi", "isis", "terrorist", "kkk",
}


def _has_word(text: str, words: set) -> str | None:
    """Return the matched word or None."""
    text_lc = text.lower()
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", text_lc):
            return w
    return None


def filter_prompt(prompt: str) -> tuple[bool, str, str]:
    """Pre-filter prompt before sending to image gen.

    Returns:
        (allowed, sanitized_prompt, reason_if_rejected)

    Reasons:
        ""              → OK
        "nsfw"          → explicit sexual rejected
        "hate"          → hate/extremist rejected
        "too_short"     → < 8 chars or < 2 word
        "empty"         → empty/whitespace
    """
    p = (prompt or "").strip()
    if not p:
        return False, p, "empty"

    if len(p) < 4:
        return False, p, "too_short"

    words = re.findall(r"\b\w+\b", p)
    meaningful = [w for w in words if len(w) >= 2]
    if len(meaningful) < 2:
        return False, p, "too_short"

    nsfw = _has_word(p, NSFW_WORDS)
    if nsfw:
        return False, p, f"nsfw:{nsfw}"

    hate = _has_word(p, HATE_WORDS)
    if hate:
        return False, p, f"hate:{hate}"

    return True, p, ""


def is_too_short_for_visual(prompt: str) -> bool:
    """Detect if prompt needs auto-enhancement (< 4 meaningful words)."""
    words = re.findall(r"\b\w+\b", prompt or "")
    meaningful = [w for w in words if len(w) >= 2]
    return len(meaningful) < 4


def _llm_complete(model: str, system: str, user: str, timeout: int = 15,
                  temperature: float = 0.7, max_tokens: int = 150) -> str | None:
    """Single chat completion via OpenAI-compatible endpoint."""
    if not PROMPT_LLM_KEY:
        return None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PROMPT_LLM_KEY}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    try:
        r = requests.post(ROUTER, headers=headers, json=payload, timeout=timeout)
        if r.status_code != 200:
            return None
        content = r.json()["choices"][0]["message"]["content"].strip()
        if len(content) < 10 or len(content) > 500:
            return None
        return content.strip('"\'')
    except Exception:
        return None


def auto_enhance_prompt(prompt: str, timeout: int = 15) -> str | None:
    """Expand short prompt into descriptive visual prompt."""
    system = (
        "You are a visual prompt enhancer. The user gave a SHORT prompt in Indonesian or English. "
        "Expand it into a descriptive visual prompt (English, 15-30 words) suitable for AI image gen. "
        "Add: subject details, setting, mood, lighting, style. Keep it tasteful (NO sexual, NO political, NO violence). "
        "Output ONLY the enhanced prompt, no quotes, no preface."
    )
    return _llm_complete(
        PROMPT_ENHANCE_MODEL, system, f"Enhance: {prompt}",
        timeout=timeout, temperature=0.7,
    )


def random_prompt(timeout: int = 15) -> str | None:
    """Generate creative random visual prompt."""
    import random
    themes = [
        "fantasy", "cyberpunk", "anime", "realistic photo", "watercolor",
        "minimalist logo", "Indonesian culture", "nature landscape",
        "cute animal", "food", "futuristic", "vintage", "underwater",
        "space", "magical", "Studio Ghibli style", "Pixar style",
        "Indonesian batik", "tropical beach", "mountain sunrise",
    ]
    theme = random.choice(themes)
    system = (
        "You are a creative AI image prompt generator. "
        "Output ONE detailed visual prompt (English, 15-30 words) suitable for AI image gen. "
        "Include: subject + setting + style + mood + lighting. "
        "Make it interesting, vivid, and TASTEFUL (NO sexual, NO political figures, NO violence). "
        "Output ONLY the prompt text, no quotes, no preface, no numbering."
    )
    return _llm_complete(
        PROMPT_RANDOM_MODEL, system, f"Generate a random {theme} image prompt now.",
        timeout=timeout, temperature=1.0,
    )


def reason_to_friendly(reason: str) -> str:
    """Translate filter reason → friendly Indonesian message."""
    if reason == "empty":
        return "📝 Prompt kosong. Silakan kirim deskripsi gambar terlebih dahulu."
    if reason == "too_short":
        return (
            "📝 Prompt terlalu pendek. Silakan kasih deskripsi visual yang lebih lengkap.\n\n"
            "*Contoh:*\n"
            "• 'kucing oren imut tidur di sofa pink'\n"
            "• 'logo kopi minimalis warna coklat hitam'\n"
            "• 'pemandangan gunung waktu sunrise, gaya anime'"
        )
    if reason.startswith("nsfw:"):
        return (
            "🔞 Prompt mengandung konten dewasa yang tidak didukung.\n\n"
            "Silakan ganti dengan prompt yang aman."
        )
    if reason.startswith("hate:"):
        return "❌ Prompt mengandung konten yang tidak diizinkan."
    return "❌ Prompt tidak valid. Silakan coba prompt lain."


if __name__ == "__main__":
    tests = [
        "musang",
        "cinta damai",
        "kontol ngaceng",
        "tsunade bikini sexy",
        "kucing oren imut tidur di sofa pink",
        "",
        "ab",
    ]
    print("=== Filter test ===")
    for t in tests:
        ok, p, reason = filter_prompt(t)
        print(f"  {ok!s:5} | reason={reason!r:30} | prompt={t!r}")
