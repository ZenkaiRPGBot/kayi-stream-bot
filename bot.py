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

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, BOT_START_TIME,
    BRAND_NAME, BOT_USERNAME, CHANNEL_USERNAME, LINK_EXPIRY_HOURS,
    API_ID, API_HASH, get_server_url
)
import database as db
from server import start_server, format_file_size, get_media_category

dp = Dispatcher()
HTTP_SESSION: aiohttp.ClientSession | None = None

def is_valid_tg_button_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    if u.startswith("tg://"):
        return True
    if u.startswith("http://") or u.startswith("https://"):
        if "localhost" in u or "127.0.0.1" in u:
            return False
        return True
    return False

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
        return {
            "proc_mem_mb": rss_mb,
            "cpu_pct": cpu_pct,
            "status": "Optimal" if rss_mb < 250 else "High"
        }
    except Exception:
        return {"proc_mem_mb": 0.0, "cpu_pct": 0.0, "status": "Normal"}

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

async def send_rich_msg(chat_id: int | str, markdown: str, reply_markup: dict | None = None) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage"
    payload = {
        "chat_id": chat_id,
        "rich_message": {"markdown": markdown}
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        if HTTP_SESSION:
            async with HTTP_SESSION.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return True
                print(f"[rich_msg] Error: {data}")
    except Exception as e:
        print(f"[rich_msg] Exception: {e}")
    return False

def build_rich_restart_markdown() -> str:
    return f"""# {BRAND_NAME} Online

• **Version:** `2.5 Enterprise MTProto`
• **Engine:** `Pyrogram MTProto 2GB+ Pipeline`
• **Status:** `Active & Ready`

### 🚀 Capabilities
- High-speed direct browser downloads with RFC 7233 byte-range seeking
- Executive glassmorphic Web Player with Ambilight and Theater Mode
- Real-time catalog with sequential File IDs (1, 2, etc.) sorted low to high
- Zero-disk RAM-optimized chunked streaming up to 2GB/4GB

*Ready to stream media.*"""

async def send_rich_restart_notification(bot: Bot):
    rich_md = build_rich_restart_markdown()
    if OWNER_ID:
        await send_rich_msg(OWNER_ID, rich_md)
    if LOG_CHANNEL_ID:
        await send_rich_msg(LOG_CHANNEL_ID, rich_md)

async def log_stream_generation(user: types.User, file_id_num: int, file_name: str, file_size: str, dl_url: str):
    if not LOG_CHANNEL_ID:
        return
    md = f"""# ⚡ Link Generated

• **File ID:** `{file_id_num}`
• **User:** `{user.full_name}` (`{user.id}`)
• **File:** `{file_name}`
• **Size:** `{file_size}`

[Direct Download]({dl_url})"""
    await send_rich_msg(LOG_CHANNEL_ID, md)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    md = f"""# 🦅 {BRAND_NAME}

• **Direct Download:** Full-speed download links (IDM & ADM compatible)
• **Web Player:** Cinema-grade online streaming with real-time Ambilight
• **App Stream:** 1-Tap playback in VLC, MX Player, and PotPlayer
• **File Indexing:** Every file receives a clean numerical ID

### Getting Started
Send or forward any **Video, Audio, or Document** to this chat to generate your link instantly."""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Active Files", "callback_data": "show_files_1", "style": "primary"},
                {"text": "Streaming Guide", "callback_data": "help_guide", "style": "success"}
            ],
            [
                {"text": f"Join {CHANNEL_USERNAME}", "url": f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"}
            ]
        ]
    }
    sent = await send_rich_msg(message.chat.id, md, reply_markup=keyboard)
    if not sent:
        await message.reply(md, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    md = f"""# 📖 {BRAND_NAME} — Streaming Guide

• **Browser:** Chrome, Edge, Safari, Firefox for instant Web Player
• **Android:** MX Player or VLC (paste direct link or launch from Web Player)
• **PC / Mac:** VLC or PotPlayer (Media ➔ Open Network Stream)
• **Smart TV:** Kodi or VLC for Android TV / FireStick

### Commands
- `/files [page]` — View active catalog sorted low to high with system load
- `/info <id>` — Deep technical inspection for any file ID
- `/myfiles` — Quick list of your generated links
- `/stats` — Platform metrics and bandwidth volume
- `/ping` — Real-time latency and uptime diagnostics"""

    keyboard = {
        "inline_keyboard": [
            [{"text": "View Files & Load", "callback_data": "show_files_1", "style": "primary"}]
        ]
    }
    await send_rich_msg(message.chat.id, md, reply_markup=keyboard)

@dp.message(Command("files"))
@dp.message(Command("loads"))
async def cmd_files(message: types.Message):
    page = 1
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        page = max(1, int(parts[1]))

    user_id = message.from_user.id
    filter_user = None if user_id == OWNER_ID else user_id
    md, markup = await build_files_markdown(filter_user, page=page, is_owner=(user_id == OWNER_ID))
    await send_rich_msg(message.chat.id, md, reply_markup=markup)

async def build_files_markdown(filter_user: int | None, page: int = 1, is_owner: bool = False) -> tuple[str, dict]:
    page_size = 5
    files, total = await db.get_active_files(user_id=filter_user, page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    load = get_system_load()
    stats = await db.get_global_stats()
    active_mb = stats["active_bytes"] / (1024 * 1024)

    title = "🦅 Current Files & System Load" if is_owner else "📁 Your Active Files & Load"

    header_block = f"""# {title}

• **Active Files:** `{total}`
• **Storage Volume:** `{active_mb:.1f} MB`
• **RAM Load:** `{load['proc_mem_mb']:.1f} MB` ({load['status']})
• **Total Downloads:** `{stats['total_downloads']}`

---
"""

    if not files:
        catalog_section = "\n*No active files found. Send a file to register ID 1!*"
    else:
        catalog_section = "### 📁 Active Catalog (Sorted ID 1 → N)\n\n"
        for f in files:
            f_id = f["id"]
            name = f["file_name"]
            size_fmt = format_file_size(f["file_size"])
            time_left = format_time_remaining(f["expires_at"])
            catalog_section += f"**ID: {f_id}** • `{size_fmt}` • `{time_left}`\n`{name}`\n\n"

    footer = f"---\n*Page {page} of {total_pages} • Type /info <id> for details*"

    btn_row_info = []
    if files:
        for f in files[:4]:
            btn_row_info.append({"text": f"Info {f['id']}", "callback_data": f"info_file_{f['id']}", "style": "primary"})

    nav_row = []
    if page > 1:
        nav_row.append({"text": "Previous", "callback_data": f"show_files_{page - 1}", "style": "primary"})
    nav_row.append({"text": f"{page} / {total_pages}", "callback_data": "noop"})
    if page < total_pages:
        nav_row.append({"text": "Next", "callback_data": f"show_files_{page + 1}", "style": "primary"})

    inline_keyboard = []
    if btn_row_info:
        inline_keyboard.append(btn_row_info)
    if nav_row:
        inline_keyboard.append(nav_row)

    return (header_block + catalog_section + footer, {"inline_keyboard": inline_keyboard})

@dp.message(Command("info"))
@dp.message(Command("file"))
async def cmd_info(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        md = """# ❓ Command Usage

• `/info 1` — Inspect file by numerical ID
• `/info <token>` — Lookup by unique URL token

*Type /files to view all active file IDs.*"""
        await send_rich_msg(message.chat.id, md)
        return

    query_id = parts[1].strip()
    await send_file_info_card(message.chat.id, query_id)

async def send_file_info_card(chat_id: int | str, query_id: str):
    record = await db.get_file_by_id_or_token(query_id)
    if not record:
        md = f"""# ❌ File Not Found

• **Query:** `{query_id}`
• **Status:** `Expired or Revoked`

*Check /files to view current active catalog.*"""
        await send_rich_msg(chat_id, md)
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

    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{token}"
    watch_url = f"{srv_url}/watch/{token}"

    md = f"""# 📋 File Details — ID {f_id}

• **File Name:**
`{file_name}`
• **File ID:** `{f_id}`
• **Size:** `{size_formatted}` (`{file_size:,} bytes`)
• **Media Type:** `{category.upper()}` (`{mime_type}`)
• **Uploader:** `{uploader_id}`
• **Uploaded At:** `{created_str} UTC`
• **Validity:** `{time_left}`
• **Downloads:** `{dls} times`

### 🚀 Direct Links
- **Web Player:** `{watch_url}`
- **Direct Link:** `{dl_url}`"""

    keyboard_rows = [
        [
            {"text": "Watch Online", "url": watch_url, "style": "success"},
            {"text": "Direct Download", "url": dl_url, "style": "primary"}
        ],
        [
            {"text": "Delete File", "callback_data": f"revoke_id_{f_id}", "style": "danger"},
            {"text": "All Files", "callback_data": "show_files_1", "style": "primary"}
        ]
    ]

    await send_rich_msg(chat_id, md, reply_markup={"inline_keyboard": keyboard_rows})

@dp.message(Command("myfiles"))
async def cmd_myfiles(message: types.Message):
    user_id = message.from_user.id
    files = await db.get_user_files(user_id, limit=6)
    if not files:
        md = """# 📁 My Active Files

*You have no active streaming links right now.*
Send any video or file to generate your first link!"""
        await send_rich_msg(message.chat.id, md)
        return

    md = f"# 📁 Your Active Links ({len(files)} Recent)\n\n"
    keyboard_rows = []

    for f in files:
        f_id = f["id"]
        name = f["file_name"]
        size_str = format_file_size(f["file_size"])
        dls = f["download_count"]
        md += f"**ID: {f_id}** • `{size_str}` • `{dls} views`\n`{name}`\n\n"
        keyboard_rows.append([
            {"text": f"Details {f_id}", "callback_data": f"info_file_{f_id}", "style": "primary"},
            {"text": "Revoke", "callback_data": f"revoke_id_{f_id}", "style": "danger"}
        ])

    md += "---\n*Tap Details to inspect player and streaming links.*"
    await send_rich_msg(message.chat.id, md, reply_markup={"inline_keyboard": keyboard_rows})

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = await db.get_global_stats()
    uptime = get_uptime_string()
    load = get_system_load()
    total_gb = stats["total_bytes"] / (1024**3)
    active_mb = stats["active_bytes"] / (1024**2)

    md = f"""# 📊 {BRAND_NAME} Statistics

• **Active Links:** `{stats['active_links']}` (`{active_mb:.1f} MB`)
• **Total Files:** `{stats['total_files']}`
• **Total Downloads:** `{stats['total_downloads']}`
• **Cumulative Data:** `{total_gb:.2f} GB`
• **Process RAM:** `{load['proc_mem_mb']:.1f} MB`
• **CPU Load:** `{load['cpu_pct']}%`
• **Uptime:** `{uptime}`
• **MTProto Engine:** `Connected 🟢`"""

    await send_rich_msg(message.chat.id, md)

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message, bot: Bot):
    t0 = time.perf_counter()
    await bot.get_me()
    latency = (time.perf_counter() - t0) * 1000
    uptime = get_uptime_string()
    md = f"""# 🦅 {BRAND_NAME} Pong

• **API Latency:** `{latency:.1f} ms`
• **System Uptime:** `{uptime}`
• **Status:** `Healthy 🟢`"""
    await send_rich_msg(message.chat.id, md)

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
    md, markup = await build_files_markdown(filter_user, page=page, is_owner=(user_id == OWNER_ID))
    await query.message.delete()
    await send_rich_msg(query.message.chat.id, md, reply_markup=markup)
    await query.answer()

@dp.callback_query(F.data.startswith("info_file_"))
async def callback_info_file(query: types.CallbackQuery):
    file_id = query.data.split("_")[2]
    await query.answer()
    await send_file_info_card(query.message.chat.id, file_id)

@dp.callback_query(F.data.startswith("revoke_id_"))
async def callback_revoke_id(query: types.CallbackQuery):
    f_id = query.data.split("_")[2]
    user_id = query.from_user.id
    deleted = await db.delete_file_by_id_or_token(f_id, user_id=None if user_id == OWNER_ID else user_id)
    if deleted:
        await query.answer(f"File ID {f_id} revoked! 🗑️", show_alert=True)
        md = f"""# 🗑️ Link Revoked

• **File ID:** `{f_id}`
• **Action:** `Permanently Deleted`

*This stream link is now dead.*"""
        await send_rich_msg(query.message.chat.id, md)
    else:
        await query.answer("Could not revoke. File may have already expired.", show_alert=True)

@dp.callback_query(F.data == "help_guide")
async def callback_help(query: types.CallbackQuery):
    await query.answer()
    await cmd_help(query.message)

@dp.callback_query(F.data == "noop")
async def callback_noop(query: types.CallbackQuery):
    await query.answer()

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
    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{token}"
    watch_url = f"{srv_url}/watch/{token}"

    md = f"""# 🦅 Link Ready — ID {file_db_id}

• **File Name:**
`{file_name}`
• **File ID:** `{file_db_id}`
• **Size:** `{size_formatted}`
• **Format:** `{cat_label}`
• **Validity:** `{LINK_EXPIRY_HOURS} Hours`

### 🚀 Direct Links
- **Web Player:** `{watch_url}`
- **Fast Download:** `{dl_url}`

*Stream directly in browser, VLC, or MX Player with full seeking.*"""

    keyboard_rows = []
    if is_valid_tg_button_url(watch_url) and is_valid_tg_button_url(dl_url):
        keyboard_rows.append([
            {"text": "Watch Online", "url": watch_url, "style": "success"},
            {"text": "Download", "url": dl_url, "style": "primary"}
        ])

    keyboard_rows.append([
        {"text": "Details", "callback_data": f"info_file_{file_db_id}", "style": "primary"},
        {"text": "Revoke Link", "callback_data": f"revoke_id_{file_db_id}", "style": "danger"}
    ])
    keyboard_rows.append([
        {"text": f"Join {CHANNEL_USERNAME}", "url": f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"}
    ])

    sent = await send_rich_msg(message.chat.id, md, reply_markup={"inline_keyboard": keyboard_rows})
    if not sent:
        # Fallback to standard HTML if rich message encounters error
        await message.reply(
            f"<b>🦅 Link Ready — ID {file_db_id}</b>\n\n"
            f"• <b>File:</b> <code>{file_name}</code>\n"
            f"• <b>Size:</b> <code>{size_formatted}</code>\n"
            f"• <b>Player:</b> {watch_url}\n"
            f"• <b>Download:</b> {dl_url}",
            parse_mode=ParseMode.HTML,
            link_preview_options=types.LinkPreviewOptions(is_disabled=True)
        )

    # Log to channel in background
    asyncio.create_task(log_stream_generation(message.from_user, file_db_id, file_name, size_formatted, dl_url))

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

    # Auto-restart notification
    asyncio.create_task(send_rich_restart_notification(bot))

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
