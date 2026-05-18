"""i18n module for Imajin AI bot — Indonesian + English.

Usage:
    from i18n import t, lang_keyboard
    await update.message.reply_text(t(uid, "start_welcome", remaining=2), parse_mode="Markdown")
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import db


TEXTS = {
    # ============================== START / WELCOME ==============================
    "start_admin": {
        "id": (
            "✨ *Imajin AI — ADMIN MODE* ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "_Unlimited generation untuk admin._ 👑\n\n"
            "🖼️  /image — Image Mode\n"
            "🎬  /video — Video Mode\n"
            "📊  /stats — Bot statistics\n"
            "💳  /pending — Pending payments\n"
            "💰  /balance — Cek token engine\n\n"
            "💡 _Ketik / buat liat semua command_"
        ),
        "en": (
            "✨ *Imajin AI — ADMIN MODE* ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "_Unlimited generation for admin._ 👑\n\n"
            "🖼️  /image — Image Mode\n"
            "🎬  /video — Video Mode\n"
            "📊  /stats — Bot statistics\n"
            "💳  /pending — Pending payments\n"
            "💰  /balance — Engine token balance\n\n"
            "💡 _Type / to see all commands_"
        ),
    },
    "start_captcha": {
        "id": (
            "👋 *Welcome ke Imajin AI!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 _Verifikasi human terlebih dahulu_\n\n"
            "*Berapa hasil:* `{q}` *?*\n\n"
            "_Tap angka yang bener:_"
        ),
        "en": (
            "👋 *Welcome to Imajin AI!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 _Please verify you're human first_\n\n"
            "*What is:* `{q}` *?*\n\n"
            "_Tap the correct number:_"
        ),
    },
    "start_welcome_main": {
        "id": (
            "✨ *Imajin AI* ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "_Imajin AI ready_ 🎨\n\n"
            "👤 Status: *{plan_label}*{free_status}\n\n"
            "🖼️  /image — Generate gambar\n"
            "🎬  /video — Generate video _(premium)_\n"
            "💎  /upgrade — Beli premium plan\n"
            "📊  /status — Cek paket Anda\n"
            "📖  /help — Cara pakai\n\n"
            "💡 _Ketik / buat liat semua command_"
        ),
        "en": (
            "✨ *Imajin AI* ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "_Imajin AI ready_ 🎨\n\n"
            "👤 Status: *{plan_label}*{free_status}\n\n"
            "🖼️  /image — Generate image\n"
            "🎬  /video — Generate video _(premium)_\n"
            "💎  /upgrade — Buy premium plan\n"
            "📊  /status — Check your plan\n"
            "📖  /help — How to use\n\n"
            "💡 _Type / to see all commands_"
        ),
    },
    "plan_free": {"id": "🆓 FREE TRIAL", "en": "🆓 FREE TRIAL"},
    "plan_premium_until": {"id": "💎 PREMIUM _(s/d {date})_", "en": "💎 PREMIUM _(until {date})_"},
    "free_trial_exhausted": {
        "id": "\n⚠️ Trial habis. Silakan upgrade premium → /upgrade",
        "en": "\n⚠️ Free trial used up. Upgrade premium → /upgrade",
    },
    "free_trial_remaining_line": {
        "id": "\n🎁 Anda memiliki *{remaining}x* trial image gen gratis",
        "en": "\n🎁 You have *{remaining}x* free image trial(s) left",
    },

    # ============================== HELP ==============================
    "help_text": {
        "id": (
            "📖 *Imajin AI — Help*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 *FREE TRIAL*\n"
            "  • 2x image generate (lifetime)\n"
            "  • Setelah pakai: harus upgrade premium\n\n"
            "💎 *PREMIUM PLANS*\n"
            "  • Weekly: Rp 50.000 / 7 hari\n"
            "  • Monthly: Rp 150.000 / 30 hari\n"
            "  • Unlimited image + video gen\n"
            "  • Akses semua model (Kling, Seedance)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *Cara Pakai:*\n"
            "1️⃣  Verify captcha di /start\n"
            "2️⃣  Kirim teks → jadi prompt\n"
            "3️⃣  Tap 🖼️ Image / 🎬 Video\n"
            "4️⃣  Atur preset, ratio, style\n"
            "5️⃣  Tap GENERATE — chill ~30s-3min\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💳 *Beli Premium:*\n"
            "  /upgrade → pilih plan + bayar QRIS\n"
            "  /pay <kode> → upload screenshot\n"
            "  Admin manual approve dalam 1-12 jam\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 *Bahasa:* /lang"
        ),
        "en": (
            "📖 *Imajin AI — Help*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 *FREE TRIAL*\n"
            "  • 2x image generations (lifetime)\n"
            "  • After use: upgrade to premium required\n\n"
            "💎 *PREMIUM PLANS*\n"
            "  • Weekly: Rp 50,000 / 7 days\n"
            "  • Monthly: Rp 150,000 / 30 days\n"
            "  • Unlimited image + video generation\n"
            "  • Access to all models (Kling, Seedance)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *How to use:*\n"
            "1️⃣  Verify captcha at /start\n"
            "2️⃣  Send text → becomes prompt\n"
            "3️⃣  Tap 🖼️ Image / 🎬 Video\n"
            "4️⃣  Set preset, ratio, style\n"
            "5️⃣  Tap GENERATE — wait ~30s-3min\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💳 *Buy Premium:*\n"
            "  /upgrade → pick plan + pay via QRIS\n"
            "  /pay <code> → upload screenshot\n"
            "  Admin approves manually within 1-12h\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 *Language:* /lang"
        ),
    },

    # ============================== AUTH GATES ==============================
    "verify_first": {
        "id": "🤖 Silakan verifikasi via /start terlebih dahulu",
        "en": "🤖 Please verify via /start first",
    },
    "verify_first_short": {
        "id": "⚠️ Silakan /start terlebih dahulu.",
        "en": "⚠️ Please /start first.",
    },
    "admin_only": {"id": "🔒 Admin only", "en": "🔒 Admin only"},
    "admin_only_long": {
        "id": "🔒 Command khusus admin. Cek paket Anda: /status",
        "en": "🔒 Admin-only command. Check your plan: /status",
    },

    # ============================== MENU / SESSION ==============================
    "menu_panel": {
        "id": "⚙️ *Control Panel*\n━━━━━━━━━━━━━━━━━━━━━",
        "en": "⚙️ *Control Panel*\n━━━━━━━━━━━━━━━━━━━━━",
    },
    "session_reset": {
        "id": "🔄 *Session berhasil di-reset.*\n_Silakan pilih ulang konfigurasi._",
        "en": "🔄 *Session reset.*\n_Please reconfigure your options._",
    },

    # ============================== IMAGE / VIDEO MODES ==============================
    "image_free_intro": {
        "id": (
            "🖼️ *Image Mode — Free Trial*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 Anda mendapat *2x trial gratis*\n"
            "🤖 Engine: *Auto* _(model dipilih otomatis)_\n\n"
            "📝 *Cara pakai:*\n"
            "1. Kirim teks deskripsi gambar Anda\n"
            "2. Tap tombol 🚀 GENERATE\n"
            "3. Tunggu ~1-2 menit\n\n"
            "💎 Mau full control + unlimited?\n"
            "/upgrade untuk premium plan"
        ),
        "en": (
            "🖼️ *Image Mode — Free Trial*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 You get *2x free trials*\n"
            "🤖 Engine: *Auto* _(model picked automatically)_\n\n"
            "📝 *How to use:*\n"
            "1. Send text describing your image\n"
            "2. Tap the 🚀 GENERATE button\n"
            "3. Wait ~1-2 minutes\n\n"
            "💎 Want full control + unlimited?\n"
            "/upgrade for premium plan"
        ),
    },
    "image_premium_intro": {
        "id": "🖼️ *Image Mode aktif*\n_Kirim teks prompt lalu tap GENERATE._",
        "en": "🖼️ *Image Mode active*\n_Send your text prompt and tap GENERATE._",
    },
    "video_premium_only": {
        "id": (
            "🔒 *Video Mode = Premium Only*\n\n"
            "Free trial hanya untuk image. Silakan upgrade:\n"
            "/upgrade"
        ),
        "en": (
            "🔒 *Video Mode = Premium Only*\n\n"
            "Free trial is for images only. Please upgrade:\n"
            "/upgrade"
        ),
    },
    "video_intro": {
        "id": "🎬 *Video Mode aktif*\n_Kirim prompt + atur model + GENERATE._",
        "en": "🎬 *Video Mode active*\n_Send prompt + set model + GENERATE._",
    },

    # ============================== STATUS ==============================
    "status_admin": {"id": "👑 ADMIN (unlimited)", "en": "👑 ADMIN (unlimited)"},
    "status_free_used": {"id": "✅ pakai", "en": "✅ used"},
    "status_free_unused": {"id": "⏳ belum dipakai", "en": "⏳ not used"},
    "status_free_label": {
        "id": "🆓 FREE — trial {used}",
        "en": "🆓 FREE — trial {used}",
    },
    "status_premium_label": {
        "id": "💎 *{plan}* _(s/d {exp})_",
        "en": "💎 *{plan}* _(until {exp})_",
    },
    "status_block": {
        "id": (
            "📊 *Akun Anda*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 ID: `{uid}`\n"
            "📋 Plan: {plan_str}\n"
            "🎨 Total gen: *{gen_count}*\n\n"
        ),
        "en": (
            "📊 *Your Account*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 ID: `{uid}`\n"
            "📋 Plan: {plan_str}\n"
            "🎨 Total gens: *{gen_count}*\n\n"
        ),
    },
    "status_upgrade_hint": {"id": "💎 Upgrade: /upgrade\n", "en": "💎 Upgrade: /upgrade\n"},

    # ============================== UPGRADE ==============================
    "upgrade_intro": {
        "id": (
            "💎 *Pilih Plan Premium*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📅 *Weekly* — Rp 50.000 / 7 hari\n"
            "  ✓ Unlimited image gen\n"
            "  ✓ Unlimited video gen\n"
            "  ✓ Akses semua model\n\n"
            "⭐ *Monthly* — Rp 150.000 / 30 hari\n"
            "  ✓ Hemat *Rp 50.000* vs weekly x 4\n"
            "  ✓ Same benefits\n\n"
            "💳 _Bayar via QRIS, manual approve admin_"
        ),
        "en": (
            "💎 *Choose Premium Plan*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📅 *Weekly* — Rp 50,000 / 7 days\n"
            "  ✓ Unlimited image gen\n"
            "  ✓ Unlimited video gen\n"
            "  ✓ Access to all models\n\n"
            "⭐ *Monthly* — Rp 150,000 / 30 days\n"
            "  ✓ Save *Rp 50,000* vs weekly x 4\n"
            "  ✓ Same benefits\n\n"
            "💳 _Pay via QRIS, admin approves manually_"
        ),
    },
    "upgrade_btn_weekly": {"id": "📅 Weekly — Rp 50.000", "en": "📅 Weekly — Rp 50,000"},
    "upgrade_btn_monthly": {"id": "⭐ Monthly — Rp 150.000", "en": "⭐ Monthly — Rp 150,000"},
    "upgrade_btn_cancel": {"id": "❌ Batal", "en": "❌ Cancel"},

    # ============================== REFERRAL ==============================
    "ref_block": {
        "id": (
            "🎁 *Program Referral Imajin AI*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 *Statistik Anda:*\n"
            "  • Total invite: *{total}*\n"
            "  • Berhasil:     *{granted}* ✅\n"
            "  • Pending:      *{pending}* ⏳\n"
            "  • Bonus trial:  *+{bonus}x* 🎁\n\n"
            "🎁 *Reward:*\n"
            "  • Anda invite teman: *+{br}x trial* per teman\n"
            "  • Teman join:        dapat *+{bi}x trial* bonus\n\n"
            "📤 *Link Invite Anda:*\n"
            "`{link}`\n\n"
            "_Tap link untuk copy, lalu share ke teman._\n\n"
            "💡 *Tips:*\n"
            "• Bonus aktif setelah teman lulus captcha /start\n"
            "• Tidak ada batas jumlah invite\n"
            "• Bonus terus terakumulasi\n"
        ),
        "en": (
            "🎁 *Imajin AI Referral Program*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 *Your Stats:*\n"
            "  • Total invites: *{total}*\n"
            "  • Successful:    *{granted}* ✅\n"
            "  • Pending:       *{pending}* ⏳\n"
            "  • Bonus trials:  *+{bonus}x* 🎁\n\n"
            "🎁 *Rewards:*\n"
            "  • You invite a friend: *+{br}x trial* per friend\n"
            "  • Friend joins:        gets *+{bi}x trial* bonus\n\n"
            "📤 *Your Invite Link:*\n"
            "`{link}`\n\n"
            "_Tap link to copy, then share with friends._\n\n"
            "💡 *Tips:*\n"
            "• Bonus activates after friend passes /start captcha\n"
            "• No invite limit\n"
            "• Bonuses keep stacking\n"
        ),
    },

    # ============================== LANGUAGE TOGGLE ==============================
    "lang_picker": {
        "id": (
            "🌐 *Pilih Bahasa / Choose Language*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Saat ini: 🇮🇩 *Indonesia*"
        ),
        "en": (
            "🌐 *Choose Language / Pilih Bahasa*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Currently: 🇺🇸 *English*"
        ),
    },
    "lang_set_id": {
        "id": "✅ Bahasa diubah ke 🇮🇩 *Indonesia*",
        "en": "✅ Language changed to 🇮🇩 *Indonesia*",
    },
    "lang_set_en": {
        "id": "✅ Bahasa diubah ke 🇺🇸 *English*",
        "en": "✅ Language changed to 🇺🇸 *English*",
    },

    # ============================== KEYBOARD LABELS ==============================
    "btn_image": {"id": "🖼️ Image", "en": "🖼️ Image"},
    "btn_video": {"id": "🎬 Video", "en": "🎬 Video"},
    "btn_generate_image": {"id": "🚀 GENERATE GAMBAR", "en": "🚀 GENERATE IMAGE"},
    "btn_generate_video": {"id": "🚀 GENERATE VIDEO", "en": "🚀 GENERATE VIDEO"},
    "btn_random_gen": {
        "id": "🎲 Random Prompt + Auto Generate Gambar",
        "en": "🎲 Random Prompt + Auto Generate Image",
    },
    "btn_upgrade_premium": {"id": "💎 Upgrade Premium", "en": "💎 Upgrade Premium"},
    "btn_reset": {"id": "🔄 Reset", "en": "🔄 Reset"},
    "btn_balance": {"id": "💰 Cek Token", "en": "💰 Token Balance"},
    "btn_back": {"id": "⬅️ Back", "en": "⬅️ Back"},
    "btn_lang": {"id": "🌐 Bahasa / Language", "en": "🌐 Language / Bahasa"},
    "btn_free_trial_label": {"id": "🎁 Free Trial — Auto Mode", "en": "🎁 Free Trial — Auto Mode"},
    "btn_prompt_empty": {
        "id": "(belum diisi — kirim teks)",
        "en": "(empty — send text)",
    },

    # ============================== CAPTCHA FLOW ==============================
    "captcha_expired": {
        "id": "⚠️ Captcha expired. Silakan /start ulang.",
        "en": "⚠️ Captcha expired. Please /start again.",
    },
    "captcha_wrong": {
        "id": "❌ Jawaban salah. Silakan coba lagi:\n\n*Berapa hasil:* `{q}` *?*",
        "en": "❌ Wrong answer. Try again:\n\n*What is:* `{q}` *?*",
    },
    "captcha_referral_bonus": {
        "id": (
            "\n\n🎁 *Bonus Referral!*\n"
            "Anda mendapat tambahan *+{n}x trial gratis* "
            "karena diinvite oleh teman."
        ),
        "en": (
            "\n\n🎁 *Referral Bonus!*\n"
            "You got *+{n}x bonus free trials* "
            "because you were invited by a friend."
        ),
    },
    "captcha_verified": {
        "id": (
            "✅ *Verified!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Selamat datang di Imajin AI! 🎉\n"
            "Anda memiliki 🎁 *{trials}x trial image gen* gratis.{ref_msg}\n\n"
            "Silakan gunakan /image atau /upgrade\n"
            "💡 Invite teman = bonus trial: /ref\n\n"
            "🌐 *Pilih bahasa / Choose your language:*"
        ),
        "en": (
            "✅ *Verified!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Welcome to Imajin AI! 🎉\n"
            "You have 🎁 *{trials}x free image trial(s)*.{ref_msg}\n\n"
            "Use /image or /upgrade to start\n"
            "💡 Invite friends = bonus trials: /ref\n\n"
            "🌐 *Choose your language / Pilih bahasa:*"
        ),
    },
    "referrer_notif": {
        "id": (
            "🎉 *Referral berhasil!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Teman Anda baru saja gabung Imajin AI 🎁\n"
            "Anda dapat *+{n}x trial gratis*.\n\n"
            "📊 Total invite sukses: *{count}*\n"
            "💎 Cek bonus: /ref"
        ),
        "en": (
            "🎉 *Referral successful!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your friend just joined Imajin AI 🎁\n"
            "You got *+{n}x free trials*.\n\n"
            "📊 Successful invites: *{count}*\n"
            "💎 Check bonus: /ref"
        ),
    },

    # ============================== UPGRADE / PAYMENT FLOW ==============================
    "upgrade_cancel": {"id": "❌ Batal upgrade.", "en": "❌ Upgrade cancelled."},
    "plan_label_weekly": {"id": "Weekly (7 hari)", "en": "Weekly (7 days)"},
    "plan_label_monthly": {"id": "Monthly (30 hari)", "en": "Monthly (30 days)"},
    "payment_created": {
        "id": (
            "✅ *Payment Created*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Kode unik: `{code}`\n"
            "📋 Plan: *{plan_label}*\n"
            "💰 Amount: *Rp {amount:,}*\n\n"
            "📲 _Scan QRIS di pesan berikutnya..._"
        ),
        "en": (
            "✅ *Payment Created*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Unique code: `{code}`\n"
            "📋 Plan: *{plan_label}*\n"
            "💰 Amount: *Rp {amount:,}*\n\n"
            "📲 _Scan QRIS in the next message..._"
        ),
    },
    "qris_caption": {
        "id": (
            "💳 *Pembayaran Rp {amount:,} via QRIS*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Kode Anda: `{code}`\n\n"
            "📋 *Steps:*\n"
            "1️⃣  Scan QR + bayar *Rp {amount:,}*\n"
            "2️⃣  Screenshot bukti transfer\n"
            "3️⃣  Kirim: `/pay {code}` lalu upload foto\n\n"
            "⏳ Admin approve dalam 1-12 jam.\n"
            "_Notifikasi otomatis setelah aktif._"
        ),
        "en": (
            "💳 *Payment Rp {amount:,} via QRIS*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Your code: `{code}`\n\n"
            "📋 *Steps:*\n"
            "1️⃣  Scan QR and pay *Rp {amount:,}*\n"
            "2️⃣  Screenshot the transfer receipt\n"
            "3️⃣  Send: `/pay {code}` then upload the photo\n\n"
            "⏳ Admin approves within 1-12 hours.\n"
            "_Auto-notification once activated._"
        ),
    },
    "qris_unset": {
        "id": (
            "⚠️ QRIS belum di-set di server.\n"
            "Silakan hubungi admin secara manual.\n\n"
            "Kode Anda: `{code}`"
        ),
        "en": (
            "⚠️ QRIS not configured on server.\n"
            "Please contact admin manually.\n\n"
            "Your code: `{code}`"
        ),
    },
    "premium_activated": {
        "id": (
            "🎉 *PREMIUM AKTIF!* 🎉\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Kode: `{code}`\n"
            "💎 Plan: *{plan}*\n"
            "📅 Expires: *{exp}*\n\n"
            "Silakan gunakan /image atau /video. 🚀"
        ),
        "en": (
            "🎉 *PREMIUM ACTIVE!* 🎉\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Code: `{code}`\n"
            "💎 Plan: *{plan}*\n"
            "📅 Expires: *{exp}*\n\n"
            "Start using /image or /video. 🚀"
        ),
    },

    # ============================== /pay command ==============================
    "screenshot_uploaded": {"id": "✅ udah", "en": "✅ uploaded"},
    "screenshot_missing": {"id": "❌ belum", "en": "❌ pending"},
    "pay_pending_block": {
        "id": (
            "💳 *Payment Anda Yang Pending*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Kode: `{code}`\n"
            "📋 Plan: *{plan}*\n"
            "💰 Amount: *Rp {amount:,}*\n"
            "📸 Screenshot: {sshot}\n"
            "🕐 Requested: _{req}_\n\n"
            "Cara: `/pay {code}` lalu kirim foto bukti transfer."
        ),
        "en": (
            "💳 *Your Pending Payment*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔑 Code: `{code}`\n"
            "📋 Plan: *{plan}*\n"
            "💰 Amount: *Rp {amount:,}*\n"
            "📸 Screenshot: {sshot}\n"
            "🕐 Requested: _{req}_\n\n"
            "How to: `/pay {code}` then send transfer receipt photo."
        ),
    },
    "pay_no_pending": {
        "id": "💳 *Belum ada payment pending*\n\nBuat payment baru: /upgrade",
        "en": "💳 *No pending payment*\n\nCreate new payment: /upgrade",
    },
    "pay_code_not_found": {
        "id": "❌ Kode `{code}` tidak ditemukan",
        "en": "❌ Code `{code}` not found",
    },
    "pay_code_not_yours": {
        "id": "⛔ Kode ini bukan milik Anda",
        "en": "⛔ This code is not yours",
    },
    "pay_code_already": {
        "id": "❌ Kode ini sudah `{status}`",
        "en": "❌ This code is already `{status}`",
    },
    "pay_send_screenshot": {
        "id": (
            "📸 *Kirim screenshot bukti transfer untuk:*\n\n"
            "🔑 `{code}`\n"
            "💰 Rp {amount:,}\n\n"
            "_Kirim foto sekarang. Auto-attach._"
        ),
        "en": (
            "📸 *Send transfer screenshot for:*\n\n"
            "🔑 `{code}`\n"
            "💰 Rp {amount:,}\n\n"
            "_Send photo now. Auto-attached._"
        ),
    },

    # ============================== MENU / PICKER OPENERS ==============================
    "menu_panel_short": {
        "id": "⚙️ Panel Generator:",
        "en": "⚙️ Generator Panel:",
    },
    "mode_video_active": {"id": "🎬 *Video Mode*", "en": "🎬 *Video Mode*"},
    "mode_image_active": {"id": "🖼️ *Image Mode*", "en": "🖼️ *Image Mode*"},
    "open_vmodel_title": {
        "id": (
            "🎬 *Pilih Video Model*\n\n"
            "_Kling V3 = paling baru, 1080p, audio support._\n"
            "_Veo 3 = Google, kualitas premium._"
        ),
        "en": (
            "🎬 *Choose Video Model*\n\n"
            "_Kling V3 = latest, 1080p, audio support._\n"
            "_Veo 3 = Google, premium quality._"
        ),
    },
    "open_var_title": {"id": "📐 *Pilih Aspect Ratio Video*", "en": "📐 *Choose Video Aspect Ratio*"},
    "open_vdur_title": {"id": "⏱️ *Pilih Duration (detik)*", "en": "⏱️ *Choose Duration (seconds)*"},
    "open_vres_title": {"id": "🎯 *Pilih Resolution*", "en": "🎯 *Choose Resolution*"},
    "open_vqty_title": {"id": "🔢 *Pilih Quantity Video (1-2)*", "en": "🔢 *Choose Video Quantity (1-2)*"},
    "audio_toggled": {
        "id": "🔊 Audio: *{state}*",
        "en": "🔊 Audio: *{state}*",
    },
    "open_model_title": {
        "id": "🤖 *Pilih Model*\n\n_Auto = Imajin pilihin model paling cocok untuk prompt._",
        "en": "🤖 *Choose Model*\n\n_Auto = Imajin picks the best model for your prompt._",
    },
    "open_ar_title": {"id": "📐 *Pilih Aspect Ratio*", "en": "📐 *Choose Aspect Ratio*"},
    "open_style_title": {"id": "🎨 *Pilih Style Preset*", "en": "🎨 *Choose Style Preset*"},
    "open_qty_title": {"id": "🔢 *Pilih Quantity (1-4)*", "en": "🔢 *Choose Quantity (1-4)*"},

    # set confirmations
    "set_video_model": {"id": "✅ Video Model: *{val}*", "en": "✅ Video Model: *{val}*"},
    "set_video_ar":    {"id": "✅ Video Aspect: *{val}*", "en": "✅ Video Aspect: *{val}*"},
    "set_video_dur":   {"id": "✅ Duration: *{val}s*", "en": "✅ Duration: *{val}s*"},
    "set_video_res":   {"id": "✅ Resolution: *{val}*", "en": "✅ Resolution: *{val}*"},
    "set_video_qty":   {"id": "✅ Video Qty: *{val}*", "en": "✅ Video Qty: *{val}*"},
    "set_model":       {"id": "✅ Model: *{val}*", "en": "✅ Model: *{val}*"},
    "set_ar":          {"id": "✅ Aspect: *{val}*", "en": "✅ Aspect: *{val}*"},
    "set_style":       {"id": "✅ Style: *{val}*", "en": "✅ Style: *{val}*"},
    "set_qty":         {"id": "✅ Quantity: *{val}*", "en": "✅ Quantity: *{val}*"},

    # Info / actions
    "info_prompt_send": {
        "id": "📝 Kirim teks apa saja sebagai prompt baru.",
        "en": "📝 Send any text as a new prompt.",
    },
    "info_freetrial_block": {
        "id": (
            "🎁 *Free Trial Mode*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Free trial menggunakan engine *Auto*.\n"
            "Model dan style dipilih otomatis untuk hasil optimal.\n\n"
            "💎 Untuk full control, akses model premium "
            "(Phoenix, FLUX, Lucid), aspect ratio custom, "
            "dan unlimited generation:\n\n"
            "/upgrade"
        ),
        "en": (
            "🎁 *Free Trial Mode*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Free trial uses *Auto* engine.\n"
            "Model and style are picked automatically for best results.\n\n"
            "💎 For full control, premium model access "
            "(Phoenix, FLUX, Lucid), custom aspect ratios, "
            "and unlimited generation:\n\n"
            "/upgrade"
        ),
    },
    "session_reset_short": {
        "id": "🔄 Session direset.",
        "en": "🔄 Session reset.",
    },

    # ============================== BALANCE ==============================
    "balance_loading_short": {
        "id": "💰 Cek balance...",
        "en": "💰 Checking balance...",
    },
    "balance_loading": {
        "id": "💰 _Cek balance..._",
        "en": "💰 _Checking balance..._",
    },
    "balance_block": {
        "id": (
            "💰 *Engine Token Balance*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 _{username}_\n"
            "💎 Plan: *{plan}*\n\n"
            "🪙  Image tokens: *{tokens:,}*\n"
            "📺  Stream tokens: {stream:,}\n"
            "💬  GPT tokens: {gpt:,}\n\n"
            "🔄 Renews: _{renewal}_"
        ),
        "en": (
            "💰 *Engine Token Balance*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 _{username}_\n"
            "💎 Plan: *{plan}*\n\n"
            "🪙  Image tokens: *{tokens:,}*\n"
            "📺  Stream tokens: {stream:,}\n"
            "💬  GPT tokens: {gpt:,}\n\n"
            "🔄 Renews: _{renewal}_"
        ),
    },
    "balance_short": {
        "id": "💰 Image tokens: *{tokens:,}*\n📺 Stream: {stream:,}\n💎 Plan: {plan}",
        "en": "💰 Image tokens: *{tokens:,}*\n📺 Stream: {stream:,}\n💎 Plan: {plan}",
    },
    "error_label": {"id": "❌ Error: `{err}`", "en": "❌ Error: `{err}`"},

    # ============================== GENERATION FLOW ==============================
    "no_prompt": {
        "id": "⚠️ Silakan kirim prompt terlebih dahulu (kirim teks).",
        "en": "⚠️ Please send a prompt first (send text).",
    },
    "trial_exhausted_block": {
        "id": (
            "🔒 *Trial sudah habis*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Anda telah menggunakan trial gratis.\n"
            "Untuk melanjutkan, silakan upgrade premium:\n\n"
            "💎 /upgrade"
        ),
        "en": (
            "🔒 *Trial used up*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "You've used your free trials.\n"
            "To continue, upgrade to premium:\n\n"
            "💎 /upgrade"
        ),
    },
    "rate_limit": {
        "id": "⏳ Mohon tunggu {wait} detik (rate limit).",
        "en": "⏳ Please wait {wait} seconds (rate limit).",
    },
    "random_loading": {
        "id": "🎲 _Memilih prompt random..._",
        "en": "🎲 _Picking random prompt..._",
    },
    "random_failed": {
        "id": "❌ Gagal generate random prompt. Silakan coba lagi atau kirim prompt manual.",
        "en": "❌ Failed to generate random prompt. Try again or send your own prompt.",
    },
    "random_success": {
        "id": "🎲 *Random prompt:*\n_{prompt}_\n\n_Generating otomatis..._",
        "en": "🎲 *Random prompt:*\n_{prompt}_\n\n_Auto-generating..._",
    },
    "enhancing": {
        "id": "✨ _Memperkaya prompt Anda..._",
        "en": "✨ _Enhancing your prompt..._",
    },
    "gen_progress_header": {
        "id": "🚀 *Generating...*\n\n📝 Prompt: _{prompt}..._\n",
        "en": "🚀 *Generating...*\n\n📝 Prompt: _{prompt}..._\n",
    },
    "gen_enhanced_line": {
        "id": "✨ _Prompt diperkaya otomatis_\n",
        "en": "✨ _Prompt auto-enhanced_\n",
    },
    "gen_queue_line": {
        "id": "⏳ Antrian: posisi *#{pos}*\n⏰ ETA: ~{eta:.0f} menit\n",
        "en": "⏳ Queue: position *#{pos}*\n⏰ ETA: ~{eta:.0f} min\n",
    },
    "gen_free_engine_line": {
        "id": "🤖 Engine: *Auto (Free Trial)*\n📐 Auto resolution\n\n_Tunggu ~1-2 menit per gen..._",
        "en": "🤖 Engine: *Auto (Free Trial)*\n📐 Auto resolution\n\n_Wait ~1-2 minutes per gen..._",
    },
    "gen_premium_engine_line": {
        "id": (
            "🤖 Model: {model}\n"
            "📐 {ar} ({w}x{h})\n"
            "🎨 Style: {style}\n"
            "🔢 Quantity: {qty}\n\n"
            "_Tunggu ~10-30 detik per gen..._"
        ),
        "en": (
            "🤖 Model: {model}\n"
            "📐 {ar} ({w}x{h})\n"
            "🎨 Style: {style}\n"
            "🔢 Quantity: {qty}\n\n"
            "_Wait ~10-30 seconds per gen..._"
        ),
    },
    "gen_starting_now": {
        "id": "🚀 _Mulai generate sekarang..._\n",
        "en": "🚀 _Starting generation now..._\n",
    },
    "gen_failed": {"id": "❌ Gagal: {err}", "en": "❌ Failed: {err}"},
    "gen_no_files": {
        "id": "⚠️ Generation succeeded tapi tidak ada file — coba ulang.",
        "en": "⚠️ Generation succeeded but no files were returned — try again.",
    },
    "gen_caption_multi": {
        "id": "✅ {n} gambar selesai\n📝 _{prompt}..._",
        "en": "✅ {n} images done\n📝 _{prompt}..._",
    },
    "gen_caption_single": {
        "id": "✅ Generated\n📝 _{prompt}..._",
        "en": "✅ Generated\n📝 _{prompt}..._",
    },
    "trial_used_hint": {
        "id": (
            "🎁 *Trial gratis sudah digunakan*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Untuk generate lagi, silakan upgrade premium:\n"
            "💎 /upgrade"
        ),
        "en": (
            "🎁 *Free trial used*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "To generate again, upgrade to premium:\n"
            "💎 /upgrade"
        ),
    },

    # Video gen
    "video_premium_only_short": {
        "id": "🔒 *Video Mode = Premium Only*\n\nFree trial hanya untuk image. Silakan upgrade:\n💎 /upgrade",
        "en": "🔒 *Video Mode = Premium Only*\n\nFree trial is for images only. Please upgrade:\n💎 /upgrade",
    },
    "video_gen_progress": {
        "id": (
            "🚀 *Generating Video...*\n\n"
            "📝 Prompt: _{prompt}..._\n"
            "🎬 Model: {model}\n"
            "📐 {ar} ({w}x{h})\n"
            "⏱️ Duration: {dur}s\n"
            "🎯 Resolution: {res}\n"
            "🔊 Audio: {audio}\n"
            "🔢 Quantity: {qty}\n\n"
            "_Video butuh ~1-3 menit, mohon ditunggu..._"
        ),
        "en": (
            "🚀 *Generating Video...*\n\n"
            "📝 Prompt: _{prompt}..._\n"
            "🎬 Model: {model}\n"
            "📐 {ar} ({w}x{h})\n"
            "⏱️ Duration: {dur}s\n"
            "🎯 Resolution: {res}\n"
            "🔊 Audio: {audio}\n"
            "🔢 Quantity: {qty}\n\n"
            "_Video takes ~1-3 minutes, please wait..._"
        ),
    },
    "video_no_files": {
        "id": "⚠️ Video gen succeeded tapi tidak ada file — coba ulang.",
        "en": "⚠️ Video gen succeeded but no files were returned — try again.",
    },
    "video_caption_first": {
        "id": (
            "✅ Video {i}/{n}\n"
            "🎬 {model}\n"
            "⏱️ {dur}s @ {res}\n"
            "📝 _{prompt}..._"
        ),
        "en": (
            "✅ Video {i}/{n}\n"
            "🎬 {model}\n"
            "⏱️ {dur}s @ {res}\n"
            "📝 _{prompt}..._"
        ),
    },
}


def t(uid: int, key: str, **kwargs) -> str:
    """Get translated text for user. Falls back to 'id' if key/lang missing."""
    lang = db.get_lang(uid)
    entry = TEXTS.get(key)
    if not entry:
        return f"[missing:{key}]"
    text = entry.get(lang) or entry.get("id") or ""
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def lang_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for /lang command."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇮🇩 Indonesia", callback_data="lang:id"),
            InlineKeyboardButton("🇺🇸 English",   callback_data="lang:en"),
        ],
    ])


def detect_lang_from_telegram(tg_lang_code: str | None) -> str:
    """Map Telegram user.language_code to our supported langs.

    Default: 'id'. Only switch to 'en' if TG explicitly says English.
    """
    if not tg_lang_code:
        return "id"
    code = tg_lang_code.lower()
    if code.startswith("id"):
        return "id"
    if code.startswith("en"):
        return "en"
    # Other languages → default to English (more universal than ID for non-ID users)
    return "en"
