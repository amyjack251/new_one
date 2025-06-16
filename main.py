import os
import re
import shutil
import yt_dlp
import instaloader
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from facebook_scraper import get_posts

BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_FILE = "sessionid.txt"

flask_app = Flask("keep_alive")

@flask_app.route("/")
def home():
    return "✅ Bot is alive"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return f.read().strip()
    return None

URL_REGEX = r"(https?://[^\s]+(?:instagram\.com|youtube\.com|youtu\.be|tiktok\.com|facebook\.com|fb\.watch|m\.facebook\.com)[^\s]*)"

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.search(URL_REGEX, text)
    if not match:
        await update.message.reply_text("❌ No supported media link found.")
        return

    url = match.group(1)
    await update.message.reply_text("⏳ Downloading...")

    os.makedirs("downloads", exist_ok=True)

    try:
        if "instagram.com" in url:
            await handle_instagram(url, update)
        elif "facebook.com" in url or "fb.watch" in url:
            await handle_facebook(url, update)
        else:
            await handle_yt_dlp(url, update)
    except Exception as e:
        await update.message.reply_text(f"❌ Error:\n{str(e)}")

    shutil.rmtree("downloads", ignore_errors=True)

async def handle_yt_dlp(url, update):
    ydl_opts = {
        'outtmpl': 'downloads/%(title).70s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'quiet': True,
        'noplaylist': False
    }

    if any(x in url for x in ["youtube.com", "youtu.be"]):
        if os.path.exists("youtube_cookies.txt"):
            ydl_opts["cookiefile"] = "youtube_cookies.txt"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    media_files = []
    if "entries" in info:
        for entry in info["entries"]:
            fname = yt_dlp.utils.sanitize_filename(ydl.prepare_filename(entry))
            media_files.append(fname)
    else:
        fname = yt_dlp.utils.sanitize_filename(ydl.prepare_filename(info))
        media_files.append(fname)

    for file in media_files:
        ext = file.split(".")[-1].lower()
        if ext in ["mp4", "webm"]:
            await update.message.reply_video(video=open(file, 'rb'))
        elif ext in ["jpg", "jpeg", "png"]:
            await update.message.reply_photo(photo=open(file, 'rb'))
        else:
            await update.message.reply_document(document=open(file, 'rb'))
        os.remove(file)

async def handle_instagram(url, update):
    shortcode = url.strip("/").split("/")[-1]
    sessionid = load_session()

    # Use yt_dlp for public reels/videos if no session
    if not sessionid and ("/reel/" in url or "/tv/" in url or "/p/" in url):
        await handle_yt_dlp(url, update)
        return

    try:
        loader = instaloader.Instaloader(dirname_pattern='downloads', save_metadata=False)
        post = None

        if sessionid:
            loader.context._session.cookies.set('sessionid', sessionid)
            loader.load_session_from_file(username="placeholder", filename=SESSION_FILE)

        try:
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
        except Exception as e:
            if not sessionid:
                await update.message.reply_text("⚠️ Post may be private or restricted. Use /session to add login.")
                return
            raise e

        loader.download_post(post, target="downloads")

        for file in os.listdir("downloads"):
            full = os.path.join("downloads", file)
            if file.endswith((".mp4", ".webm")):
                await update.message.reply_video(video=open(full, 'rb'))
            elif file.endswith((".jpg", ".jpeg", ".png", ".webp")):
                await update.message.reply_photo(photo=open(full, 'rb'))
            else:
                await update.message.reply_document(document=open(full, 'rb'))
            os.remove(full)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Instagram error.\n{str(e)}")

async def handle_facebook(url, update):
    found = False
    kwargs = {"post_urls": [url]}
    if os.path.exists("cookies.json"):
        kwargs["cookies"] = "cookies.json"

    for post in get_posts(**kwargs):
        if post.get("video"):
            await handle_yt_dlp(url, update)
            return
        elif post.get("image"):
            found = True
            await update.message.reply_photo(photo=post["image"])
        break

    if not found:
        await update.message.reply_text("⚠️ Facebook post is private or requires login.")

async def set_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        sessionid = context.args[0].strip()
        with open(SESSION_FILE, "w") as f:
            f.write(sessionid)
        await update.message.reply_text("✅ Instagram session ID saved.")
    else:
        await update.message.reply_text("⚠️ Usage: /session YOUR_SESSION_ID")

async def delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        await update.message.reply_text("❌ Instagram session ID deleted.")
    else:
        await update.message.reply_text("No session ID found.")

Thread(target=run_flask).start()

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("session", set_session))
app.add_handler(CommandHandler("delete", delete_session))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()
