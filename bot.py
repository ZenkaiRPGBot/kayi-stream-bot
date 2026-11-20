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

def format_date_str(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%b %d, %Y, %H:%M")
    except Exception:
        return "Recent"

async def send_rich_msg(chat_id: int | str, html: str, reply_markup: dict | None = None) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage"
    payload = {
        "chat_id": chat_id,
        "rich_message": {"html": html}
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        if HTTP_SESSION:
            async with HTTP_SESSION.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return True
                print(f"[rich_msg] sendRichMessage error: {data}")
    except Exception as e:
        print(f"[rich_msg] Exception: {e}")

    # Fallback to standard sendMessage with HTML parse_mode
    fallback_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Strip rich table tags for basic HTML if falling back
    clean_text = re_clean_html_fallback(html)
    fb_payload = {
        "chat_id": chat_id,
        "text": clean_text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        fb_payload["reply_markup"] = reply_markup

    try:
        if HTTP_SESSION:
            async with HTTP_SESSION.post(fallback_url, json=fb_payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                return bool(data.get("ok"))
    except Exception as e:
        print(f"[rich_msg] Fallback exception: {e}")
    return False

def re_clean_html_fallback(html: str) -> str:
    # Quick fallback conversion for standard sendMessage if richMessage is unavailable
    text = html.replace("<table bordered striped>", "").replace("</table>", "")
    text = text.replace("<tr>", "").replace("</tr>", "\n")
    text = text.replace("<th>", "<b>").replace("</th>", ":</b> ")
    text = text.replace("<td>", " ").replace("</td>", " ")
    text = text.replace("<h2>", "<b>").replace("</h2>", "</b>\n")
    text = text.replace("<h3>", "<b>").replace("</h3>", "</b>\n")
    text = text.replace("<h4>", "<b>").replace("</h4>", "</b>\n")
    text = text.replace("<p>", "").replace("</p>", "\n")
    return text.strip()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    html = f"""<h2>{BRAND_NAME}</h2>
<p>Send any file and get a direct download link and a web player within seconds.</p>

<blockquote>Videos, anime, music, and documents up to 4 GB.<br>
Links play in any browser and open in VLC, MX Player, and PotPlayer.</blockquote>

<h3>Commands</h3>
<table bordered striped>
<tr><th>Command</th><th>What it does</th></tr>
<tr><td>/files</td><td>Browse the public catalog</td></tr>
<tr><td>/myfiles</td><td>Your uploads</td></tr>
<tr><td>/info ID</td><td>Details for one file</td></tr>
<tr><td>/stats</td><td>Service overview</td></tr>
</table>"""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Browse Catalog", "callback_data": "show_files_1", "style": "primary"},
                {"text": "My Files", "callback_data": "my_files"}
            ],
            [
                {"text": f"Join {CHANNEL_USERNAME}", "url": f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"}
            ]
        ]
    }
    await send_rich_msg(message.chat.id, html, reply_markup=keyboard)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    html = f"""<h2>Streaming Guide</h2>
<p>Watch in your browser or launch directly in third-party hardware players.</p>

<blockquote>Web Player supports native HTML5 streaming with instant seek.<br>
For multi-audio and anime subtitle tracks, open in VLC or MX Player.</blockquote>

<h3>Platforms</h3>
<table bordered striped>
<tr><th>Device</th><th>Recommended App</th></tr>
<tr><td>Browser</td><td>Chrome, Safari, Edge, Firefox</td></tr>
<tr><td>Android</td><td>MX Player, VLC for Android</td></tr>
<tr><td>PC / Mac</td><td>VLC, PotPlayer</td></tr>
<tr><td>Smart TV</td><td>Kodi, VLC on Android TV</td></tr>
</table>"""

    keyboard = {
        "inline_keyboard": [
            [{"text": "Browse Catalog", "callback_data": "show_files_1", "style": "primary"}]
        ]
    }
    await send_rich_msg(message.chat.id, html, reply_markup=keyboard)

@dp.message(Command("files"))
@dp.message(Command("loads"))
async def cmd_files(message: types.Message):
    page = 1
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        page = max(1, int(parts[1]))

    html, markup = await build_files_catalog(page=page)
    await send_rich_msg(message.chat.id, html, reply_markup=markup)

async def build_files_catalog(page: int = 1) -> tuple[str, dict]:
    page_size = 5
    files, total = await db.get_active_files(page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    html = f"""<h2>Catalog</h2>
<p><i>{total} active files · Page {page} of {total_pages}</i></p>
"""

    if not files:
        html += "<p>No active files found. Send a file to register ID 1!</p>"
    else:
        for f in files:
            f_id = f["id"]
            name = f["file_name"]
            size_fmt = format_file_size(f["file_size"])
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            fmt_label = ext.upper() if ext else "FILE"
            html += f"<h4>ID {f_id} · {fmt_label} · {size_fmt}</h4>\n<p>{name}</p>\n"

    nav_row = []
    if page > 1:
        nav_row.append({"text": "Previous", "callback_data": f"show_files_{page - 1}", "style": "primary"})
    if page < total_pages:
        nav_row.append({"text": "Next", "callback_data": f"show_files_{page + 1}", "style": "primary"})
    nav_row.append({"text": "Refresh", "callback_data": f"show_files_{page}"})

    inline_keyboard = [nav_row]
    return (html, {"inline_keyboard": inline_keyboard})

@dp.message(Command("info"))
@dp.message(Command("file"))
async def cmd_info(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        html = """<h2>Command Usage</h2>
<p>Specify the file ID to view its details.</p>
<p>Example: <code>/info 1</code></p>
<p>Type /files to browse the catalog.</p>"""
        await send_rich_msg(message.chat.id, html)
        return

    query_id = parts[1].strip()
    await send_file_info_card(message.chat.id, query_id)

async def send_file_info_card(chat_id: int | str, query_id: str):
    record = await db.get_file_by_id_or_token(query_id)
    if not record:
        html = f"""<h2>File Not Found</h2>
<p>No file with ID {query_id}. Try /files to browse the catalog.</p>"""
        await send_rich_msg(chat_id, html)
        return

    f_id = record["id"]
    token = record["token"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    size_formatted = format_file_size(file_size)
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    fmt_label = ext.upper() if ext else "FILE"
    dls = record["download_count"]
    uploaded_str = format_date_str(record["created_at"])

    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{f_id}"
    watch_url = f"{srv_url}/watch/{f_id}"

    html = f"""<h2>ID {f_id}</h2>
<h3>{file_name}</h3>

<table bordered striped>
<tr><th>Size</th><td>{size_formatted}</td></tr>
<tr><th>Format</th><td>{fmt_label}</td></tr>
<tr><th>Uploaded</th><td>{uploaded_str}</td></tr>
<tr><th>Views</th><td>{dls}</td></tr>
</table>"""

    keyboard_rows = [
        [
            {"text": "Watch Online", "url": watch_url, "style": "primary"},
            {"text": "Direct Download", "url": dl_url, "style": "success"}
        ],
        [
            {"text": "Browse Catalog", "callback_data": "show_files_1"},
            {"text": "Delete", "callback_data": f"confirm_del_{f_id}", "style": "danger"}
        ]
    ]

    await send_rich_msg(chat_id, html, reply_markup={"inline_keyboard": keyboard_rows})

@dp.message(Command("myfiles"))
async def cmd_myfiles(message: types.Message):
    user_id = message.from_user.id
    files = await db.get_user_files(user_id, limit=5)
    if not files:
        html = """<h2>Your files</h2>
<p>You have no active uploads right now.</p>
<p>Send any video, music, or document to create your first link!</p>"""
        await send_rich_msg(message.chat.id, html)
        return

    html = f"""<h2>Your files</h2>
<p><i>{len(files)} uploads</i></p>
"""
    keyboard_rows = []
    srv_url = get_server_url()

    for f in files:
        f_id = f["id"]
        name = f["file_name"]
        size_str = format_file_size(f["file_size"])
        watch_url = f"{srv_url}/watch/{f_id}"
        html += f"<h4>ID {f_id} · {size_str}</h4>\n<p>{name}</p>\n"
        keyboard_rows.append([
            {"text": f"Watch ID {f_id}", "url": watch_url, "style": "primary"},
            {"text": "Delete", "callback_data": f"confirm_del_{f_id}", "style": "danger"}
        ])

    await send_rich_msg(message.chat.id, html, reply_markup={"inline_keyboard": keyboard_rows})

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = await db.get_global_stats()
    uptime = get_uptime_string()
    total_storage = format_file_size(stats["total_bytes"])

    html = f"""<h2>Overview</h2>

<table bordered striped>
<tr><th>Files</th><td>{stats['total_files']}</td></tr>
<tr><th>Storage</th><td>{total_storage}</td></tr>
<tr><th>Downloads</th><td>{stats['total_downloads']}</td></tr>
<tr><th>Active</th><td>{stats['active_links']}</td></tr>
<tr><th>Uptime</th><td>{uptime}</td></tr>
</table>"""

    keyboard = {
        "inline_keyboard": [
            [{"text": "Refresh", "callback_data": "refresh_stats", "style": "primary"}]
        ]
    }
    await send_rich_msg(message.chat.id, html, reply_markup=keyboard)

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message, bot: Bot):
    t0 = time.perf_counter()
    await bot.get_me()
    latency = (time.perf_counter() - t0) * 1000
    uptime = get_uptime_string()
    html = f"""<h2>Latency Check</h2>

<table bordered striped>
<tr><th>Latency</th><td>{latency:.1f} ms</td></tr>
<tr><th>Uptime</th><td>{uptime}</td></tr>
<tr><th>Status</th><td>Online</td></tr>
</table>"""
    await send_rich_msg(message.chat.id, html)

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
    html, markup = await build_files_catalog(page=page)
    await query.message.delete()
    await send_rich_msg(query.message.chat.id, html, reply_markup=markup)
    await query.answer()

@dp.callback_query(F.data == "my_files")
async def callback_my_files(query: types.CallbackQuery):
    await query.answer()
    await cmd_myfiles(query.message)

@dp.callback_query(F.data.startswith("info_file_"))
async def callback_info_file(query: types.CallbackQuery):
    file_id = query.data.split("_")[2]
    await query.answer()
    await send_file_info_card(query.message.chat.id, file_id)

@dp.callback_query(F.data.startswith("confirm_del_"))
async def callback_confirm_del(query: types.CallbackQuery):
    f_id = query.data.split("_")[2]
    await query.answer()
    html = f"""<h3>Delete ID {f_id}?</h3>
<p>This removes the file and its links. It cannot be undone.</p>"""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Confirm Delete", "callback_data": f"do_del_{f_id}", "style": "danger"},
                {"text": "Cancel", "callback_data": "cancel_del"}
            ]
        ]
    }
    await send_rich_msg(query.message.chat.id, html, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("do_del_"))
async def callback_do_del(query: types.CallbackQuery):
    f_id = query.data.split("_")[2]
    user_id = query.from_user.id
    deleted = await db.delete_file_by_id_or_token(f_id, user_id=None if user_id == OWNER_ID else user_id)
    if deleted:
        await query.answer(f"File ID {f_id} deleted.", show_alert=True)
        html = f"""<h2>File Deleted</h2>
<p>ID {f_id} and its streaming links have been permanently removed.</p>"""
        await query.message.delete()
        await send_rich_msg(query.message.chat.id, html)
    else:
        await query.answer("Could not delete. Link may have already expired.", show_alert=True)

@dp.callback_query(F.data == "cancel_del")
async def callback_cancel_del(query: types.CallbackQuery):
    await query.answer("Deletion cancelled.")
    await query.message.delete()

@dp.callback_query(F.data == "refresh_stats")
async def callback_refresh_stats(query: types.CallbackQuery):
    await query.answer("Stats refreshed.")
    await query.message.delete()
    await cmd_stats(query.message)

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

    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    fmt_label = ext.upper() if ext else "FILE"

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
    added_str = format_date_str(record["created_at"])

    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{file_db_id}"
    watch_url = f"{srv_url}/watch/{file_db_id}"

    # Claude Upload Response Specification
    html = f"""<h2>File ready</h2>
<h3>{file_name}</h3>

<table bordered striped>
<tr><th>ID</th><td>{file_db_id}</td></tr>
<tr><th>Size</th><td>{size_formatted}</td></tr>
<tr><th>Format</th><td>{fmt_label}</td></tr>
<tr><th>Added</th><td>{added_str}</td></tr>
</table>

<p>Watch in the browser, or download the original file.</p>"""

    keyboard_rows = [
        [
            {"text": "Watch Online", "url": watch_url, "style": "primary"},
            {"text": "Direct Download", "url": dl_url, "style": "success"}
        ],
        [
            {"text": "Details", "callback_data": f"info_file_{file_db_id}"},
            {"text": "Delete", "callback_data": f"confirm_del_{file_db_id}", "style": "danger"}
        ]
    ]

    sent = await send_rich_msg(message.chat.id, html, reply_markup={"inline_keyboard": keyboard_rows})
    if not sent:
        # Fallback to standard HTML
        await message.reply(
            f"<b>File ready</b>\n\n"
            f"<b>{file_name}</b>\n"
            f"• <b>ID:</b> {file_db_id}\n"
            f"• <b>Size:</b> {size_formatted}\n"
            f"• <b>Player:</b> {watch_url}\n"
            f"• <b>Download:</b> {dl_url}",
            parse_mode=ParseMode.HTML,
            link_preview_options=types.LinkPreviewOptions(is_disabled=True)
        )

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
