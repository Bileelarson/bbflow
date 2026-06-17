"""Telegram bot: Klein Image-Video Generator. PUBLIC mode with free trial + premium plans."""
import asyncio
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

from config import (
    TELEGRAM_BOT_TOKEN as TOKEN,
    ADMIN_IDS,
    QRIS_PATH,
    GEN_IMAGE_PREMIUM_PY as GEN_IMAGE_PY,
    GEN_IMAGE_FREE_PY,
    GEN_VIDEO_PREMIUM_PY as GEN_VIDEO_PY,
    CHECK_BALANCE_PY,
    validate as _validate_config,
)
from leo_backend import load_catalog
import db
from i18n import t, lang_keyboard, detect_lang_from_telegram

logging.basicConfig(format='%(asctime)s [%(name)s] %(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger("kleinbot")

_missing = _validate_config()
if _missing:
    raise SystemExit(f"Missing required env vars: {', '.join(_missing)} — see .env.example")

# Initialize DB on import
db.init_db()
log.info("DB ready")

# Python interpreter for subprocesses (defaults to current). Override with
# BBFLOW_PYTHON_BIN env var if you need a venv-specific binary.
PYTHON_BIN = os.environ.get("BBFLOW_PYTHON_BIN", sys.executable)

# ============== Concurrency Pool ==============
# Hybrid: free user (9router) bisa paralel, premium (Leonardo browser) sequential
# - 9router: ~10MB RAM per gen, no browser → 3 paralel aman
# - Leonardo: ~600MB RAM per browser → 1 at a time
FREE_POOL_SIZE = 3
_free_sem = asyncio.Semaphore(FREE_POOL_SIZE)   # 9router free trial
_premium_lock = asyncio.Lock()                  # Leonardo browser

# Queue tracking — per pool: list of {user_id, started_at}
# Used to compute "posisi #N" message untuk user.
_free_queue: list[dict] = []      # users waiting/running on free pool
_premium_queue: list[dict] = []   # users waiting/running on premium

# Pending captcha challenges {user_id: {"answer": int, "ts": int}}
CAPTCHA: dict[int, dict] = {}
# Pending screenshot waits {user_id: payment_code}
WAIT_SCREENSHOT: dict[int, str] = {}


def _enqueue(queue: list, user_id: int) -> int:
    """Add user to queue, return position (1-indexed)."""
    queue.append({"user_id": user_id, "joined_at": asyncio.get_event_loop().time()})
    return len(queue)


def _dequeue(queue: list, user_id: int):
    """Remove user from queue."""
    for i, item in enumerate(queue):
        if item["user_id"] == user_id:
            queue.pop(i)
            return


def _position(queue: list, user_id: int) -> int:
    """Return user's current 1-indexed position in queue (0 if not found)."""
    for i, item in enumerate(queue):
        if item["user_id"] == user_id:
            return i + 1
    return 0


async def run_subprocess(script: str, env_overrides: dict, timeout: int = 600,
                         pool: str = "premium", on_queue_update=None) -> dict:
    """Run a one-shot gen subprocess, return parsed JSON result.

    Args:
        pool: "free" → use semaphore (3 paralel), "premium" → lock (1 at a time)
        on_queue_update: optional callback(position: int) for live queue updates
    """
    is_free = pool == "free"
    queue = _free_queue if is_free else _premium_queue
    user_id = env_overrides.get("_USER_ID", 0)
    try:
        user_id = int(user_id)
    except Exception:
        user_id = 0

    # Add to queue
    if user_id:
        _enqueue(queue, user_id)

    sem_or_lock = _free_sem if is_free else _premium_lock

    try:
        # Wait for slot
        async with sem_or_lock:
            # Notify user we're starting (position 0 = running)
            if on_queue_update:
                try:
                    await on_queue_update(0)
                except Exception:
                    pass

            env = os.environ.copy()
            env.update({k: str(v) for k, v in env_overrides.items() if not k.startswith("_")})
            log.info(f"subprocess[{pool}]: {script.split('/')[-1]} uid={user_id}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    PYTHON_BIN, "-u", script,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    return {"ok": False, "error": f"timeout {timeout}s"}

                out = stdout.decode("utf-8", "ignore").strip()
                err = stderr.decode("utf-8", "ignore").strip()
                log.info(f"subprocess done: rc={proc.returncode} stdout_lines={len(out.splitlines())}")
                lines = out.splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith("{"):
                        try:
                            return json.loads(line)
                        except Exception:
                            continue
                return {"ok": False, "error": "no JSON in stdout",
                        "stdout": out[-300:], "stderr": err[-300:]}
            except Exception as e:
                return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        # Remove from queue
        if user_id:
            _dequeue(queue, user_id)


# State per user — what they're configuring
SESSIONS: dict[int, dict] = {}

CATALOG = load_catalog()


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def auth(uid: int) -> bool:
    """All authenticated TG users allowed (public bot). Captcha gating happens separately."""
    return True


def auth_check(update: Update) -> bool:
    if not update.effective_user:
        return False
    return auth(update.effective_user.id)


# ============== Captcha ==============

def issue_captcha(uid: int) -> tuple[str, int]:
    """Generate simple math captcha. Returns (question_text, answer)."""
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    op = random.choice(["+", "-"])
    if op == "-" and b > a:
        a, b = b, a
    answer = a + b if op == "+" else a - b
    q = f"{a} {op} {b}"
    CAPTCHA[uid] = {"answer": answer, "ts": int(time.time())}
    return q, answer


def captcha_keyboard(correct: int) -> InlineKeyboardMarkup:
    """Show 6 number buttons, 1 correct + 5 wrong."""
    options = {correct}
    while len(options) < 6:
        options.add(correct + random.randint(-9, 9))
        options.discard(0)
    options = list(options)
    random.shuffle(options)
    rows = []
    for i in range(0, 6, 3):
        row = [InlineKeyboardButton(str(n), callback_data=f"captcha:{n}") for n in options[i:i+3]]
        rows.append(row)
    return InlineKeyboardMarkup(rows)


# ============== Catalogs (UI labels & UUIDs) ==============

ASPECT_RATIOS = [
    ("1:1",   1024, 1024),
    ("2:3",    832, 1248),
    ("3:2",   1248,  832),
    ("4:5",    896, 1152),
    ("5:4",   1152,  896),
    ("16:9",  1408,  800),
    ("9:16",   800, 1408),
    ("4:3",   1184,  864),
    ("3:4",    864, 1184),
]

# Style preset UUIDs (from default style_ids in capture)
# 111dc692-d470-4eec-b791-3475abac4c46 = "Dynamic" (default)
STYLE_PRESETS = [
    ("Dynamic",     "111dc692-d470-4eec-b791-3475abac4c46"),
    ("Cinematic",   "a5632c79-ddd2-4b55-bb20-04eb43c4f0e6"),
    ("Creative",    "6fedbf72-4eb1-4486-87bc-ed95c1c6dab8"),
    ("Fashion",     "67e6dc04-3b9d-46f8-a6b3-7c08bb444e51"),
    ("Portrait",    "ada1492c-2c52-4ad7-9bf8-c4c44a9aa425"),
    ("Stock Photo", "5bdc3f2a-1be6-4d1c-8e77-992a30824a2e"),
    ("Vibrant",     "9d8c6432-ff09-4a98-95dc-2e5f1ae39e54"),
    ("None",        None),
]

QUANTITIES = [1, 2, 3, 4]

# Video motion models — confirmed working format on BASIC plan
VIDEO_MODELS = [
    ("Kling V3 (1080p, audio)",       "kling-3.0"),
    ("Kling V2.5 (1080p)",            "kling-2.5"),
    ("Seedance V2 Pro (HQ)",          "seedance-2.0"),
    ("Seedance V2 Fast (cepat hemat)", "seedance-2.0-fast"),
]

VIDEO_DURATIONS = [3, 4, 5, 6, 8, 10]  # seconds

VIDEO_RESOLUTIONS = [
    ("480p (fast)",  "480p"),
    ("720p (HD)",    "720p"),
    ("1080p (FHD)",  "1080p"),
]

VIDEO_QUANTITIES = [1, 2]

# Top "popular" presets — all confirmed working (Leonardo presets)
POPULAR_MODELS = [
    ("Auto (best for prompt)",      None),
    # 9router Codex — free unlimited, hemat token Leonardo
    ("⚡ GPT-5.4 Image", "__9ROUTER_CODEX__"),
    # Featured (★ in UI)
    ("FLUX.2 Pro ★",                "42588bd1-2f84-40d5-9a81-fcfbe5b37fcc"),
    ("Nano Banana Pro ★",           "59d56042-9c42-4cd9-9bfe-608aa565dd70"),
    ("Nano Banana 2 ★",             "26e4a29a-989c-4708-957a-499abcc901b1"),
    ("GPT Image-2 ★",               "63193f54-0f44-498d-b6ae-881d56fa4f33"),
    ("GPT Image-1.5 ★",             "7ffe4f2b-ec35-40ab-b43f-1f054670d38a"),
    ("Lucid Origin ★",              "3a05363d-18a8-4cfd-8839-50f7fc6d9018"),
    ("Recraft V4 Pro ★",            "b37988eb-e7bb-4457-8ce5-4792bda7a614"),
    ("Recraft V4 ★",                "5b294f1a-fa0b-40cc-b24e-7d6f60783248"),
    ("Seedream 4.5 ★",              "9006ed45-40fa-4210-9aaf-99481fc95488"),
    # Standard models
    ("Phoenix 1.0",                 "372b997f-0041-4a79-8ae2-0e7d490c1ba5"),
    ("Phoenix 0.9",                 "4423342b-b8fd-400a-99e9-c06b748f7a3b"),
    ("Lucid Realism",               "b7e44f0e-a0dc-42fb-87c9-f861567085bd"),
    ("FLUX Dev",                    "b6685533-26a9-448d-be9c-d3879bddb12a"),
    ("FLUX Schnell",                "ab6b674e-2c60-466a-8be5-801fe345db87"),
    ("FLUX.1 Kontext",              "905c14dc-e4fc-49a0-befb-fd1615022242"),
    ("FLUX.1 Kontext Max",          "202d5a51-a696-433f-a6ce-170892ce954d"),
    ("Ideogram 3.0",                "e78212a0-4cfb-4337-8680-bf25f67ad20b"),
    ("Seedream 4.0",                "7e5ff500-3d59-48c1-8df5-e02ce740adf9"),
    ("Nano Banana",                 "af3189d3-4619-477d-a3e5-4f076a86e2eb"),
    ("GPT Image-1",                 "6df03351-1cef-47d4-a913-cd92a7d8b67b"),
    ("BBFlow Lightning",          "8a1d0979-42a5-419e-842d-5dcbb6c1ba75"),
    # Style-focused presets
    ("Anime",                       "c157fc16-6144-4ff4-8582-56edfc682a7b"),
    ("Cinematic Kino",              "cf548be8-5349-4eaf-a8bf-f82597ffed6b"),
    ("Concept Art",                 "aff3f8b9-b417-4783-b9fc-4eb8f2c3cae2"),
    ("Graphic Design",              "67a4f3ee-c05a-4a5d-aaa8-f1015a08cf73"),
    ("Illustrative Albedo",         "6a17eb6e-386b-4be1-955c-25c7bfc0428c"),
    ("Lifelike Vision",             "fecc9f8b-711c-40fb-804f-bb42de380cc8"),
    ("Portrait Perfect",            "b386a587-01c0-4b30-a71d-635df5b57981"),
    ("Stock Photography",           "7e4cd4eb-95f4-4255-a37f-d22e9b1e7caa"),
]


def fresh_session(uid: int, kind: str = "image") -> dict:
    SESSIONS[uid] = {
        "kind": kind,
        "prompt": "",
        # Image fields
        "model": ("Auto (best for prompt)", None),
        "ar": ASPECT_RATIOS[0],     # 1:1
        "style": STYLE_PRESETS[0],   # Dynamic
        "quantity": 4,
        # Video fields
        "video_model":      VIDEO_MODELS[0],   # Kling V3
        "video_duration":   5,
        "video_resolution": ("1080p (FHD)", "1080p"),
        "video_audio":      True,
        "video_quantity":   1,
        "video_ar":         ASPECT_RATIOS[0],  # 1:1 default
    }
    return SESSIONS[uid]


def s(uid: int) -> dict:
    if uid not in SESSIONS:
        fresh_session(uid)
    return SESSIONS[uid]


# ============== Keyboards ==============

def menu_main(uid: int) -> InlineKeyboardMarkup:
    sess = s(uid)
    is_free_user = not is_admin(uid) and not db.is_premium(uid)
    prompt_empty = t(uid, "btn_prompt_empty")

    if sess["kind"] == "video":
        rows = [
            [
                InlineKeyboardButton(t(uid, "btn_image"), callback_data="kind:image"),
                InlineKeyboardButton(t(uid, "btn_video") + " ✓", callback_data="kind:video"),
            ],
            [InlineKeyboardButton(f"🎬 Model: {sess['video_model'][0]}", callback_data="open:vmodel")],
            [InlineKeyboardButton(f"📐 Aspect: {sess['video_ar'][0]} ({sess['video_ar'][1]}x{sess['video_ar'][2]})", callback_data="open:var")],
            [InlineKeyboardButton(f"⏱️ Duration: {sess['video_duration']}s", callback_data="open:vdur")],
            [InlineKeyboardButton(f"🎯 Resolution: {sess['video_resolution'][0]}", callback_data="open:vres")],
            [
                InlineKeyboardButton(f"🔊 Audio: {'ON' if sess['video_audio'] else 'OFF'}", callback_data="toggle:vaudio"),
                InlineKeyboardButton(f"🔢 Qty: {sess['video_quantity']}", callback_data="open:vqty"),
            ],
            [InlineKeyboardButton(f"📝 Prompt: {(sess['prompt'] or prompt_empty)[:30]}", callback_data="info:prompt")],
            [InlineKeyboardButton(t(uid, "btn_generate_video"), callback_data="action:gen_video")],
        ]
        # Cek Token ONLY for admin
        if is_admin(uid):
            rows.append([InlineKeyboardButton(t(uid, "btn_balance"), callback_data="action:balance"),
                         InlineKeyboardButton(t(uid, "btn_reset"), callback_data="action:reset")])
        else:
            rows.append([InlineKeyboardButton(t(uid, "btn_reset"), callback_data="action:reset")])
    elif is_free_user:
        # Free trial — minimalist UI: prompt + GENERATE only
        rows = [
            [InlineKeyboardButton(t(uid, "btn_free_trial_label"), callback_data="info:freetrial")],
            [InlineKeyboardButton(f"📝 Prompt: {(sess['prompt'] or prompt_empty)[:30]}", callback_data="info:prompt")],
            [InlineKeyboardButton(t(uid, "btn_random_gen"), callback_data="action:random_gen")],
            [InlineKeyboardButton(t(uid, "btn_generate_image"), callback_data="action:generate")],
            [InlineKeyboardButton(t(uid, "btn_upgrade_premium"), callback_data="action:upgrade_btn"),
             InlineKeyboardButton(t(uid, "btn_reset"), callback_data="action:reset")],
        ]
    else:
        # Premium / admin — full picker UI
        kind_label = "Video" if sess["kind"] == "video" else "Image"
        gen_label = t(uid, "btn_generate_video") if sess["kind"] == "video" else t(uid, "btn_generate_image")
        rows = [
            [
                InlineKeyboardButton(t(uid, "btn_image") + (" ✓" if sess["kind"] == "image" else ""), callback_data="kind:image"),
                InlineKeyboardButton(t(uid, "btn_video") + (" ✓" if sess["kind"] == "video" else ""), callback_data="kind:video"),
            ],
            [InlineKeyboardButton(f"🤖 Model: {sess['model'][0]}", callback_data="open:model")],
            [InlineKeyboardButton(f"📐 Aspect: {sess['ar'][0]} ({sess['ar'][1]}x{sess['ar'][2]})", callback_data="open:ar")],
            [InlineKeyboardButton(f"🎨 Style: {sess['style'][0]}", callback_data="open:style")],
            [InlineKeyboardButton(f"🔢 Quantity: {sess['quantity']}", callback_data="open:qty")],
            [InlineKeyboardButton(f"📝 Prompt: {(sess['prompt'] or prompt_empty)[:30]}", callback_data="info:prompt")],
        ]
        # Random prompt khusus mode image
        if sess["kind"] == "image":
            rows.append([InlineKeyboardButton(t(uid, "btn_random_gen"), callback_data="action:random_gen")])
        rows.append([InlineKeyboardButton(gen_label, callback_data="action:generate")])
        # Cek Token ONLY for admin
        if is_admin(uid):
            rows.append([InlineKeyboardButton(t(uid, "btn_balance"), callback_data="action:balance"),
                         InlineKeyboardButton(t(uid, "btn_reset"), callback_data="action:reset")])
        else:
            rows.append([InlineKeyboardButton(t(uid, "btn_reset"), callback_data="action:reset")])
    # Always add language toggle as last row
    rows.append([InlineKeyboardButton(t(uid, "btn_lang"), callback_data="lang:open")])
    return InlineKeyboardMarkup(rows)


def menu_choices(items: list[tuple], prefix: str, cols: int = 2, back_cb: str = "open:main") -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, item in enumerate(items):
        label = item[0] if isinstance(item, tuple) else str(item)
        row.append(InlineKeyboardButton(label[:35], callback_data=f"{prefix}:{i}"))
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


# ============== Handlers ==============

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        return
    u = update.effective_user
    uid = u.id
    # Register/update user in DB
    is_new_user = db.get_user(uid) is None
    db.upsert_user(uid, u.username, u.first_name)
    # Auto-detect lang from Telegram on first contact
    if is_new_user:
        detected = detect_lang_from_telegram(getattr(u, "language_code", None))
        db.set_lang(uid, detected)
    fresh_session(uid)

    # Parse referral payload from /start <payload>
    # Format: ref_<referrer_id>
    if is_new_user and not is_admin(uid) and ctx.args:
        payload = ctx.args[0].strip()
        if payload.startswith("ref_"):
            try:
                referrer_id = int(payload[4:])
                if db.record_referral(referrer_id, uid):
                    log.info(f"Referral recorded: {referrer_id} → {uid}")
            except (ValueError, Exception) as e:
                log.warning(f"Bad referral payload: {payload!r} ({e})")

    # Admin bypass captcha
    if is_admin(uid):
        await update.message.reply_text(
            t(uid, "start_admin"),
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )
        return

    # Captcha gate
    if not db.captcha_passed(uid):
        q, ans = issue_captcha(uid)
        await update.message.reply_text(
            t(uid, "start_captcha", q=q),
            parse_mode="Markdown",
            reply_markup=captcha_keyboard(ans),
        )
        return

    # Already verified — show main UI
    user = db.get_user(uid)
    is_prem = db.is_premium(uid)
    if is_prem and user.get("expires_at"):
        from datetime import datetime
        exp = datetime.fromtimestamp(user["expires_at"]).strftime("%d %b %Y")
        plan_label = t(uid, "plan_premium_until", date=exp)
    else:
        plan_label = t(uid, "plan_free")

    free_status = ""
    if not is_prem:
        remaining = db.free_trial_remaining(uid)
        if remaining <= 0:
            free_status = t(uid, "free_trial_exhausted")
        else:
            free_status = t(uid, "free_trial_remaining_line", remaining=remaining)

    await update.message.reply_text(
        t(uid, "start_welcome_main", plan_label=plan_label, free_status=free_status),
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    await update.message.reply_text(
        t(uid, "help_text"),
        parse_mode="Markdown",
    )


async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Toggle UI language between Indonesian and English."""
    if not auth_check(update): return
    u = update.effective_user
    uid = u.id
    # Make sure user exists in DB so set_lang works
    if db.get_user(uid) is None:
        db.upsert_user(uid, u.username, u.first_name)
    await update.message.reply_text(
        t(uid, "lang_picker"),
        parse_mode="Markdown",
        reply_markup=lang_keyboard(),
    )


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text(t(uid, "verify_first"))
        return
    await update.message.reply_text(
        t(uid, "menu_panel"),
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    fresh_session(uid)
    await update.message.reply_text(
        t(uid, "session_reset"),
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
    )


async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin only — Leonardo token balance."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text(t(uid, "admin_only_long"))
        return
    msg = await update.message.reply_text(t(uid, "balance_loading"), parse_mode="Markdown")
    res = await run_subprocess(CHECK_BALANCE_PY, {}, timeout=120, pool="premium")
    if res.get("ok"):
        await msg.edit_text(
            t(uid, "balance_block",
              username=res.get('username','?'),
              plan=res.get('plan','?'),
              tokens=res['tokens'],
              stream=res['stream'],
              gpt=res.get('gpt',0),
              renewal=res.get('renewal','?')[:10]),
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text(t(uid, "error_label", err=res.get('error')), parse_mode="Markdown")


async def cmd_image(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text(t(uid, "verify_first"))
        return
    sess = s(uid)
    sess["kind"] = "image"

    is_free_user = not is_admin(uid) and not db.is_premium(uid)
    if is_free_user:
        # Free user — auto mode, no menu, just instructions
        await update.message.reply_text(
            t(uid, "image_free_intro"),
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )
    else:
        # Premium/admin — full menu
        await update.message.reply_text(
            t(uid, "image_premium_intro"),
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )


async def cmd_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text(t(uid, "verify_first"))
        return
    if not db.is_premium(uid):
        await update.message.reply_text(
            t(uid, "video_premium_only"),
            parse_mode="Markdown",
        )
        return
    sess = s(uid)
    sess["kind"] = "video"
    await update.message.reply_text(
        t(uid, "video_intro"),
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
    )


async def cmd_ref(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User: /ref - show referral link + stats."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text(t(uid, "verify_first_short"))
        return

    bot_username = (await ctx.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    stats_data = db.referral_stats(uid)
    user = db.get_user(uid)
    bonus_total = (user.get("bonus_trials", 0) if user else 0) or 0

    await update.message.reply_text(
        t(uid, "ref_block",
          total=stats_data['total'],
          granted=stats_data['granted'],
          pending=stats_data['pending'],
          bonus=bonus_total,
          br=db.REFERRAL_BONUS_REFERRER,
          bi=db.REFERRAL_BONUS_INVITED,
          link=ref_link),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show user plan + session config."""
    if not auth_check(update): return
    uid = update.effective_user.id
    user = db.get_user(uid) or db.upsert_user(uid, update.effective_user.username, update.effective_user.first_name)

    is_prem = db.is_premium(uid)
    if is_admin(uid):
        plan_str = t(uid, "status_admin")
    elif is_prem:
        from datetime import datetime
        exp = datetime.fromtimestamp(user["expires_at"]).strftime("%d %b %Y %H:%M")
        plan_str = t(uid, "status_premium_label", plan=user['plan'].upper(), exp=exp)
    else:
        used_label = t(uid, "status_free_used") if user.get("free_used") else t(uid, "status_free_unused")
        plan_str = t(uid, "status_free_label", used=used_label)

    info = t(uid, "status_block",
             uid=uid,
             plan_str=plan_str,
             gen_count=user.get('gen_count', 0))
    if not is_prem and not is_admin(uid):
        info += t(uid, "status_upgrade_hint")
    await update.message.reply_text(info, parse_mode="Markdown")


# ============== Premium / Payment Commands ==============

async def cmd_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show plan options."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text(t(uid, "verify_first"))
        return

    rows = [
        [InlineKeyboardButton(t(uid, "upgrade_btn_weekly"),  callback_data="upgrade:weekly")],
        [InlineKeyboardButton(t(uid, "upgrade_btn_monthly"), callback_data="upgrade:monthly")],
        [InlineKeyboardButton(t(uid, "upgrade_btn_cancel"),  callback_data="upgrade:cancel")],
    ]
    await update.message.reply_text(
        t(uid, "upgrade_intro"),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def cmd_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User pakai /pay <code> untuk attach bukti screenshot."""
    if not auth_check(update): return
    uid = update.effective_user.id
    args = ctx.args
    if not args:
        # Show pending payment if any
        pending = db.get_pending_payment_for_user(uid)
        if pending:
            from datetime import datetime
            req = datetime.fromtimestamp(pending["requested_at"]).strftime("%d %b %H:%M")
            sshot_status = t(uid, "screenshot_uploaded") if pending["screenshot_id"] else t(uid, "screenshot_missing")
            await update.message.reply_text(
                t(uid, "pay_pending_block",
                  code=pending['code'],
                  plan=pending['plan'],
                  amount=pending['amount'],
                  sshot=sshot_status,
                  req=req),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                t(uid, "pay_no_pending"),
                parse_mode="Markdown",
            )
        return

    code = args[0].strip().upper()
    p = db.get_payment(code)
    if not p:
        await update.message.reply_text(t(uid, "pay_code_not_found", code=code), parse_mode="Markdown")
        return
    if p["user_id"] != uid:
        await update.message.reply_text(t(uid, "pay_code_not_yours"))
        return
    if p["status"] != "pending":
        await update.message.reply_text(t(uid, "pay_code_already", status=p['status']), parse_mode="Markdown")
        return

    WAIT_SCREENSHOT[uid] = code
    await update.message.reply_text(
        t(uid, "pay_send_screenshot", code=code, amount=p['amount']),
        parse_mode="Markdown",
    )


async def cmd_redeem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin-only: manually redeem code without screenshot (test/promo)."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🔒 Admin only")
        return
    args = ctx.args
    if len(args) < 1:
        await update.message.reply_text("Usage: `/redeem <code>`", parse_mode="Markdown")
        return
    code = args[0].strip().upper()
    user = db.approve_payment(code, uid)
    if user:
        await update.message.reply_text(
            f"✅ Redeemed `{code}` for user `{user['user_id']}`\n"
            f"Plan: {user['plan']}, expires: <t:{user['expires_at']}:F>",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Code not found or already processed")


# ============== Admin Commands ==============

async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: show pending payments awaiting approval."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🔒 Admin only")
        return
    pending = db.list_pending_payments(20)
    if not pending:
        await update.message.reply_text("✅ Tidak ada pending payment")
        return

    lines = [f"💳 *{len(pending)} Pending Payment(s)*", "━━━━━━━━━━━━━━━━━━━━━", ""]
    from datetime import datetime
    for p in pending:
        req = datetime.fromtimestamp(p["requested_at"]).strftime("%d/%m %H:%M")
        uname = f"@{p['username']}" if p['username'] else (p.get('first_name') or 'no-username')
        lines.append(
            f"🔑 `{p['code']}`\n"
            f"   👤 {uname} (ID: `{p['user_id']}`)\n"
            f"   💰 Rp {p['amount']:,} ({p['plan']})\n"
            f"   🕐 {req}\n"
            f"   ✓ `/approve {p['code']}`\n"
            f"   ✗ `/reject {p['code']} alasan`\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: approve payment by code."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🔒 Admin only")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: `/approve <code>`", parse_mode="Markdown")
        return
    code = ctx.args[0].strip().upper()
    user = db.approve_payment(code, uid)
    if not user:
        await update.message.reply_text(f"❌ Code `{code}` not pending or not found", parse_mode="Markdown")
        return

    from datetime import datetime
    exp = datetime.fromtimestamp(user["expires_at"]).strftime("%d %b %Y %H:%M")
    await update.message.reply_text(
        f"✅ APPROVED `{code}`\n\n"
        f"User: `{user['user_id']}`\n"
        f"Plan: {user['plan']}\n"
        f"Expires: {exp}",
        parse_mode="Markdown",
    )
    # Notify user
    try:
        await ctx.bot.send_message(
            user["user_id"],
            f"🎉 *PREMIUM AKTIF!* 🎉\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 Kode: `{code}`\n"
            f"💎 Plan: *{user['plan'].upper()}*\n"
            f"📅 Expires: *{exp}*\n\n"
            f"Silakan gunakan /image atau /video. 🚀",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.warning(f"failed notify user {user['user_id']}: {e}")


async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: reject payment by code."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🔒 Admin only")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: `/reject <code> [reason]`", parse_mode="Markdown")
        return
    code = ctx.args[0].strip().upper()
    reason = " ".join(ctx.args[1:]) or "no reason"
    p = db.get_payment(code)
    if not db.reject_payment(code, uid, reason):
        await update.message.reply_text(f"❌ Code `{code}` not pending or not found", parse_mode="Markdown")
        return
    await update.message.reply_text(f"✅ REJECTED `{code}`\nReason: _{reason}_", parse_mode="Markdown")
    if p:
        try:
            await ctx.bot.send_message(
                p["user_id"],
                f"❌ *Payment Ditolak*\n\n"
                f"🔑 Kode: `{code}`\n"
                f"📝 Alasan: _{reason}_\n\n"
                f"Coba lagi /upgrade atau hubungi admin.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: bot statistics."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🔒 Admin only")
        return
    s = db.stats()
    success_rate = round(s['gen_success'] / s['gen_total'] * 100, 1) if s['gen_total'] > 0 else 0
    await update.message.reply_text(
        f"📊 *BBFlow — Statistics*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *USERS* ({s['users_total']:,} total)\n"
        f"  • Premium aktif:    {s['users_premium']:,}\n"
        f"  • Trial dipakai:    {s['users_free_used']:,}\n"
        f"  • Trial habis (3x): {s['users_trial_full']:,}\n"
        f"  • Captcha lulus:    {s['users_captcha']:,}\n\n"
        f"📈 *NEW USERS*\n"
        f"  • Hari ini:    +{s['users_today']:,}\n"
        f"  • 7 hari:      +{s['users_week']:,}\n"
        f"  • 30 hari:     +{s['users_month']:,}\n\n"
        f"⚡ *ACTIVE USERS*\n"
        f"  • 24 jam:      {s['users_active_24h']:,}\n"
        f"  • 7 hari:      {s['users_active_7d']:,}\n\n"
        f"🎨 *GENERATIONS* ({s['gen_total']:,} total)\n"
        f"  • Image:       {s['gen_image']:,}\n"
        f"  • Video:       {s['gen_video']:,}\n"
        f"  • Hari ini:    {s['gen_today']:,}\n"
        f"  • Success rate: {success_rate}% ({s['gen_success']:,}/{s['gen_total']:,})\n"
        f"  • Failed:      {s['gen_failed']:,}\n\n"
        f"💰 *REVENUE*\n"
        f"  • Total:       Rp {s['revenue_idr']:,}\n"
        f"  • 30 hari:     Rp {s['revenue_month']:,}\n"
        f"  • Approved:    {s['approved_pay']:,}\n"
        f"  • Pending:     {s['pending_pay']:,}\n"
        f"  • Rejected:    {s['rejected_pay']:,}\n"
        f"  • Conv rate:   {s['conv_rate']}%\n\n"
        f"📋 *Quick Commands*\n"
        f"  • /pending — payment menunggu\n"
        f"  • /users — list user terbaru\n",
        parse_mode="Markdown",
    )


async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: list 20 users terbaru with usage detail."""
    if not auth_check(update): return
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🔒 Admin only")
        return

    args = ctx.args
    limit = 20
    if args:
        try:
            limit = max(1, min(100, int(args[0])))
        except ValueError:
            pass

    users = db.list_users_recent(limit=limit)
    if not users:
        await update.message.reply_text("📭 Belum ada user.")
        return

    import datetime
    lines = [f"👥 {len(users)} User Terbaru", "━━━━━━━━━━━━━━━━━━━━━", ""]

    for i, u in enumerate(users, 1):
        # Use plain text — username/name often contain _ * [ ] which break Markdown
        uname = f"@{u['username']}" if u['username'] else (u['first_name'] or "(no name)")
        joined = datetime.datetime.fromtimestamp(u['created_at']).strftime("%d %b %H:%M")
        plan = u['plan'].upper() if u['plan'] != 'free' else 'FREE'
        if u['plan'] != 'free' and u['expires_at']:
            exp_dt = datetime.datetime.fromtimestamp(u['expires_at'])
            expired = exp_dt < datetime.datetime.now()
            plan_label = f"❌ {plan} (exp)" if expired else f"💎 {plan}"
        else:
            plan_label = f"🆓 FREE ({u['free_used']}/{db.FREE_TRIAL_LIMIT})"

        lines.append(
            f"{i}. {uname} [{u['user_id']}]\n"
            f"   {plan_label} | gen: {u['gen_count']} | {joined}"
        )

    lines.append("")
    lines.append(f"Showing {len(users)} of {db.stats()['users_total']} total")
    lines.append("Pakai /users 50 untuk lebih banyak (max 100).")

    msg = "\n".join(lines)
    # Telegram message max ~4000 chars
    if len(msg) > 3900:
        msg = msg[:3900] + "\n\n(truncated, gunakan limit lebih kecil)"

    # Send as PLAIN TEXT — no Markdown — to avoid parse errors with _ * [ ] in usernames
    await update.message.reply_text(msg)


async def post_init(application: Application):
    """Set bot commands menu (slash menu)."""
    public_commands = [
        BotCommand("start",   "🚀 Mulai / restart bot"),
        BotCommand("image",   "🖼️ Generate gambar"),
        BotCommand("video",   "🎬 Generate video (premium)"),
        BotCommand("ref",     "🎁 Invite teman, dapat bonus trial"),
        BotCommand("upgrade", "💎 Beli premium plan"),
        BotCommand("pay",     "📸 Upload bukti transfer"),
        BotCommand("status",  "📊 Cek paket Anda"),
        BotCommand("menu",    "⚙️ Buka panel kontrol"),
        BotCommand("reset",   "🔄 Reset session"),
        BotCommand("lang",    "🌐 Bahasa / Language"),
        BotCommand("help",    "📖 Help & dokumentasi"),
    ]
    await application.bot.set_my_commands(public_commands)
    # Admin gets extra commands in their scope
    from telegram import BotCommandScopeChat
    admin_commands = public_commands + [
        BotCommand("pending",  "🔔 List pending payments"),
        BotCommand("approve",  "✅ Approve payment"),
        BotCommand("reject",   "❌ Reject payment"),
        BotCommand("redeem",   "🎁 Manual redeem"),
        BotCommand("stats",    "📈 Bot statistics"),
        BotCommand("users",    "👥 List user terbaru"),
        BotCommand("balance",  "💰 Token engine"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(admin_id))
        except Exception as e:
            log.warning(f"failed set admin commands for {admin_id}: {e}")
    log.info(f"Slash menu registered (public={len(public_commands)}, admin={len(admin_commands)})")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id

    # Gate captcha
    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text(
            "🤖 Silakan verifikasi via /start terlebih dahulu",
            parse_mode="Markdown",
        )
        return

    sess = s(uid)
    sess["prompt"] = update.message.text.strip()
    await update.message.reply_text(
        f"📝 Prompt diset:\n_{sess['prompt']}_\n\n"
        f"Tap *GENERATE* untuk mulai 🚀",
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
    )


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Receive payment proof screenshot."""
    if not auth_check(update): return
    uid = update.effective_user.id

    code = WAIT_SCREENSHOT.get(uid)
    if not code:
        await update.message.reply_text(
            "📸 _Foto diterima, tapi gak ada konteks._\n\n"
            "Mau upload bukti transfer? Pakai: `/pay <kode>` terlebih dahulu.\n"
            "Belum punya kode? `/upgrade`",
            parse_mode="Markdown",
        )
        return

    # Get largest photo size
    file_id = update.message.photo[-1].file_id
    if db.attach_screenshot(code, file_id):
        WAIT_SCREENSHOT.pop(uid, None)
        p = db.get_payment(code)
        await update.message.reply_text(
            f"✅ *Screenshot Diterima!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 Kode: `{code}`\n"
            f"💰 Rp {p['amount']:,}\n\n"
            f"⏳ _Admin akan cek dalam 1-12 jam_\n"
            f"_Anda akan menerima notifikasi setelah disetujui._\n\n"
            f"Cek status: /status",
            parse_mode="Markdown",
        )
        # Notify admins
        u = update.effective_user
        uname = f"@{u.username}" if u.username else (u.first_name or "no-username")
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id,
                )
                await ctx.bot.send_message(
                    admin_id,
                    f"🔔 *NEW PAYMENT*\n\n"
                    f"🔑 `{code}`\n"
                    f"👤 {uname} (`{uid}`)\n"
                    f"📋 Plan: *{p['plan']}*\n"
                    f"💰 Rp {p['amount']:,}\n\n"
                    f"✅ Approve:\n`/approve {code}`\n\n"
                    f"❌ Reject:\n`/reject {code} alasan`",
                    parse_mode="Markdown",
                )
            except Exception as e:
                log.warning(f"failed notify admin {admin_id}: {e}")
    else:
        await update.message.reply_text(
            "❌ Gagal attach screenshot. Coba `/pay <kode>` ulang.",
            parse_mode="Markdown",
        )


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        await update.callback_query.answer("⛔ Denied", show_alert=True)
        return

    q = update.callback_query
    uid = q.from_user.id
    sess = s(uid)
    data = q.data

    await q.answer()

    # ============== Language toggle ==============
    if data == "lang:open":
        await q.edit_message_text(
            t(uid, "lang_picker"),
            parse_mode="Markdown",
            reply_markup=lang_keyboard(),
        )
        return
    if data == "lang:id" or data == "lang:en":
        new_lang = data.split(":", 1)[1]
        # Make sure user row exists
        if db.get_user(uid) is None:
            db.upsert_user(uid, q.from_user.username, q.from_user.first_name)
        db.set_lang(uid, new_lang)
        confirm_key = "lang_set_id" if new_lang == "id" else "lang_set_en"
        await q.edit_message_text(
            t(uid, confirm_key),
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )
        return

    # ============== Captcha ==============
    if data.startswith("captcha:"):
        try:
            picked = int(data.split(":", 1)[1])
        except ValueError:
            return
        challenge = CAPTCHA.get(uid)
        if not challenge:
            await q.edit_message_text(t(uid, "captcha_expired"))
            return
        if picked == challenge["answer"]:
            db.mark_captcha_passed(uid)
            CAPTCHA.pop(uid, None)

            # Grant referral bonus if this user was invited
            ref_result = db.grant_referral_bonus(uid)
            ref_msg = ""
            if ref_result:
                referrer_id, ref_count = ref_result
                ref_msg = t(uid, "captcha_referral_bonus", n=db.REFERRAL_BONUS_INVITED)
                # Notif referrer
                try:
                    await ctx.bot.send_message(
                        referrer_id,
                        t(referrer_id, "referrer_notif", n=db.REFERRAL_BONUS_REFERRER, count=ref_count),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    log.warning(f"Failed notif referrer {referrer_id}: {e}")

            total_trials = db.free_trial_remaining(uid)
            await q.edit_message_text(
                t(uid, "captcha_verified", trials=total_trials, ref_msg=ref_msg),
                parse_mode="Markdown",
                reply_markup=lang_keyboard(),
            )
        else:
            q2, ans = issue_captcha(uid)
            await q.edit_message_text(
                t(uid, "captcha_wrong", q=q2),
                parse_mode="Markdown",
                reply_markup=captcha_keyboard(ans),
            )
        return

    # ============== Upgrade flow ==============
    if data.startswith("upgrade:"):
        choice = data.split(":", 1)[1]
        if choice == "cancel":
            await q.edit_message_text(t(uid, "upgrade_cancel"))
            return
        if choice not in ("weekly", "monthly"):
            return
        # Create payment record
        p = db.create_payment_request(uid, choice)
        plan_label = t(uid, "plan_label_weekly") if choice == "weekly" else t(uid, "plan_label_monthly")

        # Edit current message to confirmation
        await q.edit_message_text(
            t(uid, "payment_created", code=p['code'], plan_label=plan_label, amount=p['amount']),
            parse_mode="Markdown",
        )

        # Send QRIS image
        if QRIS_PATH.exists():
            with open(QRIS_PATH, "rb") as f:
                await ctx.bot.send_photo(
                    chat_id=q.message.chat.id,
                    photo=f,
                    caption=t(uid, "qris_caption", amount=p['amount'], code=p['code']),
                    parse_mode="Markdown",
                )
        else:
            await ctx.bot.send_message(
                chat_id=q.message.chat.id,
                text=t(uid, "qris_unset", code=p['code']),
                parse_mode="Markdown",
            )
        return

    if data == "open:main":
        await q.edit_message_text(t(uid, "menu_panel_short"), reply_markup=menu_main(uid))

    elif data.startswith("kind:"):
        kind = data.split(":", 1)[1]
        sess["kind"] = kind
        await q.edit_message_text(
            t(uid, "mode_video_active") if kind == "video" else t(uid, "mode_image_active"),
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )

    # ====== Video pickers ======
    elif data == "open:vmodel":
        await q.edit_message_text(
            t(uid, "open_vmodel_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(VIDEO_MODELS, "set:vmodel", cols=1)
        )

    elif data == "open:var":
        await q.edit_message_text(
            t(uid, "open_var_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(ASPECT_RATIOS, "set:var", cols=3)
        )

    elif data == "open:vdur":
        items = [(f"{d}s", d) for d in VIDEO_DURATIONS]
        await q.edit_message_text(
            t(uid, "open_vdur_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(items, "set:vdur", cols=3)
        )

    elif data == "open:vres":
        await q.edit_message_text(
            t(uid, "open_vres_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(VIDEO_RESOLUTIONS, "set:vres", cols=1)
        )

    elif data == "open:vqty":
        items = [(str(n), n) for n in VIDEO_QUANTITIES]
        await q.edit_message_text(
            t(uid, "open_vqty_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(items, "set:vqty", cols=2)
        )

    elif data == "toggle:vaudio":
        sess["video_audio"] = not sess["video_audio"]
        await q.edit_message_text(
            t(uid, "audio_toggled", state="ON" if sess["video_audio"] else "OFF"),
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )

    elif data.startswith("set:vmodel:"):
        idx = int(data.split(":")[2])
        sess["video_model"] = VIDEO_MODELS[idx]
        await q.edit_message_text(t(uid, "set_video_model", val=sess['video_model'][0]),
                                    parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data.startswith("set:var:"):
        idx = int(data.split(":")[2])
        sess["video_ar"] = ASPECT_RATIOS[idx]
        await q.edit_message_text(t(uid, "set_video_ar", val=sess['video_ar'][0]),
                                    parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data.startswith("set:vdur:"):
        idx = int(data.split(":")[2])
        sess["video_duration"] = VIDEO_DURATIONS[idx]
        await q.edit_message_text(t(uid, "set_video_dur", val=sess['video_duration']),
                                    parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data.startswith("set:vres:"):
        idx = int(data.split(":")[2])
        sess["video_resolution"] = VIDEO_RESOLUTIONS[idx]
        await q.edit_message_text(t(uid, "set_video_res", val=sess['video_resolution'][0]),
                                    parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data.startswith("set:vqty:"):
        idx = int(data.split(":")[2])
        sess["video_quantity"] = VIDEO_QUANTITIES[idx]
        await q.edit_message_text(t(uid, "set_video_qty", val=sess['video_quantity']),
                                    parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data == "open:model":
        await q.edit_message_text(
            t(uid, "open_model_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(POPULAR_MODELS, "set:model", cols=1)
        )

    elif data == "open:ar":
        await q.edit_message_text(
            t(uid, "open_ar_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(ASPECT_RATIOS, "set:ar", cols=3)
        )

    elif data == "open:style":
        await q.edit_message_text(
            t(uid, "open_style_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices(STYLE_PRESETS, "set:style", cols=2)
        )

    elif data == "open:qty":
        await q.edit_message_text(
            t(uid, "open_qty_title"),
            parse_mode="Markdown",
            reply_markup=menu_choices([(str(n),) for n in QUANTITIES], "set:qty", cols=4)
        )

    elif data.startswith("set:model:"):
        idx = int(data.split(":")[2])
        sess["model"] = POPULAR_MODELS[idx]
        await q.edit_message_text(t(uid, "set_model", val=sess['model'][0]), parse_mode="Markdown",
                                    reply_markup=menu_main(uid))

    elif data.startswith("set:ar:"):
        idx = int(data.split(":")[2])
        sess["ar"] = ASPECT_RATIOS[idx]
        await q.edit_message_text(t(uid, "set_ar", val=sess['ar'][0]), parse_mode="Markdown",
                                    reply_markup=menu_main(uid))

    elif data.startswith("set:style:"):
        idx = int(data.split(":")[2])
        sess["style"] = STYLE_PRESETS[idx]
        await q.edit_message_text(t(uid, "set_style", val=sess['style'][0]), parse_mode="Markdown",
                                    reply_markup=menu_main(uid))

    elif data.startswith("set:qty:"):
        idx = int(data.split(":")[2])
        sess["quantity"] = QUANTITIES[idx]
        await q.edit_message_text(t(uid, "set_qty", val=sess['quantity']), parse_mode="Markdown",
                                    reply_markup=menu_main(uid))

    elif data == "info:prompt":
        await q.message.reply_text(t(uid, "info_prompt_send"))

    elif data == "info:freetrial":
        await q.message.reply_text(
            t(uid, "info_freetrial_block"),
            parse_mode="Markdown",
        )

    elif data == "action:upgrade_btn":
        # Trigger /upgrade flow programmatically
        rows = [
            [InlineKeyboardButton(t(uid, "upgrade_btn_weekly"),  callback_data="upgrade:weekly")],
            [InlineKeyboardButton(t(uid, "upgrade_btn_monthly"), callback_data="upgrade:monthly")],
            [InlineKeyboardButton(t(uid, "upgrade_btn_cancel"),  callback_data="upgrade:cancel")],
        ]
        await q.message.reply_text(
            t(uid, "upgrade_intro"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    elif data == "action:reset":
        fresh_session(uid)
        await q.edit_message_text(t(uid, "session_reset_short"), reply_markup=menu_main(uid))

    elif data == "action:balance":
        m = await q.message.reply_text(t(uid, "balance_loading_short"))
        res = await run_subprocess(CHECK_BALANCE_PY, {}, timeout=120, pool="premium")
        if res.get("ok"):
            await m.edit_text(
                t(uid, "balance_short", tokens=res['tokens'], stream=res['stream'], plan=res['plan']),
                parse_mode="Markdown"
            )
        else:
            await m.edit_text(t(uid, "error_label", err=res.get('error')))

    elif data == "action:random_gen":
        # Random prompt → auto-fill session prompt → re-emit action:generate flow
        from prompt_filter import random_prompt as gen_random_prompt

        loading = await q.message.reply_text(
            t(uid, "random_loading"),
            parse_mode="Markdown",
        )
        try:
            new_prompt = await asyncio.get_event_loop().run_in_executor(
                None, gen_random_prompt, 12
            )
        except Exception as e:
            new_prompt = None
            log.warning(f"random_prompt failed: {e}")

        try:
            await loading.delete()
        except Exception:
            pass

        if not new_prompt:
            await q.message.reply_text(t(uid, "random_failed"))
            return

        # Update session
        sess["prompt"] = new_prompt
        await q.message.reply_text(
            t(uid, "random_success", prompt=new_prompt),
            parse_mode="Markdown",
        )
        # Fall-through to action:generate by re-firing logic
        # Simulate by re-invoking ourselves with action:generate semantics
        # Use a synthetic data variable to reuse code path
        data = "action:generate"
        # Continue to action:generate block below

    if data == "action:generate":
        if not sess["prompt"]:
            await q.message.reply_text(t(uid, "no_prompt"))
            return

        # Pre-filter prompt (NSFW/hate/too_short)
        from prompt_filter import filter_prompt, is_too_short_for_visual, auto_enhance_prompt, reason_to_friendly
        allowed, sanitized, fr_reason = filter_prompt(sess["prompt"])
        if not allowed:
            await q.message.reply_text(
                reason_to_friendly(fr_reason),
                parse_mode="Markdown",
            )
            return

        # Gate: free trial check
        if not is_admin(uid) and not db.is_premium(uid):
            allowed_trial, reason = db.can_use_free_trial(uid)
            if not allowed_trial:
                await q.message.reply_text(
                    t(uid, "trial_exhausted_block"),
                    parse_mode="Markdown",
                )
                return

        # Rate limit
        ok, wait = db.check_rate_limit(uid, cooldown_seconds=30)
        if not ok:
            await q.message.reply_text(t(uid, "rate_limit", wait=wait))
            return

        # Auto-enhance for free user with short prompt
        is_free_user = not is_admin(uid) and not db.is_premium(uid)
        prompt_to_use = sanitized
        was_enhanced = False
        if is_free_user and is_too_short_for_visual(sanitized):
            enh_msg = await q.message.reply_text(
                t(uid, "enhancing"),
                parse_mode="Markdown",
            )
            try:
                enhanced = await asyncio.get_event_loop().run_in_executor(
                    None, auto_enhance_prompt, sanitized, 12
                )
                if enhanced:
                    prompt_to_use = enhanced
                    was_enhanced = True
            except Exception:
                pass
            try:
                await enh_msg.delete()
            except Exception:
                pass

        # Determine pool + initial queue position
        pool = "free" if is_free_user else "premium"
        active_queue = _free_queue if is_free_user else _premium_queue
        queued_now = len(active_queue)
        if is_free_user:
            est_position = max(0, queued_now + 1 - FREE_POOL_SIZE)
        else:
            est_position = max(0, queued_now)

        progress_text = t(uid, "gen_progress_header", prompt=prompt_to_use[:80])
        if was_enhanced:
            progress_text += t(uid, "gen_enhanced_line")

        # Add queue indicator
        if est_position > 0:
            eta_min = est_position * (1.5 if is_free_user else 0.5)
            progress_text += t(uid, "gen_queue_line", pos=est_position, eta=eta_min)
        progress_text += "\n"

        # Branch: free user → 9router auto, premium/admin → Leonardo full menu
        if is_free_user:
            progress_text += t(uid, "gen_free_engine_line")
        else:
            progress_text += t(uid, "gen_premium_engine_line",
                               model=sess['model'][0],
                               ar=sess['ar'][0], w=sess['ar'][1], h=sess['ar'][2],
                               style=sess['style'][0],
                               qty=sess['quantity'])

        progress = await q.message.reply_text(progress_text, parse_mode="Markdown")

        # Live queue update callback
        async def on_q_update(pos):
            try:
                if pos == 0:
                    new_text = progress_text.replace(
                        t(uid, "gen_queue_line", pos=est_position,
                          eta=est_position * (1.5 if is_free_user else 0.5)),
                        t(uid, "gen_starting_now"),
                    )
                    await progress.edit_text(new_text, parse_mode="Markdown")
            except Exception:
                pass

        # Run with pool routing
        is_codex_model = (not is_free_user) and sess["model"][1] == "__9ROUTER_CODEX__"
        if is_free_user or is_codex_model:
            # GPT-5.4 API only supports n=1 per request → script loops sequential.
            # Free user: always 1 (trial limit). Premium codex: respect sess qty.
            qty = 1 if is_free_user else sess["quantity"]
            # ~60-120s per image → bump timeout for multi-gen
            free_timeout = max(300, 150 * qty)
            res = await run_subprocess(GEN_IMAGE_FREE_PY, {
                "LEO_PROMPT":   prompt_to_use,
                "LEO_QUANTITY": qty,
                "_USER_ID":     uid,
            }, timeout=free_timeout, pool="free", on_queue_update=on_q_update)
        else:
            res = await run_subprocess(GEN_IMAGE_PY, {
                "LEO_PROMPT":   prompt_to_use,
                "LEO_PRESET":   sess["model"][1] or "",
                "LEO_STYLE":    sess["style"][1] or "",
                "LEO_WIDTH":    sess["ar"][1],
                "LEO_HEIGHT":   sess["ar"][2],
                "LEO_QUANTITY": sess["quantity"],
                "_USER_ID":     uid,
            }, timeout=300, pool="premium", on_queue_update=on_q_update)

        # Record generation in DB
        db.record_generation(
            uid, "image", sess["prompt"],
            res.get("gen_id"),
            "success" if res.get("ok") else "failed",
            res.get("error") if not res.get("ok") else None,
        )

        if not res.get("ok"):
            await progress.edit_text(t(uid, "gen_failed", err=res.get('error')))
            return

        files = res.get("files", [])
        if not files:
            await progress.edit_text(t(uid, "gen_no_files"))
            return

        # Mark free trial as used (only for non-premium non-admin)
        if not is_admin(uid) and not db.is_premium(uid):
            db.mark_free_used(uid)

        # Send as media group (up to 10 photos per group)
        if len(files) > 1:
            media = [InputMediaPhoto(open(f, "rb")) for f in files[:10]]
            media[0].caption = t(uid, "gen_caption_multi", n=len(files), prompt=sess['prompt'][:120])
            media[0].parse_mode = "Markdown"
            await q.message.reply_media_group(media)
        else:
            with open(files[0], "rb") as f:
                await q.message.reply_photo(
                    photo=f,
                    caption=t(uid, "gen_caption_single", prompt=sess['prompt'][:120]),
                    parse_mode="Markdown",
                )

        # Trial used hint
        if not is_admin(uid) and not db.is_premium(uid):
            await q.message.reply_text(
                t(uid, "trial_used_hint"),
                parse_mode="Markdown",
            )

        await progress.delete()

    elif data == "action:gen_video":
        if not sess["prompt"]:
            await q.message.reply_text(t(uid, "no_prompt"))
            return

        # Gate: video is premium-only
        if not is_admin(uid) and not db.is_premium(uid):
            await q.message.reply_text(
                t(uid, "video_premium_only_short"),
                parse_mode="Markdown",
            )
            return

        # Rate limit
        ok, wait = db.check_rate_limit(uid, cooldown_seconds=30)
        if not ok:
            await q.message.reply_text(t(uid, "rate_limit", wait=wait))
            return

        progress = await q.message.reply_text(
            t(uid, "video_gen_progress",
              prompt=sess['prompt'][:80],
              model=sess['video_model'][0],
              ar=sess['video_ar'][0], w=sess['video_ar'][1], h=sess['video_ar'][2],
              dur=sess['video_duration'],
              res=sess['video_resolution'][0],
              audio="ON" if sess['video_audio'] else "OFF",
              qty=sess['video_quantity']),
            parse_mode="Markdown"
        )

        # Map UI model slug to motionModel ENUM
        motion_model_map = {
            "kling-3.0":         "KLING3_0",
            "kling-2.5":         "KLING2_5",
            "seedance-2.0":      "SEEDANCE2_0",
            "seedance-2.0-fast": "SEEDANCE2_0FAST",
        }
        motion_slug = sess["video_model"][1]
        motion_enum = motion_model_map.get(motion_slug, "KLING3_0")

        res = await run_subprocess(GEN_VIDEO_PY, {
            "LEO_PROMPT":       sess["prompt"],
            "LEO_MOTION_MODEL": motion_slug,
            "LEO_MOTION_ENUM":  motion_enum,
            "LEO_DURATION":     sess["video_duration"],
            "LEO_RESOLUTION":   sess["video_resolution"][1],
            "LEO_AUDIO":        "1" if sess["video_audio"] else "0",
            "LEO_QUANTITY":     sess["video_quantity"],
            "_USER_ID":         uid,
        }, timeout=600, pool="premium")

        # Record generation in DB
        db.record_generation(
            uid, "video", sess["prompt"],
            res.get("gen_id"),
            "success" if res.get("ok") else "failed",
            res.get("error") if not res.get("ok") else None,
        )

        if not res.get("ok"):
            await progress.edit_text(t(uid, "gen_failed", err=res.get('error')))
            return

        files = res.get("files", [])
        if not files:
            await progress.edit_text(t(uid, "video_no_files"))
            return

        # Send video files
        for i, f in enumerate(files):
            with open(f, "rb") as fh:
                caption = t(uid, "video_caption_first",
                            i=i+1, n=len(files),
                            model=sess['video_model'][0],
                            dur=sess['video_duration'],
                            res=sess['video_resolution'][1],
                            prompt=sess['prompt'][:100]) if i == 0 else None
                await q.message.reply_video(
                    video=fh,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

        await progress.delete()


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Update %s caused error: %s", update, ctx.error)


def main():
    log.info("Starting BBFlow (subprocess mode)...")

    # concurrent_updates=True — proses banyak user paralel (TANPA ini, semua user antri 1-by-1!)
    # Bot pakai async semaphore di run_subprocess() untuk control real concurrency.
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("menu",    cmd_menu))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("image",   cmd_image))
    app.add_handler(CommandHandler("video",   cmd_video))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("ref",     cmd_ref))
    app.add_handler(CommandHandler("lang",    cmd_lang))
    # Premium / payment
    app.add_handler(CommandHandler("upgrade", cmd_upgrade))
    app.add_handler(CommandHandler("pay",     cmd_pay))
    app.add_handler(CommandHandler("redeem",  cmd_redeem))
    # Admin
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject",  cmd_reject))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("users",   cmd_users))
    # Callbacks + content
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    log.info("Bot polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
