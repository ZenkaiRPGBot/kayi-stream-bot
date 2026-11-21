import os
import sys
import time
import secrets
import html
import subprocess
import asyncio
from datetime import datetime, timezone
import aiohttp
import psutil
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton,
    BotCommand, BotCommandScopeDefault, BotCommandScopeChat
)
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, BOT_START_TIME,
    BRAND_NAME, BOT_USERNAME, CHANNEL_USERNAME, COMMUNITY_URL,
    LINK_EXPIRY_HOURS, API_ID, API_HASH, IST, get_server_url
)
import database as db
from server import start_server, format_file_size, get_media_category

dp = Dispatcher()
HTTP_SESSION: aiohttp.ClientSession | None = None

# ==============================================================================
# SYSTEM & METRICS HELPERS
# ==============================================================================

def get_uptime_string() -> str:
    uptime_sec = int((datetime.now(IST) - BOT_START_TIME).total_seconds())
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0 or days > 0: parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "0s"

def get_system_load() -> dict:
    try:
        proc = psutil.Process()
        mem_info = proc.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        cpu_pct = proc.cpu_percent(interval=None)
        return {
            "proc_mem_mb": rss_mb,
            "cpu_pct": cpu_pct,
            "status": "Optimal" if rss_mb < 250 else "High"
        }
    except Exception:
        return {"proc_mem_mb": 0.0, "cpu_pct": 0.0, "status": "Normal"}

def format_date_str(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%b %d, %Y, %I:%M %p IST")
    except Exception:
        return "Recent"

async def measure_gateway_latency(bot: Bot) -> float:
    t0 = time.perf_counter()
    try:
        await bot.get_me()
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return 0.0

# ==============================================================================
# UI CARD BUILDERS
# ==============================================================================

def build_file_card_text(file_id: int, file_name: str, file_size: int, mime_type: str, watch_url: str, dl_url: str, is_cached: bool = False) -> str:
    category = get_media_category(mime_type, file_name)
    icon_map = {
        "video": "🎬 Video",
        "audio": "🎵 Audio",
        "image": "🖼️ Image",
        "pdf": "📄 PDF",
        "document": "📁 File"
    }
    type_label = icon_map.get(category, "📁 File")
    size_str = format_file_size(file_size)
    tag = " ⚡" if is_cached else ""

    return (
        f"<b>Stream Link Generated ✅{tag}</b>\n\n"
        f"• <b>File:</b> <code>{html.escape(file_name)}</code>\n"
        f"• <b>Size:</b> <code>{size_str}</code>\n"
        f"• <b>Type:</b> <code>{type_label}</code>\n"
        f"• <b>Engine:</b> <code>High-Speed RAM Stream</code> 🚀\n\n"
        f"<b>Stream / Watch Online 👇</b>\n"
        f"<code>{watch_url}</code>\n\n"
        f"<b>Direct Download URL 👇</b>\n"
        f"<code>{dl_url}</code>\n\n"
        "<i>Tap buttons below to stream, download, or copy:</i>"
    )

def build_file_markup(watch_url: str, dl_url: str, file_db_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Watch Online 🍿", url=watch_url, style="primary"),
            InlineKeyboardButton(text="Fast Download ⚡", url=dl_url, style="success")
        ],
        [
            InlineKeyboardButton(text="Copy Stream 📋", copy_text=CopyTextButton(text=watch_url)),
            InlineKeyboardButton(text="Copy Download 📋", copy_text=CopyTextButton(text=dl_url))
        ],
        [
            InlineKeyboardButton(text="File Details ℹ️", callback_data=f"info_file_{file_db_id}"),
            InlineKeyboardButton(text="Delete Link 🗑️", callback_data=f"del:ask:{file_db_id}", style="danger")
        ]
    ])

async def build_usage_card_text(bot: Bot) -> tuple[str, InlineKeyboardMarkup]:
    stats = await db.get_global_stats()
    sys_metrics = get_system_load()
    uptime_str = get_uptime_string()
    latency_ms = await measure_gateway_latency(bot)
    now_ist_str = datetime.now(IST).strftime("%d %b %Y, %I:%M:%S %p IST")
    total_bandwidth = format_file_size(stats["total_bytes"])
    active_storage = format_file_size(stats["active_bytes"])

    text = (
        f"<b>{BRAND_NAME} — Server Metrics 📊</b>\n\n"
        "<b>Streaming Engine Status:</b>\n"
        f"• <b>Health:</b> <code>Healthy & Active</code> 🟢\n"
        f"• <b>Engine:</b> <code>Pyrogram MTProto + Range Server</code>\n"
        f"• <b>Gateway Latency:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"• <b>Uptime:</b> <code>{uptime_str}</code>\n\n"
        "<b>Storage & Activity:</b>\n"
        f"• <b>Total Files Registered:</b> <code>{stats['total_files']}</code>\n"
        f"• <b>Active Streaming Links:</b> <code>{stats['active_links']}</code>\n"
        f"• <b>Active Storage Size:</b> <code>{active_storage}</code>\n"
        f"• <b>Total Downloads / Streams:</b> <code>{stats['total_downloads']}</code>\n"
        f"• <b>Bandwidth Transferred:</b> <code>{total_bandwidth}</code>\n\n"
        "<b>Hardware Resources:</b>\n"
        f"• <b>RAM Usage:</b> <code>{sys_metrics['proc_mem_mb']:.1f} MB</code>\n"
        f"• <b>CPU Usage:</b> <code>{sys_metrics['cpu_pct']:.1f}%</code>\n\n"
        f"🕒 <i>Updated: {now_ist_str}</i>"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Refresh 🔄", callback_data="usage:refresh", style="primary"),
            InlineKeyboardButton(text="Channel 👑", url=COMMUNITY_URL, style="success")
        ]
    ])
    return text, markup

# ==============================================================================
# STARTUP & RESTART NOTIFICATION
# ==============================================================================

async def setup_bot_commands(bot: Bot):
    default_commands = [
        BotCommand(command="start", description="Start bot & overview"),
        BotCommand(command="myfiles", description="View your active uploads"),
        BotCommand(command="files", description="Browse public catalog"),
        BotCommand(command="ping", description="Check latency & uptime"),
        BotCommand(command="help", description="How to stream in VLC / browser"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    owner_commands = default_commands + [
        BotCommand(command="stats", description="Bot statistics & metrics"),
        BotCommand(command="usage", description="System RAM/CPU load"),
        BotCommand(command="restart", description="Safe restart process")
    ]
    try:
        await bot.set_my_commands(owner_commands, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    except Exception:
        pass

async def send_restart_notification(bot: Bot):
    try:
        commit_res = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            capture_output=True, text=True, timeout=3
        )
        last_commit = commit_res.stdout.strip() if commit_res.returncode == 0 else "System initialization update"
    except Exception:
        last_commit = "System initialization update"

    now_ist_str = datetime.now(IST).strftime("%d %b %Y, %I:%M:%S %p IST")
    msg_text = (
        f"<b>{BRAND_NAME} Restarted 🚀</b>\n\n"
        f"• <b>Status:</b> <code>Online & Streaming</code> 🟢\n"
        f"• <b>Commit:</b> <code>{html.escape(last_commit)}</code>\n"
        f"• <b>Time:</b> <code>{now_ist_str}</code>\n\n"
        f"⚡ <i>Zero-disk MTProto chunk streaming ready.</i>"
    )

    targets = []
    if LOG_CHANNEL_ID:
        targets.append(LOG_CHANNEL_ID)
    if OWNER_ID and str(OWNER_ID) != LOG_CHANNEL_ID:
        targets.append(OWNER_ID)

    for chat_id in targets:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"[restart] Could not notify {chat_id}: {e}")

# ==============================================================================
# COMMAND HANDLERS
# ==============================================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    text = (
        f"<b>Welcome to {BRAND_NAME}!</b> 🚀\n\n"
        "Convert any video, anime episode, music track, or large document into a "
        "<b>high-speed web player and direct download link</b> within seconds.\n\n"
        "<b>Supported Media:</b>\n"
        "• <b>Videos & Movies:</b> MP4, MKV, WebM, AVI (Up to 2GB/4GB)\n"
        "• <b>Audio & Music:</b> MP3, FLAC, M4A, WAV, Opus\n"
        "• <b>Documents:</b> PDF, ZIP, APK, ISO, archives\n\n"
        "<b>Streaming Features:</b>\n"
        "• Native HTML5 in-browser video player with instant seek\n"
        "• Multi-audio and subtitle track support in VLC / MX Player\n"
        "• Fast chunked streaming without saving files to disk\n\n"
        "👉 <b>Send or forward any file below to generate your link!</b>"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="My Files 📂", callback_data="user:myfiles", style="primary"),
            InlineKeyboardButton(text="Catalog 🌐", callback_data="show_files_1")
        ],
        [
            InlineKeyboardButton(text="Channel 👑", url=COMMUNITY_URL, style="success")
        ]
    ])

    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        f"<b>{BRAND_NAME} — Streaming Guide</b> 📖\n\n"
        "<b>How to use:</b>\n"
        "1. Send or forward any video, audio, or document to the bot.\n"
        "2. The bot instantly provides <b>Stream</b> and <b>Download</b> links.\n"
        "3. Tap <b>Watch Online 🍿</b> to open the browser player, or launch in external hardware players.\n\n"
        "<b>Recommended Players:</b>\n"
        "• <b>Android:</b> MX Player, VLC for Android\n"
        "• <b>PC / Mac:</b> VLC Media Player, PotPlayer\n"
        "• <b>iOS:</b> Safari, VLC for Mobile, Outplayer\n"
        "• <b>Smart TV:</b> Kodi, VLC on Android TV\n\n"
        "<b>Commands:</b>\n"
        "• <code>/myfiles</code> — View and manage your uploads\n"
        "• <code>/files</code> — Browse public active files\n"
        "• <code>/info &lt;ID&gt;</code> — Detailed file metadata\n"
        "• <code>/ping</code> — Server latency & uptime"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Browse Catalog 🌐", callback_data="show_files_1", style="primary"),
            InlineKeyboardButton(text="My Files 📂", callback_data="user:myfiles")
        ]
    ])
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup)

@dp.message(Command("myfiles"))
@dp.message(Command("mylinks"))
async def cmd_myfiles(message: types.Message):
    user_id = message.from_user.id
    files = await db.get_user_files(user_id, limit=5)
    if not files:
        await message.reply(
            "<i>You don't have any active streaming files right now.\n"
            "Send any video or file to create your first link!</i>",
            parse_mode=ParseMode.HTML
        )
        return

    srv_url = get_server_url()
    lines = [f"<b>Your Active Streaming Files 📂</b>\n<i>Showing {len(files)} recent uploads</i>\n"]
    keyboard_rows = []

    for idx, f in enumerate(files, 1):
        f_id = f["id"]
        name = f["file_name"]
        size_str = format_file_size(f["file_size"])
        watch_url = f"{srv_url}/watch/{f_id}"
        dl_url = f"{srv_url}/dl/{f_id}"

        lines.append(f"<b>{idx}. ID {f_id}</b> · <code>{html.escape(name)}</code> ({size_str})")
        keyboard_rows.append([
            InlineKeyboardButton(text=f"Watch #{f_id} 🍿", url=watch_url, style="primary"),
            InlineKeyboardButton(text=f"Delete 🗑️", callback_data=f"del:ask:{f_id}", style="danger")
        ])

    keyboard_rows.append([
        InlineKeyboardButton(text="Refresh 🔄", callback_data="user:myfiles")
    ])

    await message.reply(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

@dp.message(Command("files"))
async def cmd_files(message: types.Message):
    page = 1
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        page = max(1, int(parts[1]))

    text, markup = await build_files_catalog(page=page)
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup)

async def build_files_catalog(page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    page_size = 5
    files, total = await db.get_active_files(page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    lines = [f"<b>Public Stream Catalog 🌐</b>\n<i>{total} active files · Page {page} of {total_pages}</i>\n"]
    srv_url = get_server_url()

    if not files:
        lines.append("<i>No active files found. Send a file to register ID 1!</i>")
    else:
        for f in files:
            f_id = f["id"]
            name = f["file_name"]
            size_fmt = format_file_size(f["file_size"])
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            fmt_label = ext.upper() if ext else "FILE"
            watch_url = f"{srv_url}/watch/{f_id}"
            lines.append(f"• <b>ID {f_id}</b> [{fmt_label} · {size_fmt}]\n  <a href=\"{watch_url}\">{html.escape(name)}</a>")

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Previous", callback_data=f"show_files_{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"show_files_{page + 1}"))
    nav_row.append(InlineKeyboardButton(text="Refresh 🔄", callback_data=f"show_files_{page}"))

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[nav_row])

@dp.message(Command("info"))
@dp.message(Command("file"))
async def cmd_info(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "<b>Usage:</b> <code>/info &lt;ID&gt;</code>\n\n"
            "<i>Example: <code>/info 1</code></i>",
            parse_mode=ParseMode.HTML
        )
        return

    query_id = parts[1].strip()
    await send_file_info_card(message, query_id)

async def send_file_info_card(message: types.Message, query_id: str):
    record = await db.get_file_by_id_or_token(query_id)
    if not record:
        await message.reply(f"❌ <i>No active file found with ID {html.escape(query_id)}.</i>", parse_mode=ParseMode.HTML)
        return

    f_id = record["id"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    mime_type = record["mime_type"]
    uploaded_str = format_date_str(record["created_at"])
    dls = record["download_count"]

    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{f_id}"
    watch_url = f"{srv_url}/watch/{f_id}"

    card_text = (
        f"<b>File Information ℹ️</b>\n\n"
        f"• <b>ID:</b> <code>{f_id}</code>\n"
        f"• <b>Name:</b> <code>{html.escape(file_name)}</code>\n"
        f"• <b>Size:</b> <code>{format_file_size(file_size)}</code>\n"
        f"• <b>Total Plays/Downloads:</b> <code>{dls}</code>\n"
        f"• <b>Uploaded:</b> <code>{uploaded_str}</code>\n\n"
        f"<b>Stream URL 👇</b>\n"
        f"<code>{watch_url}</code>\n\n"
        f"<b>Download URL 👇</b>\n"
        f"<code>{dl_url}</code>"
    )

    markup = build_file_markup(watch_url, dl_url, f_id)
    await message.reply(card_text, parse_mode=ParseMode.HTML, reply_markup=markup, link_preview_options=types.LinkPreviewOptions(is_disabled=True))

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message, bot: Bot):
    latency = await measure_gateway_latency(bot)
    uptime_str = get_uptime_string()
    sys_metrics = get_system_load()

    text = (
        "<b>Pong!</b> ⚡\n\n"
        f"• <b>Latency:</b> <code>{latency:.1f} ms</code>\n"
        f"• <b>Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Engine:</b> <code>Active & Healthy</code> 🟢\n"
        f"• <b>RAM Usage:</b> <code>{sys_metrics['proc_mem_mb']:.1f} MB</code>"
    )
    await message.reply(text, parse_mode=ParseMode.HTML)

@dp.message(Command("stats"))
@dp.message(Command("usage"))
async def cmd_stats(message: types.Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("Access restricted to bot owner.")
        return

    text, markup = await build_usage_card_text(bot)
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup)

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("Access denied. Owner only.")
        return
    await message.reply("<b>Restarting streaming server...</b>", parse_mode=ParseMode.HTML)
    if HTTP_SESSION and not HTTP_SESSION.closed:
        await HTTP_SESSION.close()
    await bot.session.close()
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ==============================================================================
# CALLBACK QUERY HANDLERS
# ==============================================================================

@dp.callback_query(F.data.startswith("show_files_"))
async def callback_show_files(query: types.CallbackQuery):
    page = int(query.data.split("_")[2])
    text, markup = await build_files_catalog(page=page)
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await query.answer()

@dp.callback_query(F.data == "user:myfiles")
async def callback_user_myfiles(query: types.CallbackQuery):
    await query.answer()
    await cmd_myfiles(query.message)

@dp.callback_query(F.data.startswith("info_file_"))
async def callback_info_file(query: types.CallbackQuery):
    file_id = query.data.split("_")[2]
    await query.answer()
    await send_file_info_card(query.message, file_id)

@dp.callback_query(F.data.startswith("del:ask:"))
async def cb_delete_ask(callback: types.CallbackQuery):
    f_id = int(callback.data.split(":")[2])
    record = await db.get_file_by_id_or_token(f_id)
    if not record:
        await callback.answer("File record not found or already deleted.", show_alert=True)
        return

    # Check permission
    if callback.from_user.id != record["user_id"] and callback.from_user.id != OWNER_ID:
        await callback.answer("⚠️ You can only delete your own uploads.", show_alert=True)
        return

    confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Confirm Delete 🗑️", callback_data=f"del:confirm:{f_id}", style="danger"),
            InlineKeyboardButton(text="Cancel ↩️", callback_data=f"del:cancel:{f_id}")
        ]
    ])

    try:
        await callback.message.edit_reply_markup(reply_markup=confirm_markup)
    except TelegramBadRequest:
        pass
    await callback.answer("Confirm deletion?")

@dp.callback_query(F.data.startswith("del:cancel:"))
async def cb_delete_cancel(callback: types.CallbackQuery):
    f_id = int(callback.data.split(":")[2])
    record = await db.get_file_by_id_or_token(f_id)
    if not record:
        await callback.answer("File record not found.", show_alert=True)
        return

    srv_url = get_server_url()
    watch_url = f"{srv_url}/watch/{f_id}"
    dl_url = f"{srv_url}/dl/{f_id}"
    original_markup = build_file_markup(watch_url, dl_url, f_id)

    try:
        await callback.message.edit_reply_markup(reply_markup=original_markup)
    except TelegramBadRequest:
        pass
    await callback.answer("Deletion cancelled.")

@dp.callback_query(F.data.startswith("del:confirm:"))
async def cb_delete_confirm(callback: types.CallbackQuery):
    f_id = int(callback.data.split(":")[2])
    record = await db.get_file_by_id_or_token(f_id)
    if not record:
        await callback.answer("File was already deleted.", show_alert=True)
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        return

    # Check permission
    if callback.from_user.id != record["user_id"] and callback.from_user.id != OWNER_ID:
        await callback.answer("⚠️ You can only delete your own uploads.", show_alert=True)
        return

    await db.delete_file_by_id_or_token(f_id)
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.answer("🗑️ Streaming link deleted successfully!", show_alert=True)

@dp.callback_query(F.data == "usage:refresh")
async def cb_usage_refresh(callback: types.CallbackQuery, bot: Bot):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Access restricted to bot owner.", show_alert=True)
        return

    text, markup = await build_usage_card_text(bot)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await callback.answer("Metrics refreshed.")

# ==============================================================================
# MEDIA UPLOAD HANDLER
# ==============================================================================

@dp.message(F.video | F.document | F.audio | F.voice | F.animation)
async def handle_media_file(message: types.Message):
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

    # 1. Deduplication Cache Check
    cached = await db.find_file_by_unique_id(file_unique_id)
    if cached:
        file_db_id = cached["id"]
        srv_url = get_server_url()
        watch_url = f"{srv_url}/watch/{file_db_id}"
        dl_url = f"{srv_url}/dl/{file_db_id}"
        card_text = build_file_card_text(
            file_id=file_db_id,
            file_name=cached["file_name"],
            file_size=cached["file_size"],
            mime_type=cached["mime_type"],
            watch_url=watch_url,
            dl_url=dl_url,
            is_cached=True
        )
        markup = build_file_markup(watch_url, dl_url, file_db_id)
        await message.reply(card_text, parse_mode=ParseMode.HTML, reply_markup=markup, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        return

    # 2. Save new record to database
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
    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{file_db_id}"
    watch_url = f"{srv_url}/watch/{file_db_id}"

    # 3. Build Single Clean Response Card
    card_text = build_file_card_text(
        file_id=file_db_id,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        watch_url=watch_url,
        dl_url=dl_url,
        is_cached=False
    )
    markup = build_file_markup(watch_url, dl_url, file_db_id)

    await message.reply(
        card_text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

async def main():
    global HTTP_SESSION
    if not BOT_TOKEN:
        print("\nERROR: BOT_TOKEN is missing in .env!\n")
        sys.exit(1)

    print(f"Launching {BRAND_NAME} Bot...")
    await db.init_db()

    # Clean expired records on startup
    cleaned = await db.cleanup_expired_files()
    if cleaned > 0:
        print(f"[db] Cleaned {cleaned} expired files on startup.")

    # Start streaming server with MTProto
    server_runner = await start_server()

    # Shared HTTP ClientSession
    HTTP_SESSION = aiohttp.ClientSession()

    bot = Bot(token=BOT_TOKEN)
    await setup_bot_commands(bot)
    await send_restart_notification(bot)

    print(f"{BRAND_NAME} Bot active. Serving requests with zero-disk RAM chunk streaming.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if HTTP_SESSION and not HTTP_SESSION.closed:
            await HTTP_SESSION.close()
        await bot.session.close()
        await server_runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot shutting down safely...")
