import os
import asyncio
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
DOWNLOAD_DIR = './downloads'
COOKIES_FILE = 'cookies.txt'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Base yt-dlp options
def get_ydl_opts(custom_cookies=None):
    return {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': custom_cookies if custom_cookies and os.path.exists(custom_cookies) else None,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.redgifs.com/',
        'merge_output_format': 'mp4',
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **RedGIFs Downloader Bot**\n\n"
        "1️⃣ Upload your `cookies.txt` file and type `/coki` in the caption.\n"
        "2️⃣ Use `/user <username>` to download all videos."
    )

async def handle_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the uploaded document as cookies.txt"""
    if not update.message.document:
        await update.message.reply_text("Please upload the `cookies.txt` file as a document.")
        return

    file = await context.bot.get_file(update.message.document.file_id)
    await file.download_to_drive(COOKIES_FILE)
    await update.message.reply_text("✅ `cookies.txt` updated successfully!")

async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/user <username>`")
        return

    username = context.args[0]
    
    if not os.path.exists(COOKIES_FILE):
        await update.message.reply_text("⚠️ No cookies found! Please upload `cookies.txt` with `/coki` first.")
        return

    await update.message.reply_text(f"🔍 Fetching videos for `{username}`...")

    try:
        # Step 1: Extract URLs
        opts = get_ydl_opts(COOKIES_FILE)
        opts['extract_flat'] = True
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Note: RedGIFs uses /users/username/videos
            info = ydl.extract_info(f"https://www.redgifs.com/users/{username}/videos", download=False)
            urls = [entry['url'] for entry in info.get('entries', []) if 'url' in entry]

        if not urls:
            await update.message.reply_text("❌ No videos found or user is private.")
            return

        await update.message.reply_text(f"📦 Found {len(urls)} videos. Processing one-by-one...")

        # Step 2: Download and Upload sequentially
        for url in urls:
            try:
                download_opts = get_ydl_opts(COOKIES_FILE)
                download_opts['outtmpl'] = f'{DOWNLOAD_DIR}/%(id)s.%(ext)s'
                
                with yt_dlp.YoutubeDL(download_opts) as ydl:
                    video_info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(video_info)

                if os.path.exists(file_path):
                    # Check size for Telegram 50MB limit
                    if os.path.getsize(file_path) < 50 * 1024 * 1024:
                        with open(file_path, 'rb') as v:
                            # Added high timeouts for VPS stability
                            await update.message.reply_video(
                                video=v, 
                                caption=f"✅ {video_info.get('title', 'Video')}",
                                write_timeout=600, 
                                connect_timeout=100
                            )
                    else:
                        await update.message.reply_text(f"⏩ Skipped (Too Large): {video_info.get('title')}")
                    
                    os.remove(file_path) # Clear space immediately
                
                await asyncio.sleep(1) # Safety delay
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                continue

        await update.message.reply_text(f"🏁 Finished all tasks for `{username}`.")

    except Exception as e:
        await update.message.reply_text(f"❌ Fatal Error: {str(e)}")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("user", user_command))
    # This triggers /coki when you upload a file with that caption
    application.add_handler(MessageHandler(filters.Document.ALL & filters.Caption(["/coki"]), handle_cookies))

    print("VPS Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()