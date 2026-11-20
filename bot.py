import os
import sys
import time
import secrets
import asyncio
from datetime import datetime, timezone
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, BOT_START_TIME,
    BRAND_NAME, BOT_USERNAME, CHANNEL_USERNAME, SERVER_URL, LINK_EXPIRY_HOURS
)
import database as db
from server import start_server, format_file_size, get_media_category

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

def build_rich_restart_markdown() -> str:
    return f"""# {BRAND_NAME} Online

| Feature | Status |
| :--- | :---: |
| Bot Status | Online 🟢 |
| Stream Engine | 128KB Chunked 🟢 |
| Web Player | Plyr Cinema UI 🟢 |
| External Players | VLC / MX Player 🟢 |
| Ecosystem | {CHANNEL_USERNAME} 🟢 |

### What's New
- High-speed direct browser download links with RFC 7233 byte-range seeking
- Executive glassmorphic Web Player with Plyr.js, PiP, and speed controls
- 1-Tap VLC Player and MX Player intent launchers
- Active link management via /myfiles and instant link revocation
- Zero-disk RAM-optimized chunked streaming

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

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📖 Streaming Guide", callback_data="help_guide"),
        types.InlineKeyboardButton(text="📊 My Links", callback_data="user_myfiles")
    )
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    builder.row(types.InlineKeyboardButton(text=f"📢 Join {CHANNEL_USERNAME}", url=channel_url))

    welcome_text = (
        f"<b>🦅 Welcome to {BRAND_NAME}!</b>\n\n"
        "⚡ <b>Ultra-Fast File to Direct Link & Video Stream Generator</b>\n\n"
        "<b>What I can do for you:</b>\n"
        "• <b>Direct Download Links:</b> High-speed browser downloads with IDM & ADM support.\n"
        "• <b>Instant Web Player:</b> Stream videos and music online without downloading.\n"
        "• <b>External App Streaming:</b> 1-tap playback in <b>VLC</b>, <b>MX Player</b>, and <b>Smart TVs</b>.\n"
        "• <b>No Waiting Time:</b> Instant links generated in 0.5 seconds!\n\n"
        "👇 <b>Simply send or forward any Video, Audio, or Document here to get started!</b>"
    )
    await message.reply(welcome_text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        f"<b>📖 {BRAND_NAME} — How to Stream & Play</b>\n\n"
        "<b>1️⃣ Direct Download:</b>\n"
        "Tap the <b>🚀 Fast Download</b> button or copy the direct link into Chrome, IDM, or 1DM.\n\n"
        "<b>2️⃣ Online Web Player:</b>\n"
        "Tap <b>📺 Web Player</b> to watch videos directly in your browser with full controls, subtitle support, and speed adjustment.\n\n"
        "<b>3️⃣ Stream in VLC Player:</b>\n"
        "• <b>PC / Mac:</b> Media ➔ Open Network Stream ➔ Paste your Direct Link.\n"
        "• <b>Android / iOS:</b> Tap the <b>⚡ VLC Player</b> button to launch VLC instantly.\n\n"
        "<b>4️⃣ Stream in MX Player (Android):</b>\n"
        "Tap the <b>📱 MX Player</b> button to open the video inside MX Player automatically.\n\n"
        "<b>Commands:</b>\n"
        "• /myfiles — View and manage your active links\n"
        "• /stats — View bot statistics\n"
        "• /ping — Check latency & server uptime"
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🚀 Try it now — Send a File", callback_data="noop"))
    await message.reply(help_text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.message(Command("myfiles"))
async def cmd_myfiles(message: types.Message):
    user_id = message.from_user.id
    files = await db.get_user_files(user_id, limit=5)
    if not files:
        await message.reply("📁 <b>You have no active streaming links.</b>\n\nSend any video or file to generate your first link!", parse_mode=ParseMode.HTML)
        return

    text = f"<b>📁 Your Active Links ({len(files)} Recent):</b>\n\n"
    builder = InlineKeyboardBuilder()

    for idx, f in enumerate(files, 1):
        token = f["token"]
        name = f["file_name"]
        size_str = format_file_size(f["file_size"])
        dls = f["download_count"]
        watch_url = f"{SERVER_URL}/watch/{token}"
        text += f"<b>{idx}. {name}</b>\n• Size: <code>{size_str}</code> | Downloads: <code>{dls}</code>\n• Stream: {watch_url}\n\n"
        builder.row(
            types.InlineKeyboardButton(text=f"📺 Watch #{idx}", url=watch_url),
            types.InlineKeyboardButton(text=f"🗑️ Revoke #{idx}", callback_data=f"revoke_{token}")
        )

    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup(), link_preview_options=types.LinkPreviewOptions(is_disabled=True))

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = await db.get_global_stats()
    uptime = get_uptime_string()
    total_gb = stats["total_bytes"] / (1024**3)
    text = (
        f"<b>📊 {BRAND_NAME} — Platform Statistics</b>\n\n"
        f"• <b>Active Links:</b> <code>{stats['active_links']}</code>\n"
        f"• <b>Total Files Hosted:</b> <code>{stats['total_files']}</code>\n"
        f"• <b>Total Downloads & Streams:</b> <code>{stats['total_downloads']}</code>\n"
        f"• <b>Data Streamed:</b> <code>{total_gb:.2f} GB</code>\n"
        f"• <b>Bot Uptime:</b> <code>{uptime}</code>\n"
        f"• <b>Engine Status:</b> <code>Online 🟢</code>"
    )
    await message.reply(text, parse_mode=ParseMode.HTML)

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
        f"• <b>Status:</b> <code>Healthy 🟢</code>"
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

@dp.callback_query(F.data.startswith("revoke_"))
async def callback_revoke(query: types.CallbackQuery):
    token = query.data.split("_")[1]
    user_id = query.from_user.id
    # Owner or uploader can delete
    deleted = await db.delete_file_record(token, user_id=None if user_id == OWNER_ID else user_id)
    if deleted:
        await query.answer("Link revoked and deleted! 🗑️", show_alert=True)
        await query.message.edit_text("<b>🗑️ Link has been permanently deleted and revoked.</b>", parse_mode=ParseMode.HTML)
    else:
        await query.answer("Could not revoke. Link may have already expired.", show_alert=True)

@dp.callback_query(F.data == "help_guide")
async def callback_help(query: types.CallbackQuery):
    await query.answer()
    await cmd_help(query.message)

@dp.callback_query(F.data == "user_myfiles")
async def callback_myfiles(query: types.CallbackQuery):
    await query.answer()
    await cmd_myfiles(query.message)

@dp.callback_query(F.data == "noop")
async def callback_noop(query: types.CallbackQuery):
    await query.answer("Send any file directly to this chat! 📁")

@dp.message(F.video | F.document | F.audio | F.voice | F.animation)
async def handle_media_file(message: types.Message, bot: Bot):
    user_id = message.from_user.id

    # Anti-abuse rate limit
    within_limit = await db.check_rate_limit(user_id, limit=5)
    if not within_limit:
        await message.reply("⏳ <b>Rate Limit:</b> You are sending files too fast. Please wait 1 minute.", parse_mode=ParseMode.HTML)
        return

    # Extract media file info
    media = message.video or message.document or message.audio or message.voice or message.animation
    file_id = media.file_id
    file_unique_id = media.file_unique_id
    file_size = getattr(media, "file_size", 0) or 0
    mime_type = getattr(media, "mime_type", "application/octet-stream") or "application/octet-stream"
    
    file_name = getattr(media, "file_name", None)
    if not file_name:
        if message.video:
            file_name = f"video_{file_unique_id[:8]}.mp4"
        elif message.audio:
            file_name = f"audio_{file_unique_id[:8]}.mp3"
        elif message.voice:
            file_name = f"voice_{file_unique_id[:8]}.ogg"
        elif message.animation:
            file_name = f"animation_{file_unique_id[:8]}.mp4"
        else:
            file_name = f"file_{file_unique_id[:8]}.bin"

    # Category icon
    category = get_media_category(mime_type, file_name)
    icon_map = {
        "video": "🎬 Video",
        "audio": "🎵 Audio Track",
        "image": "🖼️ Image",
        "pdf": "📑 PDF Document",
        "document": "📁 Document"
    }
    cat_label = icon_map.get(category, "📦 File")

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
    vlc_url = f"vlc://{dl_url.replace('https://', '').replace('http://', '')}"
    mx_url = f"intent:{dl_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end"

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📺 Web Player", url=watch_url),
        types.InlineKeyboardButton(text="🚀 Fast Download", url=dl_url)
    )
    if category == "video":
        builder.row(
            types.InlineKeyboardButton(text="⚡ Open in VLC", url=vlc_url),
            types.InlineKeyboardButton(text="📱 Open in MX", url=mx_url)
        )
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    builder.row(
        types.InlineKeyboardButton(text="🗑️ Revoke Link", callback_data=f"revoke_{token}"),
        types.InlineKeyboardButton(text=f"📢 Join {CHANNEL_USERNAME}", url=channel_url)
    )

    response_text = (
        f"<b>🦅 {BRAND_NAME} — Stream Link Ready!</b>\n\n"
        f"📁 <b>File:</b> <code>{file_name}</code>\n"
        f"📦 <b>Size:</b> <code>{size_formatted}</code>\n"
        f"🎭 <b>Type:</b> <code>{cat_label}</code>\n"
        f"⏱️ <b>Validity:</b> <code>{LINK_EXPIRY_HOURS} Hours</code>\n\n"
        f"<b>🚀 Direct Download Link:</b>\n"
        f"<code>{dl_url}</code> <i>(Tap to copy)</i>\n\n"
        f"<b>📺 Stream / Player URL:</b>\n"
        f"<code>{watch_url}</code>\n\n"
        f"<i>Paste link in VLC, MX Player, Smart TV, or open directly in browser!</i>"
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
