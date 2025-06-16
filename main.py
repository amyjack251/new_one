import os
import re
import yt_dlp
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SESSION_FILE = "sessionid.txt"

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return f.read().strip()
    return None

def save_session(sessionid):
    with open(SESSION_FILE, "w") as f:
        f.write(sessionid)

def delete_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set.")

sessionid = load_session()

URL_REGEX = r"(https?://[\w./?=&%-]+(?:instagram\.com|youtu\.be|youtube\.com|tiktok\.com|facebook\.com)[^\s]*)"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match = re.search(URL_REGEX, text)
    if not match:
        await update.message.reply_text("❌ No supported link found.")
        return

    url = match.group(1)
    await update.message.reply_text("⏳ Downloading media...")

    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'outtmpl': 'downloads/%(title).70s.%(ext)s',
        'format': 'best',
        'quiet': True,
    }

    if 'instagram.com' in url and sessionid:
        ydl_opts['cookiefile'] = SESSION_FILE
        with open(SESSION_FILE, 'w') as f:
            f.write(f"sessionid={sessionid}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info)
            ydl.download([url])

        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                await update.message.reply_video(video=f)
            os.remove(filename)
        else:
            await update.message.reply_text("⚠️ Downloaded but file not found.")
    except Exception as e:
        logger.error("Download error", exc_info=True)
        await update.message.reply_text("❌ An error occurred while downloading.")

async def set_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        new_id = context.args[0].strip()
        save_session(new_id)
        global sessionid
        sessionid = new_id
        await update.message.reply_text("✅ Session ID saved.")
    else:
        await update.message.reply_text("⚠️ Usage: /session SESSIONID")

async def delete_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_session()
    global sessionid
    sessionid = None
    await update.message.reply_text("❌ Session ID deleted.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("session", set_session))
    app.add_handler(CommandHandler("delete", delete_session_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot is running...")
    app.run_polling()
