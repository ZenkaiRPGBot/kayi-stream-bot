import os
import sys
import time
import secrets
import asyncio
from datetime import datetime, timezone
import aiohttp
import psutil
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

def get_system_load() -> dict:
    try:
        proc = psutil.Process()
        mem_info = proc.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        cpu_pct = proc.cpu_percent(interval=None)
        sys_mem = psutil.virtual_memory()
        return {
            "proc_mem_mb": rss_mb,
            "cpu_pct": cpu_pct,
            "sys_mem_used_pct": sys_mem.percent,
            "status": "Optimal 🟢" if rss_mb < 250 else "High 🟡"
        }
    except Exception:
        return {
            "proc_mem_mb": 0.0,
            "cpu_pct": 0.0,
            "sys_mem_used_pct": 0.0,
            "status": "Normal 🟢"
        }

def format_time_remaining(expires_at_iso: str) -> str:
    try:
        now = datetime.now(timezone.utc)
        exp_dt = datetime.fromisoformat(expires_at_iso)
        if exp_dt <= now:
            return "Expired"
        diff = exp_dt - now
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if diff.days > 0:
            return f"{diff.days}d {hours}h left"
        return f"{hours}h {minutes}m left"
    except Exception:
        return "Active"

def build_rich_restart_markdown() -> str:
    return f"""# {BRAND_NAME} Online

| Feature | Status |
| :--- | :---: |
| Bot Status | Online 🟢 |
| Stream Engine | 128KB Chunked 🟢 |
| Web Player | Plyr Cinema UI 🟢 |
| File ID System | Active 🟢 |
| Ecosystem | {CHANNEL_USERNAME} 🟢 |

### What's New
- Incremental File IDs (#1, #2, etc.) for instant lookup
- /files command: Live bot storage load & active files explorer
- /info <id> command: In-depth technical metadata inspector
- 1-Tap VLC Player and MX Player intent launchers
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

async def log_stream_generation(bot: Bot, user: types.User, file_id_num: int, file_name: str, file_size: str, dl_url: str):
    if not LOG_CHANNEL_ID:
        return
    text = (
        f"⚡ <b>New Link Generated ({BRAND_NAME})</b>\n\n"
        f"• <b>ID:</b> <code>#{file_id_num}</code>\n"
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
        types.InlineKeyboardButton(text="📁 View Active Files", callback_data="show_files_1"),
        types.InlineKeyboardButton(text="📖 Streaming Guide", callback_data="help_guide")
    )
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    builder.row(types.InlineKeyboardButton(text=f"📢 Join {CHANNEL_USERNAME}", url=channel_url))

    welcome_text = (
        f"<b>🦅 Welcome to {BRAND_NAME}!</b>\n\n"
        "⚡ <b>Ultra-Fast File to Direct Link & Video Stream Generator</b>\n\n"
        "<b>What I do:</b>\n"
        "• <b>Instant Links:</b> Send any file ➔ Get high-speed download & streaming links.\n"
        "• <b>Web Player:</b> Stream videos in HD with Plyr.js, speed adjustment & subtitles.\n"
        "• <b>External Players:</b> 1-tap playback in <b>VLC</b>, <b>MX Player</b>, or <b>Smart TVs</b>.\n"
        "• <b>File ID Registry:</b> Every file is cataloged with an ID for easy tracking (/files & /info).\n\n"
        "👇 <b>Send or forward any Video, Audio, or Document here to get started!</b>"
    )
    await message.reply(welcome_text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        f"<b>📖 {BRAND_NAME} — Command & Streaming Guide</b>\n\n"
        "<b>📂 File Management Commands:</b>\n"
        "• /files [page] — View current active files, bot memory & system load\n"
        "• /info &lt;id&gt; — Get comprehensive technical details for a specific file ID\n"
        "• /myfiles — Quick list of your personal generated links\n"
        "• /stats — Global platform statistics\n"
        "• /ping — Check latency & server uptime\n\n"
        "<b>📺 Streaming Tips:</b>\n"
        "• <b>Web:</b> Tap <b>📺 Web Player</b> to play directly in browser.\n"
        "• <b>VLC / MX:</b> Tap the dedicated buttons to launch VLC or MX Player with 1 tap!\n"
        "• <b>IDM / ADM:</b> Paste the <b>🚀 Direct Download Link</b> into download managers for multi-threaded speed."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📁 View Files & Load", callback_data="show_files_1"))
    await message.reply(help_text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.message(Command("files"))
@dp.message(Command("loads"))
async def cmd_files(message: types.Message):
    # Parse optional page number e.g. /files 2
    page = 1
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        page = max(1, int(parts[1]))

    user_id = message.from_user.id
    # Owner sees all files across the bot; regular users see their files
    filter_user = None if user_id == OWNER_ID else user_id
    text, markup = await build_files_page(filter_user, page=page, is_owner=(user_id == OWNER_ID))
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup, link_preview_options=types.LinkPreviewOptions(is_disabled=True))

async def build_files_page(filter_user: int | None, page: int = 1, is_owner: bool = False) -> tuple[str, types.InlineKeyboardMarkup]:
    page_size = 6
    files, total = await db.get_active_files(user_id=filter_user, page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    load = get_system_load()
    stats = await db.get_global_stats()
    active_mb = stats["active_bytes"] / (1024 * 1024)

    header = "<b>🦅 Current Files & System Load</b>\n" if is_owner else "<b>📁 Your Active Files & Bot Load</b>\n"
    meta_section = (
        f"{header}"
        f"• <b>Active Files:</b> <code>{total}</code> | <b>Volume:</b> <code>{active_mb:.1f} MB</code>\n"
        f"• <b>RAM Load:</b> <code>{load['proc_mem_mb']:.1f} MB</code> ({load['status']}) | <b>CPU:</b> <code>{load['cpu_pct']}%</code>\n"
        f"• <b>Total Downloads:</b> <code>{stats['total_downloads']}</code>\n"
        f"────────────────────\n"
    )

    if not files:
        body = "<i>No active files found. Send a file to register ID #1!</i>\n"
    else:
        body = ""
        for f in files:
            f_id = f["id"]
            name = f["file_name"]
            size_fmt = format_file_size(f["file_size"])
            time_left = format_time_remaining(f["expires_at"])
            dls = f["download_count"]
            body += f"<b>[#{f_id}]</b> <code>{name}</code>\n• Size: <code>{size_fmt}</code> | 👁️ {dls} | ⏳ {time_left}\n"

    footer = f"\n📄 <i>Page {page} of {total_pages} • Use /info &lt;id&gt; for full details</i>"

    builder = InlineKeyboardBuilder()
    # Add quick info buttons for the current files
    if files:
        btn_row = []
        for f in files[:4]:
            btn_row.append(types.InlineKeyboardButton(text=f"ℹ️ #{f['id']}", callback_data=f"info_file_{f['id']}"))
        builder.row(*btn_row)

    # Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(types.InlineKeyboardButton(text="⬅️ Prev", callback_data=f"show_files_{page - 1}"))
    nav_row.append(types.InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(types.InlineKeyboardButton(text="Next ➡️", callback_data=f"show_files_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    return (meta_section + body + footer, builder.as_markup())

@dp.message(Command("info"))
@dp.message(Command("file"))
async def cmd_info(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "<b>❓ Usage:</b> <code>/info &lt;id&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/info 1</code>\n"
            "• <code>/info #1</code>\n"
            "• <code>/info &lt;token&gt;</code>\n\n"
            "<i>Use /files to list all active file IDs.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    query_id = parts[1].strip()
    await send_file_info_card(message, query_id)

async def send_file_info_card(target_message: types.Message, query_id: str, edit: bool = False):
    record = await db.get_file_by_id_or_token(query_id)
    if not record:
        err_text = f"❌ <b>File Not Found:</b> No active record matching ID <code>{query_id}</code>.\n\n<i>It may have expired or been revoked. Check /files for active items.</i>"
        if edit:
            await target_message.edit_text(err_text, parse_mode=ParseMode.HTML)
        else:
            await target_message.reply(err_text, parse_mode=ParseMode.HTML)
        return

    f_id = record["id"]
    token = record["token"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    size_formatted = format_file_size(file_size)
    mime_type = record.get("mime_type") or "application/octet-stream"
    category = get_media_category(mime_type, file_name)
    dls = record["download_count"]
    uploader_id = record["user_id"]
    time_left = format_time_remaining(record["expires_at"])
    created_str = record["created_at"].replace("T", " ")[:19]

    dl_url = f"{SERVER_URL}/dl/{token}"
    watch_url = f"{SERVER_URL}/watch/{token}"
    vlc_url = f"vlc://{dl_url.replace('https://', '').replace('http://', '')}"
    mx_url = f"intent:{dl_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end"

    card = (
        f"<b>📋 File Record — ID #{f_id}</b>\n\n"
        f"📁 <b>Name:</b> <code>{file_name}</code>\n"
        f"📦 <b>Size:</b> <code>{size_formatted}</code> (<code>{file_size:,} bytes</code>)\n"
        f"🎭 <b>Type:</b> <code>{category.upper()}</code> (<code>{mime_type}</code>)\n"
        f"👤 <b>Uploader ID:</b> <code>{uploader_id}</code>\n"
        f"📅 <b>Created:</b> <code>{created_str} UTC</code>\n"
        f"⏳ <b>Status:</b> <code>{time_left}</code>\n"
        f"👁️ <b>Downloads & Streams:</b> <code>{dls} times</code>\n\n"
        f"<b>🚀 Direct Download Link:</b>\n"
        f"<code>{dl_url}</code>\n\n"
        f"<b>📺 Stream / Player URL:</b>\n"
        f"<code>{watch_url}</code>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📺 Web Player", url=watch_url),
        types.InlineKeyboardButton(text="🚀 Fast Download", url=dl_url)
    )
    if category == "video":
        builder.row(
            types.InlineKeyboardButton(text="⚡ VLC Player", url=vlc_url),
            types.InlineKeyboardButton(text="📱 MX Player", url=mx_url)
        )
    builder.row(
        types.InlineKeyboardButton(text="🗑️ Delete File", callback_data=f"revoke_id_{f_id}"),
        types.InlineKeyboardButton(text="📁 All Files", callback_data="show_files_1")
    )

    if edit:
        await target_message.edit_text(card, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup(), link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    else:
        await target_message.reply(card, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup(), link_preview_options=types.LinkPreviewOptions(is_disabled=True))

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
        f_id = f["id"]
        name = f["file_name"]
        size_str = format_file_size(f["file_size"])
        dls = f["download_count"]
        watch_url = f"{SERVER_URL}/watch/{token}"
        text += f"<b>#{f_id} • {name}</b>\n• Size: <code>{size_str}</code> | 👁️ {dls}\n• Stream: {watch_url}\n\n"
        builder.row(
            types.InlineKeyboardButton(text=f"ℹ️ Info #{f_id}", callback_data=f"info_file_{f_id}"),
            types.InlineKeyboardButton(text=f"🗑️ Revoke", callback_data=f"revoke_id_{f_id}")
        )

    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup(), link_preview_options=types.LinkPreviewOptions(is_disabled=True))

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = await db.get_global_stats()
    uptime = get_uptime_string()
    load = get_system_load()
    total_gb = stats["total_bytes"] / (1024**3)
    active_mb = stats["active_bytes"] / (1024**2)

    text = (
        f"<b>📊 {BRAND_NAME} — Platform Statistics</b>\n\n"
        f"• <b>Active Links:</b> <code>{stats['active_links']}</code> (<code>{active_mb:.1f} MB</code>)\n"
        f"• <b>Total Files Hosted:</b> <code>{stats['total_files']}</code>\n"
        f"• <b>Total Downloads & Streams:</b> <code>{stats['total_downloads']}</code>\n"
        f"• <b>Cumulative Data:</b> <code>{total_gb:.2f} GB</code>\n"
        f"• <b>Process RAM:</b> <code>{load['proc_mem_mb']:.1f} MB</code>\n"
        f"• <b>CPU Utilization:</b> <code>{load['cpu_pct']}%</code>\n"
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

@dp.callback_query(F.data.startswith("show_files_"))
async def callback_show_files(query: types.CallbackQuery):
    page = int(query.data.split("_")[2])
    user_id = query.from_user.id
    filter_user = None if user_id == OWNER_ID else user_id
    text, markup = await build_files_page(filter_user, page=page, is_owner=(user_id == OWNER_ID))
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    await query.answer()

@dp.callback_query(F.data.startswith("info_file_"))
async def callback_info_file(query: types.CallbackQuery):
    file_id = query.data.split("_")[2]
    await query.answer()
    await send_file_info_card(query.message, file_id, edit=True)

@dp.callback_query(F.data.startswith("revoke_id_"))
async def callback_revoke_id(query: types.CallbackQuery):
    f_id = query.data.split("_")[2]
    user_id = query.from_user.id
    deleted = await db.delete_file_by_id_or_token(f_id, user_id=None if user_id == OWNER_ID else user_id)
    if deleted:
        await query.answer(f"File #{f_id} permanently revoked! 🗑️", show_alert=True)
        await query.message.edit_text(f"<b>🗑️ File #{f_id} has been permanently deleted and revoked.</b>", parse_mode=ParseMode.HTML)
    else:
        await query.answer("Could not revoke. File may have already expired.", show_alert=True)

@dp.callback_query(F.data.startswith("revoke_"))
async def callback_revoke(query: types.CallbackQuery):
    token = query.data.split("_")[1]
    user_id = query.from_user.id
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

@dp.callback_query(F.data == "noop")
async def callback_noop(query: types.CallbackQuery):
    await query.answer()

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

    file_db_id = record["id"]
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
        types.InlineKeyboardButton(text="ℹ️ File Info", callback_data=f"info_file_{file_db_id}"),
        types.InlineKeyboardButton(text="🗑️ Revoke", callback_data=f"revoke_id_{file_db_id}")
    )
    builder.row(types.InlineKeyboardButton(text=f"📢 Join {CHANNEL_USERNAME}", url=channel_url))

    response_text = (
        f"<b>🦅 {BRAND_NAME} — Stream Link Ready!</b>\n\n"
        f"🆔 <b>File ID:</b> <code>#{file_db_id}</code>\n"
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
    asyncio.create_task(log_stream_generation(bot, message.from_user, file_db_id, file_name, size_formatted, dl_url))

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
