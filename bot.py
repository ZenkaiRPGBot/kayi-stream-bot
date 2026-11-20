import os
import sys
import time
import secrets
import asyncio
from datetime import datetime, timezone
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, BOT_START_TIME,
    BRAND_NAME, BOT_USERNAME, CHANNEL_USERNAME, SERVER_URL, LINK_EXPIRY_HOURS
)
import database as db
from server import start_server

dp = Dispatcher()
HTTP_SESSION: aiohttp.ClientSession | None = None

def get_uptime_string() -> str:
    delta = datetime.now(timezone.utc) - BOT_START_TIME
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0 or days > 0: parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"

def build_rich_restart_markdown() -> str:
    return f"""# {BRAND_NAME} Online

| Feature | Status |
| :--- | :---: |
| Bot Status | Online 🟢 |
| Stream Engine | Ready 🟢 |
| Web Player | Active 🟢 |
| Range Seeker | Enabled 🟢 |

### What's New
- High-speed direct browser download links
- Online HTML5 video player (VLC, MX Player compatible)
- Low memory chunked streaming architecture
- Anti-abuse limits (rate limiting & expiry)
- Ecosystem integration for {CHANNEL_USERNAME}

*Ready to stream media.*"""

async def send_rich_restart_notification(bot: Bot):
    rich_md = build_rich_restart_markdown()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage"

    if OWNER_ID:
        try:
            payload = {"chat_id": OWNER_ID, "rich_message": {"markdown": rich_md}}
            if HTTP_SESSION:
                async with HTTP_SESSION.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        print(f"[restart] Restart notification sent to owner ({OWNER_ID})")
        except Exception as e:
            print(f"[restart] Notice: Could not send restart notification to owner: {e}")

    if LOG_CHANNEL_ID:
        try:
            payload = {"chat_id": LOG_CHANNEL_ID, "rich_message": {"markdown": rich_md}}
            if HTTP_SESSION:
                async with HTTP_SESSION.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    print(f"[log_channel] Restart log sent to channel: {LOG_CHANNEL_ID}")
        except Exception as e:
            print(f"[log_channel] Notice: Could not send log to channel: {e}")

async def log_stream_generation(bot: Bot, user: types.User, file_name: str, file_size: str, dl_url: str):
    if not LOG_CHANNEL_ID:
        return
    text = (
        f"⚡ <b>New Link Generated ({BRAND_NAME})</b>\n\n"
        f"• <b>User:</b> {user.full_name} (<code>{user.id}</code>)\n"
        f"• <b>File:</b> <code>{file_name}</code>\n"
        f"• <b>Size:</b> <code>{file_size}</code>\n"
        f"• <b>Link:</b> {dl_url}"
    )
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"[log] Error logging to channel: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"📢 Join {CHANNEL_USERNAME}", url=channel_url))
    
    welcome_text = (
        f"<b>🦅 Welcome to {BRAND_NAME}!</b>\n\n"
        "⚡ <b>Instant Telegram File-to-Direct-Link Generator</b>\n\n"
        "<b>How to use:</b>\n"
        "• Send or forward ANY video, audio, or document to this bot.\n"
        "• Instantly get a high-speed direct browser download link and online web player URL!\n"
        "• Play your files directly in <b>VLC, MX Player, Smart TV</b>, or any browser without downloading inside Telegram first.\n\n"
        f"<i>Links remain valid for {LINK_EXPIRY_HOURS} hours.</i>\n\n"
        "Send your file below to start 👇"
    )
    await message.reply(welcome_text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message, bot: Bot):
    t0 = time.perf_counter()
    await bot.get_me()
    latency = (time.perf_counter() - t0) * 1000
    uptime = get_uptime_string()
    response = (
        f"<b>{BRAND_NAME} — Pong!</b>\n\n"
        f"• <b>Speed:</b> <code>{latency:.1f} ms</code>\n"
        f"• <b>Uptime:</b> <code>{uptime}</code>\n"
        f"• <b>Status:</b> <code>Healthy</code>"
    )
    await message.reply(response, parse_mode=ParseMode.HTML)

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("Access denied. Owner only.")
        return
    await message.reply("<b>Restarting...</b>", parse_mode=ParseMode.HTML)
    if HTTP_SESSION and not HTTP_SESSION.closed:
        await HTTP_SESSION.close()
    await bot.session.close()
    os.execv(sys.executable, [sys.executable] + sys.argv)

@dp.message(F.video | F.document | F.audio | F.voice)
async def handle_incoming_file(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    
    # Rate limit check
    within_limit = await db.check_rate_limit(user_id, limit=5)
    if not within_limit:
        await message.reply("⏳ <b>Rate Limit:</b> You are sending files too fast. Please wait 1 minute.", parse_mode=ParseMode.HTML)
        return

    # Extract media file info
    media = message.video or message.document or message.audio or message.voice
    file_id = media.file_id
    file_unique_id = media.file_unique_id
    file_size = media.file_size or 0
    mime_type = getattr(media, "mime_type", "application/octet-stream")
    
    file_name = getattr(media, "file_name", None)
    if not file_name:
        if message.video:
            file_name = f"video_{file_unique_id[:8]}.mp4"
        elif message.audio:
            file_name = f"audio_{file_unique_id[:8]}.mp3"
        elif message.voice:
            file_name = f"voice_{file_unique_id[:8]}.ogg"
        else:
            file_name = f"file_{file_unique_id[:8]}.bin"

    # Save to database
    token = secrets.token_urlsafe(12)
    record = await db.save_file_record(
        token=token,
        user_id=user_id,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type
    )

    size_formatted = format_file_size(file_size)
    dl_url = f"{SERVER_URL}/dl/{token}"
    watch_url = f"{SERVER_URL}/watch/{token}"

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🚀 Fast Download", url=dl_url),
        types.InlineKeyboardButton(text="📺 Web Player", url=watch_url)
    )
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    builder.row(types.InlineKeyboardButton(text=f"📢 Join {CHANNEL_USERNAME}", url=channel_url))

    response_text = (
        f"<b>🦅 {BRAND_NAME} — Link Generated!</b>\n\n"
        f"📁 <b>File:</b> <code>{file_name}</code>\n"
        f"📦 <b>Size:</b> <code>{size_formatted}</code>\n"
        f"⏱️ <b>Validity:</b> <code>{LINK_EXPIRY_HOURS} Hours</code>\n\n"
        f"<b>🚀 Direct Download Link:</b>\n"
        f"<code>{dl_url}</code> <i>(Tap to copy)</i>\n\n"
        f"<b>📺 Stream / Player URL:</b>\n"
        f"<code>{watch_url}</code>\n\n"
        f"<i>Paste in VLC, MX Player, Smart TV, or open in browser!</i>"
    )

    await message.reply(
        response_text,
        parse_mode=ParseMode.HTML,
        reply_markup=builder.as_markup(),
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

    # Log to channel in background
    asyncio.create_task(log_stream_generation(bot, message.from_user, file_name, size_formatted, dl_url))

async def main():
    global HTTP_SESSION
    if not BOT_TOKEN:
        print("\nERROR: BOT_TOKEN is missing in .env!\n")
        sys.exit(1)

    print(f"Launching {BRAND_NAME} Bot...")
    await db.init_db()

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=False, enable_cleanup_closed=True)
    HTTP_SESSION = aiohttp.ClientSession(connector=connector)

    bot = Bot(token=BOT_TOKEN)
    runner = await start_server()
    await bot.delete_webhook(drop_pending_updates=True)

    await send_rich_restart_notification(bot)

    print(f"{BRAND_NAME} Bot is actively polling. Ready to receive requests.")
    try:
        await dp.start_polling(bot)
    finally:
        if HTTP_SESSION and not HTTP_SESSION.closed:
            await HTTP_SESSION.close()
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot stopped.")
