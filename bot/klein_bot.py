"""Telegram bot: BBFlow Multimodal (Chat, Image, Video). PUBLIC mode."""
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

db.init_db()
log.info("DB ready")

PYTHON_BIN = os.environ.get("IMAJIN_PYTHON_BIN", sys.executable)

FREE_POOL_SIZE = 3
_free_sem = asyncio.Semaphore(FREE_POOL_SIZE)   
_premium_lock = asyncio.Lock()                  

_free_queue: list[dict] = []      
_premium_queue: list[dict] = []   

CAPTCHA: dict[int, dict] = {}
WAIT_SCREENSHOT: dict[int, str] = {}


def _enqueue(queue: list, user_id: int) -> int:
    queue.append({"user_id": user_id, "joined_at": asyncio.get_event_loop().time()})
    return len(queue)

def _dequeue(queue: list, user_id: int):
    for i, item in enumerate(queue):
        if item["user_id"] == user_id:
            queue.pop(i)
            return

def _position(queue: list, user_id: int) -> int:
    for i, item in enumerate(queue):
        if item["user_id"] == user_id:
            return i + 1
    return 0


async def run_subprocess(script: str, env_overrides: dict, timeout: int = 600,
                         pool: str = "premium", on_queue_update=None) -> dict:
    is_free = pool == "free"
    queue = _free_queue if is_free else _premium_queue
    user_id = env_overrides.get("_USER_ID", 0)
    try:
        user_id = int(user_id)
    except Exception:
        user_id = 0

    if user_id:
        _enqueue(queue, user_id)

    sem_or_lock = _free_sem if is_free else _premium_lock

    try:
        async with sem_or_lock:
            if on_queue_update:
                try:
                    await on_queue_update(0)
                except Exception:
                    pass

            env = os.environ.copy()
            env.update({k: str(v) for k, v in env_overrides.items() if not k.startswith("_")})
            
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
        if user_id:
            _dequeue(queue, user_id)


SESSIONS: dict[int, dict] = {}
CATALOG = load_catalog()

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def auth(uid: int) -> bool:
    return True

def auth_check(update: Update) -> bool:
    if not update.effective_user:
        return False
    return auth(update.effective_user.id)


def issue_captcha(uid: int) -> tuple[str, int]:
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

VIDEO_MODELS = [
    ("Kling V3 (1080p, audio)",       "kling-3.0"),
    ("Kling V2.5 (1080p)",            "kling-2.5"),
    ("Seedance V2 Pro (HQ)",          "seedance-2.0"),
    ("Seedance V2 Fast",              "seedance-2.0-fast"),
]

VIDEO_DURATIONS = [3, 4, 5, 6, 8, 10] 
VIDEO_RESOLUTIONS = [("480p (fast)", "480p"), ("720p (HD)", "720p"), ("1080p (FHD)", "1080p")]
VIDEO_QUANTITIES = [1, 2]

POPULAR_MODELS = [
    ("Auto (best for prompt)",      None),
    ("⚡ GPT-5.4 Image", "__9ROUTER_CODEX__"),
    ("FLUX.2 Pro ★",                "42588bd1-2f84-40d5-9a81-fcfbe5b37fcc"),
    ("Nano Banana Pro ★",           "59d56042-9c42-4cd9-9bfe-608aa565dd70"),
    ("Recraft V4 Pro ★",            "b37988eb-e7bb-4457-8ce5-4792bda7a614"),
    ("FLUX Dev",                    "b6685533-26a9-448d-be9c-d3879bddb12a"),
]

def fresh_session(uid: int, kind: str = "chat") -> dict:
    # Le bot démarre désormais en mode CHAT par défaut
    SESSIONS[uid] = {
        "kind": kind,
        "prompt": "",
        "model": ("Auto (best for prompt)", None),
        "ar": ASPECT_RATIOS[0],     
        "style": STYLE_PRESETS[0],   
        "quantity": 4,
        "video_model":      VIDEO_MODELS[0],   
        "video_duration":   5,
        "video_resolution": ("1080p (FHD)", "1080p"),
        "video_audio":      True,
        "video_quantity":   1,
        "video_ar":         ASPECT_RATIOS[0],  
    }
    return SESSIONS[uid]


def s(uid: int) -> dict:
    if uid not in SESSIONS:
        fresh_session(uid)
    return SESSIONS[uid]


def menu_main(uid: int) -> InlineKeyboardMarkup:
    sess = s(uid)
    is_free_user = not is_admin(uid) and not db.is_premium(uid)
    prompt_empty = "(empty - send text)"

    # LIGNE DE NAVIGATION PRINCIPALE (CHAT / IMAGE / VIDEO)
    nav_row = [
        InlineKeyboardButton("💬 Chat" + (" ✓" if sess["kind"] == "chat" else ""), callback_data="kind:chat"),
        InlineKeyboardButton("🖼️ Image" + (" ✓" if sess["kind"] == "image" else ""), callback_data="kind:image"),
        InlineKeyboardButton("🎬 Video" + (" ✓" if sess["kind"] == "video" else ""), callback_data="kind:video"),
    ]

    # --- MODE CHAT ---
    if sess["kind"] == "chat":
        rows = [nav_row]
        if is_admin(uid):
            rows.append([InlineKeyboardButton("💰 Token Balance", callback_data="action:balance"), InlineKeyboardButton("🔄 Reset", callback_data="action:reset")])
        else:
            rows.append([InlineKeyboardButton("💎 Upgrade", callback_data="action:upgrade_btn"), InlineKeyboardButton("🔄 Reset", callback_data="action:reset")])
        return InlineKeyboardMarkup(rows)

    # --- MODE VIDEO ---
    elif sess["kind"] == "video":
        rows = [
            nav_row,
            [InlineKeyboardButton(f"🎬 Model: {sess['video_model'][0]}", callback_data="open:vmodel")],
            [InlineKeyboardButton(f"📐 Aspect: {sess['video_ar'][0]} ({sess['video_ar'][1]}x{sess['video_ar'][2]})", callback_data="open:var")],
            [InlineKeyboardButton(f"⏱️ Duration: {sess['video_duration']}s", callback_data="open:vdur")],
            [InlineKeyboardButton(f"🎯 Resolution: {sess['video_resolution'][0]}", callback_data="open:vres")],
            [
                InlineKeyboardButton(f"🔊 Audio: {'ON' if sess['video_audio'] else 'OFF'}", callback_data="toggle:vaudio"),
                InlineKeyboardButton(f"🔢 Qty: {sess['video_quantity']}", callback_data="open:vqty"),
            ],
            [InlineKeyboardButton(f"📝 Prompt: {(sess['prompt'] or prompt_empty)[:30]}", callback_data="info:prompt")],
            [InlineKeyboardButton("🚀 GENERATE VIDEO", callback_data="action:gen_video")],
        ]
        if is_admin(uid):
            rows.append([InlineKeyboardButton("💰 Token Balance", callback_data="action:balance"), InlineKeyboardButton("🔄 Reset", callback_data="action:reset")])
        else:
            rows.append([InlineKeyboardButton("🔄 Reset", callback_data="action:reset")])
        return InlineKeyboardMarkup(rows)

    # --- MODE IMAGE ---
    else:
        rows = [
            nav_row,
            [InlineKeyboardButton(f"🤖 Model: {sess['model'][0]}", callback_data="open:model")],
            [InlineKeyboardButton(f"📐 Aspect: {sess['ar'][0]} ({sess['ar'][1]}x{sess['ar'][2]})", callback_data="open:ar")],
            [InlineKeyboardButton(f"🎨 Style: {sess['style'][0]}", callback_data="open:style")],
            [InlineKeyboardButton(f"🔢 Quantity: {sess['quantity']}", callback_data="open:qty")],
            [InlineKeyboardButton(f"📝 Prompt: {(sess['prompt'] or prompt_empty)[:30]}", callback_data="info:prompt")],
            [InlineKeyboardButton("🚀 GENERATE IMAGE", callback_data="action:generate")]
        ]
        if is_admin(uid):
            rows.append([InlineKeyboardButton("💰 Token Balance", callback_data="action:balance"), InlineKeyboardButton("🔄 Reset", callback_data="action:reset")])
        else:
            rows.append([InlineKeyboardButton("🔄 Reset", callback_data="action:reset")])
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


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    u = update.effective_user
    uid = u.id
    db.upsert_user(uid, u.username, u.first_name)
    db.set_lang(uid, "en") # Force English
    fresh_session(uid, kind="chat") # Start in Chat Mode

    if is_admin(uid):
        await update.message.reply_text(
            "✨ *BBFlow — ADMIN MODE* ✨\n━━━━━━━━━━━━━━━━━━━━━\n_Unlimited generation for admin._ 👑",
            parse_mode="Markdown",
            reply_markup=menu_main(uid),
        )
        return

    if not db.captcha_passed(uid):
        q, ans = issue_captcha(uid)
        await update.message.reply_text(f"👋 *Welcome to BBFlow!*\n\n🤖 _Verify you're human_\n*What is:* `{q}` *?*", parse_mode="Markdown", reply_markup=captcha_keyboard(ans))
        return

    await update.message.reply_text(
        "✨ *BBFlow* ✨\n━━━━━━━━━━━━━━━━━━━━━\n_Ready! Select a mode below._ 🚀",
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
    )

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    await update.message.reply_text("⚙️ *Control Panel*", parse_mode="Markdown", reply_markup=menu_main(uid))

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update): return
    uid = update.effective_user.id
    fresh_session(uid)
    await update.message.reply_text("🔄 *Session reset.*", parse_mode="Markdown", reply_markup=menu_main(uid))

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """C'est ici que la magie de l'IA Textuelle (Chat) opère"""
    if not auth_check(update): return
    uid = update.effective_user.id

    if not is_admin(uid) and not db.captcha_passed(uid):
        await update.message.reply_text("🤖 Please verify via /start first", parse_mode="Markdown")
        return

    sess = s(uid)
    user_text = update.message.text.strip()

    # --- 1. MODE CHAT (La nouveauté) ---
    if sess["kind"] == "chat":
        # On affiche un message d'attente
        loading_msg = await update.message.reply_text("💬 _Thinking..._", parse_mode="Markdown")
        
        # Fonction pour appeler ton compte Anything AI
        def call_chat_api(text):
            import requests
            api_key = os.environ.get("OPENAI_API_KEY")
            api_base = os.environ.get("OPENAI_BASE_URL", "https://api.anything.ai/v1").rstrip('/')
            
            try:
                res = requests.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-3.5-turbo", # Modèle standard par défaut
                        "messages": [{"role": "user", "content": text}]
                    },
                    timeout=30
                )
                res.raise_for_status()
                return res.json()["choices"][0]["message"]["content"]
            except Exception as e:
                return f"❌ Connection Error (Check API keys): {str(e)}"

        # On exécute l'appel à l'IA en arrière-plan
        response = await asyncio.get_event_loop().run_in_executor(None, call_chat_api, user_text)
        
        # On remplace le "Thinking..." par la vraie réponse (Sans format Markdown pour éviter les crashs)
        await loading_msg.edit_text(response)
        return

    # --- 2. MODE IMAGE OU VIDEO (L'ancien comportement) ---
    sess["prompt"] = user_text
    mode_emoji = "🖼️" if sess["kind"] == "image" else "🎬"
    
    await update.message.reply_text(
        f"📝 Prompt saved for {mode_emoji} {sess['kind'].capitalize()}:\n_{sess['prompt']}_\n\n"
        f"Tap *GENERATE* to start 🚀",
        parse_mode="Markdown",
        reply_markup=menu_main(uid),
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

    if data.startswith("kind:"):
        kind = data.split(":", 1)[1]
        sess["kind"] = kind
        msgs = {
            "chat": "💬 *Chat Mode*\n_Type any message to talk to the AI._",
            "image": "🖼️ *Image Mode*\n_Send text to describe your image._",
            "video": "🎬 *Video Mode*\n_Send text to describe your video._"
        }
        await q.edit_message_text(msgs.get(kind, ""), parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data == "open:main":
        await q.edit_message_text("⚙️ Menu:", reply_markup=menu_main(uid))

    elif data == "open:vmodel":
        await q.edit_message_text("🎬 *Choose Video Model*", parse_mode="Markdown", reply_markup=menu_choices(VIDEO_MODELS, "set:vmodel", cols=1))
    elif data == "open:var":
        await q.edit_message_text("📐 *Choose Video Aspect Ratio*", parse_mode="Markdown", reply_markup=menu_choices(ASPECT_RATIOS, "set:var", cols=3))
    elif data == "open:vdur":
        items = [(f"{d}s", d) for d in VIDEO_DURATIONS]
        await q.edit_message_text("⏱️ *Choose Duration*", parse_mode="Markdown", reply_markup=menu_choices(items, "set:vdur", cols=3))
    elif data == "open:vres":
        await q.edit_message_text("🎯 *Choose Resolution*", parse_mode="Markdown", reply_markup=menu_choices(VIDEO_RESOLUTIONS, "set:vres", cols=1))
    elif data == "open:vqty":
        items = [(str(n), n) for n in VIDEO_QUANTITIES]
        await q.edit_message_text("🔢 *Choose Quantity*", parse_mode="Markdown", reply_markup=menu_choices(items, "set:vqty", cols=2))
    elif data == "toggle:vaudio":
        sess["video_audio"] = not sess["video_audio"]
        await q.edit_message_text("🔊 Audio toggled", parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data.startswith("set:vmodel:"):
        idx = int(data.split(":")[2])
        sess["video_model"] = VIDEO_MODELS[idx]
        await q.edit_message_text(f"✅ Video Model: *{sess['video_model'][0]}*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:var:"):
        idx = int(data.split(":")[2])
        sess["video_ar"] = ASPECT_RATIOS[idx]
        await q.edit_message_text(f"✅ Video Aspect: *{sess['video_ar'][0]}*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:vdur:"):
        idx = int(data.split(":")[2])
        sess["video_duration"] = VIDEO_DURATIONS[idx]
        await q.edit_message_text(f"✅ Duration: *{sess['video_duration']}s*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:vres:"):
        idx = int(data.split(":")[2])
        sess["video_resolution"] = VIDEO_RESOLUTIONS[idx]
        await q.edit_message_text(f"✅ Resolution: *{sess['video_resolution'][0]}*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:vqty:"):
        idx = int(data.split(":")[2])
        sess["video_quantity"] = VIDEO_QUANTITIES[idx]
        await q.edit_message_text(f"✅ Quantity: *{sess['video_quantity']}*", parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data == "open:model":
        await q.edit_message_text("🤖 *Choose Model*", parse_mode="Markdown", reply_markup=menu_choices(POPULAR_MODELS, "set:model", cols=1))
    elif data == "open:ar":
        await q.edit_message_text("📐 *Choose Aspect Ratio*", parse_mode="Markdown", reply_markup=menu_choices(ASPECT_RATIOS, "set:ar", cols=3))
    elif data == "open:style":
        await q.edit_message_text("🎨 *Choose Style Preset*", parse_mode="Markdown", reply_markup=menu_choices(STYLE_PRESETS, "set:style", cols=2))
    elif data == "open:qty":
        await q.edit_message_text("🔢 *Choose Quantity*", parse_mode="Markdown", reply_markup=menu_choices([(str(n),) for n in QUANTITIES], "set:qty", cols=4))

    elif data.startswith("set:model:"):
        idx = int(data.split(":")[2])
        sess["model"] = POPULAR_MODELS[idx]
        await q.edit_message_text(f"✅ Model: *{sess['model'][0]}*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:ar:"):
        idx = int(data.split(":")[2])
        sess["ar"] = ASPECT_RATIOS[idx]
        await q.edit_message_text(f"✅ Aspect: *{sess['ar'][0]}*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:style:"):
        idx = int(data.split(":")[2])
        sess["style"] = STYLE_PRESETS[idx]
        await q.edit_message_text(f"✅ Style: *{sess['style'][0]}*", parse_mode="Markdown", reply_markup=menu_main(uid))
    elif data.startswith("set:qty:"):
        idx = int(data.split(":")[2])
        sess["quantity"] = QUANTITIES[idx]
        await q.edit_message_text(f"✅ Quantity: *{sess['quantity']}*", parse_mode="Markdown", reply_markup=menu_main(uid))

    elif data == "action:reset":
        fresh_session(uid, kind=sess["kind"])
        await q.edit_message_text("🔄 Session reset.", reply_markup=menu_main(uid))

    elif data == "action:balance":
        m = await q.message.reply_text("💰 Checking balance...")
        res = await run_subprocess(CHECK_BALANCE_PY, {}, timeout=120, pool="premium")
        if res.get("ok"):
            await m.edit_text(f"💰 Image tokens: *{res['tokens']:,}*\n📺 Stream: {res['stream']:,}\n💎 Plan: {res['plan']}", parse_mode="Markdown")
        else:
            await m.edit_text(f"❌ Error: {res.get('error')}")

    if data == "action:generate":
        if not sess["prompt"]:
            await q.message.reply_text("⚠️ Please send a text prompt first.")
            return

        progress = await q.message.reply_text(f"🚀 *Generating Image...*\n\n📝 _{sess['prompt'][:80]}_", parse_mode="Markdown")

        async def on_q_update(pos):
            pass

        res = await run_subprocess(GEN_IMAGE_FREE_PY, {
            "LEO_PROMPT":   sess["prompt"],
            "LEO_QUANTITY": 1,
            "_USER_ID":     uid,
        }, timeout=300, pool="free", on_queue_update=on_q_update)

        if not res.get("ok"):
            await progress.edit_text(f"❌ Failed: {res.get('error')}")
            return

        files = res.get("files", [])
        if not files:
            await progress.edit_text("⚠️ No files returned.")
            return

        with open(files[0], "rb") as f:
            await q.message.reply_photo(photo=f, caption=f"✅ Generated\n📝 _{sess['prompt'][:120]}_", parse_mode="Markdown")
        await progress.delete()

    elif data == "action:gen_video":
        if not sess["prompt"]:
            await q.message.reply_text("⚠️ Please send a text prompt first.")
            return

        progress = await q.message.reply_text(f"🚀 *Generating Video...*\n\n📝 _{sess['prompt'][:80]}_", parse_mode="Markdown")

        res = await run_subprocess(GEN_VIDEO_PY, {
            "LEO_PROMPT":       sess["prompt"],
            "LEO_MOTION_MODEL": sess["video_model"][1],
            "LEO_DURATION":     sess["video_duration"],
            "LEO_RESOLUTION":   sess["video_resolution"][1],
            "LEO_AUDIO":        "1" if sess["video_audio"] else "0",
            "LEO_QUANTITY":     sess["video_quantity"],
            "_USER_ID":         uid,
        }, timeout=600, pool="premium")

        if not res.get("ok"):
            await progress.edit_text(f"❌ Failed: {res.get('error')}")
            return

        files = res.get("files", [])
        if not files:
            await progress.edit_text("⚠️ No files returned.")
            return

        for i, f in enumerate(files):
            with open(f, "rb") as fh:
                await q.message.reply_video(video=fh)

        await progress.delete()

def main():
    log.info("Starting BBFlow Bot...")
    app = Application.builder().token(TOKEN).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("menu",    cmd_menu))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    log.info("Bot polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
