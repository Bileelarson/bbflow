import os
import sys
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configuration basique des logs
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("kleinbot")

# --- VARIABLES GLOBALES DE BRANDING ---
BOT_NAME = "BBFlow"
ADMIN_TITLE = f"✨ {BOT_NAME} — ADMIN MODE ✨"

# On récupère le token Telegram depuis Render
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /start et affiche le menu d'accueil en anglais par défaut."""
    user_id = str(update.effective_user.id)
    admin_ids = os.environ.get("ADMIN_TELEGRAM_IDS", "").split(",")
    
    is_admin = user_id in admin_ids
    
    # Texte d'accueil personnalisé
    if is_admin:
        welcome_text = f"{ADMIN_TITLE}\n\nUnlimited generation for admin. 👑\n\nSend any text as a new prompt to start generating."
    else:
        welcome_text = f"Welcome to {BOT_NAME} AI 🚀\n\nSend any text to generate an image."

    # Clavier principal (entièrement en anglais)
    keyboard = [
        [InlineKeyboardButton("🖼️ Image Mode", callback_data="mode:image")],
        [InlineKeyboardButton("🤖 Model: Auto", callback_data="settings:model")],
        [InlineKeyboardButton("📐 Aspect: 1:1", callback_data="settings:aspect")],
        [InlineKeyboardButton("📝 Prompt: (empty)", callback_data="settings:prompt")],
        [InlineKeyboardButton("🚀 GENERATE IMAGE", callback_data="action:generate")],
        [InlineKeyboardButton("💰 Token Balance", callback_data="action:balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les clics sur les boutons du menu."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "action:generate":
        await query.edit_message_text(text="🚀 Generating... Please wait ~10 seconds.")
        # Ici le script appellera normalement gen_image_one.py
        # Pour ce squelette nettoyé, on simule l'appel.
    elif data == "action:balance":
        await query.edit_message_text(text="💰 Balance checked: Unlimited (Admin)")
    else:
        await query.edit_message_text(text=f"⚙️ Setting selected: {data}\nSend /start to go back.")

def main():
    if not TOKEN:
        logger.error("Erreur critique: TELEGRAM_BOT_TOKEN n'est pas défini dans l'environnement Render.")
        sys.exit(1)
        
    logger.info("Démarrage de BBFlow Bot...")
    
    application = Application.builder().token(TOKEN).build()

    # On enregistre les commandes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Lance le bot en mode polling continu
    application.run_polling()

if __name__ == "__main__":
    main()
