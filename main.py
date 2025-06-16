import os
import re
import yt_dlp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_FILE = "sessionid.txt"

# Flask keep-alive server
app_flask = Flask("keep_alive")

@app_flask.route("/")
def home():
    return "✅ Bot is alive!"

def run_flask():
    app_flask.run(host="0.0.0.0", port=8080)

# Load Instagram session ID from file
def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return f.read().strip()
    return None

# Regex to detect supported media URLs
URL_REGEX = r"(https?://[^\s]+(?:instagram\.com|youtube\.com|youtu\.be|tiktok\.com)[^\s]*)"

# Main media handler
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.strip()
    match = re.search(URL_REGEX, message)
    if not match:
        await update.message.reply_text("❌ No supported media link found.")
        return

    url = match.group(1)
    await update.message.reply_text(f"📥 Downloading from:\n{url}")

    ydl_opts = {
        'outtmpl': 'downloaded.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
    }

    if "instagram.com" in url:
        sessionid = load_session()
        if sessionid:
            with open(SESSION_FILE, "w") as f:
                f.write(f"sessionid={sessionid}")
            ydl_opts['cookiefile'] = SESSION_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if filename.endswith(".mp4"):
            await update.message.reply_video(video=open(filename, 'rb'))
        else:
            await update.message.reply_document(document=open(filename, 'rb'))

        os.remove(filename)

    except Exception as e:
        await update.message.reply_text(f"❌ Error:\n{str(e)}")

# /session command
async def set_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        sessionid = context.args[0].strip()
        with open(SESSION_FILE, "w") as f:
            f.write(sessionid)
        await update.message.reply_text("✅ Session ID saved.")
    else:
        await update.message.reply_text("⚠️ Usage: /session YOUR_SESSION_ID")

# /delete command
async def delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        await update.message.reply_text("❌ Session ID deleted.")
    else:
        await update.message.reply_text("No session ID found.")

# Start Flask keep-alive server
Thread(target=run_flask).start()

# Start the Telegram bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("session", set_session))
app.add_handler(CommandHandler("delete", delete_session))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()
