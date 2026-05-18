# Imajin AI Bot

Public Telegram bot SaaS skeleton — **free trial + premium plan** gating, payment flow, multi-language (ID/EN), referral bonuses, and a pluggable image/video generation engine.

This repo is the **engine-agnostic kerangka**. The free tier ships wired to any OpenAI-compatible image API (default: a local proxy). The premium tier is a stub — drop in your own provider (Leonardo, Midjourney, OpenAI, Replicate, etc.) by editing 4 small Python files.

## Features

- 🆓 **Free trial**: per-user trial counter (default 2), captcha gate, optional referral bonus
- 💎 **Premium plan**: SQLite-backed users + manual QRIS payment flow with admin approval
- 🌐 **Multi-language**: full ID/EN i18n with auto-detect from Telegram `language_code`
- 🎨 **Image gen**: free tier via OpenAI-compatible `/v1/images/generations` (SSE + b64)
- 🎬 **Video gen**: premium tier hook (stub — wire your provider)
- ✨ **Prompt enhancer + random**: short prompts auto-expanded by an LLM (configurable model)
- 🚫 **Prompt filter**: NSFW + hate keyword block (Indonesian + English)
- 👨‍💼 **Admin commands**: balance check, payment approve/reject, user lookup, broadcast
- 🤝 **Referrals**: `/start <code>` invite tracking with bonus trials for both inviter & invitee
- ⚙️ **Pluggable engine**: 4 stub scripts you can swap (free image, premium image, premium video, balance check)

## Quick start

```bash
# 1. Clone + install deps
git clone https://github.com/Khimsaja/imajin-ai-bot.git
cd imajin-ai-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set:
#   TELEGRAM_BOT_TOKEN=...           (from @BotFather)
#   ADMIN_TELEGRAM_IDS=123456789     (your Telegram user_id)
#   FREE_API_BASE / FREE_API_KEY     (any OpenAI-compatible image endpoint)

# 3. Run
python3 bot/klein_bot.py

# Or with PM2
pm2 start ecosystem.config.js
```

The bot creates `data/users.db` on first run.

## Repo layout

```
imajin-ai-bot/
├── bot/
│   ├── klein_bot.py          # main entrypoint — Telegram handlers, plan gating, flow
│   ├── config.py             # env-var driven config (TOKEN, ADMIN_IDS, paths)
│   ├── db.py                 # SQLite — users, payments, referrals, queue
│   ├── i18n.py               # ID/EN string table + per-user language preference
│   ├── prompt_filter.py      # NSFW/hate filter + LLM auto-enhance + random prompt
│   ├── gen_image_free.py     # FREE tier image gen (OpenAI-compatible API)
│   ├── gen_image_one.py      # PREMIUM image gen — STUB, wire your provider
│   ├── gen_video_one.py      # PREMIUM video gen — STUB, wire your provider
│   ├── check_balance_one.py  # PREMIUM balance check — STUB, wire your provider
│   └── leo_backend.py        # Premium catalog loader (model/preset list)
├── assets/
│   ├── bot_logo.jpg
│   └── QRIS_PLACEHOLDER.txt  # drop your own qris.jpg here for QRIS payment flow
├── ecosystem.config.js       # PM2 process definition
├── requirements.txt
├── .env.example
└── README.md
```

Runtime files are created under `data/` (gitignored): `data/users.db`, `data/out/`, `data/catalog/`.

## Configuration

All config is environment-driven. See `.env.example` for the full list. Key vars:

| Var | What | Required |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | ✅ |
| `ADMIN_TELEGRAM_IDS` | Comma-separated TG user_ids that can run admin commands | ✅ |
| `FREE_API_BASE` | OpenAI-compatible image API base URL | for free tier |
| `FREE_API_KEY` | Bearer token for the free-tier engine | for free tier |
| `FREE_IMAGE_MODEL` | Model id sent in the `model` field | for free tier |
| `PROMPT_LLM_*` | Chat-completions endpoint for prompt enhance + random | optional |

## Wiring a premium engine

The premium tier subprocesses out to four scripts. Each receives parameters via env vars and emits a single JSON line to stdout. Replace these with your provider.

```python
# bot/gen_image_one.py — premium image
# Input env: LEO_PROMPT, LEO_QUANTITY, LEO_MODEL, LEO_STYLE, LEO_WIDTH, LEO_HEIGHT
# Output JSON: {"ok": true, "gen_id": "...", "files": ["/abs/img.png"], "prompt": "..."}

# bot/gen_video_one.py — premium video
# Input env: LEO_PROMPT, LEO_VIDEO_MODEL, LEO_DURATION, LEO_ASPECT
# Output JSON: {"ok": true, "gen_id": "...", "files": ["/abs/video.mp4"], "prompt": "..."}

# bot/check_balance_one.py — quota / balance
# Output JSON: {"ok": true, "balance": {"tokens": 14600, "renew_at": "..."}}
```

The catalog (model & style preset list shown to premium users) lives at `data/catalog/`:

```
data/catalog/models_clean.json   # [{"id": "flux-dev", "name": "FLUX.1 Dev"}, ...]
data/catalog/presets_clean.json  # [{"id": "anime-v2", "name": "Anime"}, ...]
```

Empty catalog is fine — the bot falls back to hardcoded defaults inside `klein_bot.py` (`POPULAR_MODELS`, `STYLE_PRESETS`, `VIDEO_MODELS`).

## Payment flow

The bot ships with a manual QRIS payment flow:

1. User picks a plan (e.g. 50k IDR / month, 150k IDR / 3 months — configurable in `i18n.py`)
2. Bot sends QRIS image (`assets/qris.jpg`) + unique payment code (e.g. `IMAJIN-A1B2-C3D4`)
3. User pays + sends screenshot
4. Admin runs `/approve <code>` or `/reject <code> <reason>`
5. On approve, plan is activated for the user, expiry tracked

To use, drop your real QRIS PNG at `assets/qris.jpg`. The placeholder is gitignored.

## Admin commands

- `/balance` — premium engine balance check
- `/approve <code>` — approve a pending payment
- `/reject <code> <reason>` — reject with note to user
- `/pending` — list pending payments
- `/users` — list all users
- `/find <id|username>` — lookup user
- `/grant <id> <plan> <days>` — manually grant a plan
- `/broadcast <message>` — send to all users

## Internationalization

`bot/i18n.py` holds a translation table:

```python
TEXTS = {
    "welcome_free": {"id": "Selamat datang...", "en": "Welcome..."},
    ...
}
```

User language is auto-detected from `update.effective_user.language_code` on first contact and persisted in the `users` table. Users can change it later via `/lang`. Admin-facing strings stay in Indonesian.

When adding a new string, **always add both `id` and `en` keys** — the bot raises if a key is missing.

## Security notes

- `.env` is gitignored — never commit your bot token or API keys
- `data/users.db` is gitignored — never commit user data
- `assets/qris.jpg` is gitignored — that's your real payment QR
- Admin user IDs are in env, not hardcoded
- The repo includes **no real provider code for premium engines**, only stubs

## License

MIT — see [LICENSE](LICENSE).

## Author

[@Khimsaja](https://github.com/Khimsaja)
