import os
import sys
import time
import secrets
import html
import subprocess
import asyncio
from datetime import datetime
import aiohttp
import psutil
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton,
    BotCommand, BotCommandScopeDefault, BotCommandScopeChat,
    MenuButtonWebApp, WebAppInfo
)
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, BOT_START_TIME,
    BRAND_NAME, BOT_USERNAME, CHANNEL_USERNAME, COMMUNITY_URL, DEVELOPER_URL,
    WELCOME_VIDEO_FILE_ID,
    LINK_EXPIRY_HOURS, API_ID, API_HASH, IST, get_server_url
)
import database as db
from server import start_server, format_file_size, get_media_category
from fsub import FSubMiddleware, check_channel_membership

dp = Dispatcher()
dp.message.outer_middleware(FSubMiddleware())
dp.callback_query.outer_middleware(FSubMiddleware())

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

def build_file_card_text(file_name: str, file_size: int, mime_type: str, watch_url: str, dl_url: str, is_cached: bool = False) -> str:
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

    # Clean single card WITHOUT showing technical ID to normal users
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

def build_file_markup(watch_url: str, dl_url: str, display_id: str) -> InlineKeyboardMarkup:
    # Telegram WebApp for seamless in-app streaming
    if watch_url.startswith("https://"):
        watch_btn = InlineKeyboardButton(text="Watch in WebApp 🍿", web_app=types.WebAppInfo(url=watch_url), style="primary")
    else:
        watch_btn = InlineKeyboardButton(text="Watch Online 🍿", url=watch_url, style="primary")

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            watch_btn,
            InlineKeyboardButton(text="Fast Download ⚡", url=dl_url, style="success")
        ],
        [
            InlineKeyboardButton(text="Copy Stream 📋", copy_text=CopyTextButton(text=watch_url)),
            InlineKeyboardButton(text="Copy Download 📋", copy_text=CopyTextButton(text=dl_url))
        ],
        [
            InlineKeyboardButton(text="File Details ℹ️", callback_data=f"info_file_{display_id}"),
            InlineKeyboardButton(text="Delete Link 🗑️", callback_data=f"del:ask:{display_id}", style="danger")
        ]
    ])

# ==============================================================================
# BUTTONED STATS / USAGE BUILDER (Logical Tabs, No Channel Link)
# ==============================================================================

async def build_stats_view(bot: Bot, tab: str = "overview") -> tuple[str, InlineKeyboardMarkup]:
    stats = await db.get_global_stats()
    sys_metrics = get_system_load()
    uptime_str = get_uptime_string()
    latency_ms = await measure_gateway_latency(bot)
    now_ist_str = datetime.now(IST).strftime("%d %b %Y, %I:%M:%S %p IST")
    total_bandwidth = format_file_size(stats["total_bytes"])
    active_storage = format_file_size(stats["active_bytes"])

    if tab == "system":
        text = (
            f"<b>{BRAND_NAME} — Server & Hardware Load ⚙️</b>\n\n"
            "<b>Hardware Metrics:</b>\n"
            f"• <b>RAM Consumption:</b> <code>{sys_metrics['proc_mem_mb']:.1f} MB</code>\n"
            f"• <b>CPU Utilization:</b> <code>{sys_metrics['cpu_pct']:.1f}%</code>\n"
            f"• <b>Status:</b> <code>{sys_metrics['status']}</code>\n\n"
            "<b>Engine & Network:</b>\n"
            f"• <b>Gateway Latency:</b> <code>{latency_ms:.1f} ms</code>\n"
            f"• <b>MTProto Streaming:</b> <code>Active & Healthy</code> 🟢\n"
            f"• <b>System Uptime:</b> <code>{uptime_str}</code>\n\n"
            f"🕒 <i>Updated: {now_ist_str}</i>"
        )
    else:
        text = (
            f"<b>{BRAND_NAME} — Service Overview 📊</b>\n\n"
            "<b>Storage & Link Counts:</b>\n"
            f"• <b>Active Streaming Links:</b> <code>{stats['active_links']}</code>\n"
            f"• <b>Active Storage Footprint:</b> <code>{active_storage}</code>\n"
            f"• <b>Total Files Registered:</b> <code>{stats['total_files']}</code>\n\n"
            "<b>Transfer Statistics:</b>\n"
            f"• <b>Total Stream Downloads:</b> <code>{stats['total_downloads']}</code>\n"
            f"• <b>Total Bandwidth Served:</b> <code>{total_bandwidth}</code>\n\n"
            f"• <b>Uptime:</b> <code>{uptime_str}</code> · <b>Latency:</b> <code>{latency_ms:.1f} ms</code>\n"
            f"🕒 <i>Updated: {now_ist_str}</i>"
        )

    # Clean tab buttons: active tab marked, inactive tab switchable
    tab_overview_btn = InlineKeyboardButton(
        text="• Overview 📊 •" if tab == "overview" else "Overview 📊",
        callback_data="stats:tab:overview"
    )
    tab_system_btn = InlineKeyboardButton(
        text="• Server Load ⚙️ •" if tab == "system" else "Server Load ⚙️",
        callback_data="stats:tab:system"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [tab_overview_btn, tab_system_btn],
        [InlineKeyboardButton(text="Refresh Metrics 🔄", callback_data=f"stats:refresh:{tab}", style="primary")]
    ])
    return text, markup

# ==============================================================================
# BUTTONED HELP GUIDE BUILDER (Pure Guide, No Command Shortcuts)
# ==============================================================================

HELP_MAIN_TEXT = (
    f"<b>{BRAND_NAME} — Help Center</b> 📖\n\n"
    "Welcome to the Kayi File to Link Help Center. Choose a topic below to learn how to stream videos online, download files, use the web player and Mini App, and manage your links.\n\n"
    "• <b>Getting Started:</b> Sending files and generating links\n"
    "• <b>Streaming & Downloading:</b> Watch links, direct downloads, and external players\n"
    "• <b>Video Player & Mini App:</b> Browser playback, player controls, and Mini App\n"
    "• <b>Managing Your Files:</b> Viewing active files and link information\n"
    "• <b>Troubleshooting:</b> Common playback issues and solutions\n\n"
    "<i>Select a section below for details:</i>"
)

HELP_SECTIONS = {
    "start": (
        f"<b>Getting Started — {BRAND_NAME}</b> 🚀\n\n"
        "Convert any Telegram file or video into high-speed streaming and direct download links.\n\n"
        "<b>How to Use:</b>\n"
        "1. Send or forward any video, audio, or document file into this chat.\n"
        "2. The bot registers the file and assigns a sequential reference ID (e.g. <code>20261122001</code>).\n"
        "3. You instantly receive an action card with <b>Watch Online</b> and <b>Download</b> buttons.\n"
        "4. Share the link with anyone — viewers can watch or download directly in their browser without a Telegram account."
    ),
    "streaming": (
        "<b>Streaming & Downloading</b> 🎬\n\n"
        "<b>Watch Online:</b>\n"
        "Tap <b>Watch Online</b> to open the file in the responsive in-browser HTML5 video player.\n\n"
        "<b>Direct Download:</b>\n"
        "Tap <b>Fast Download</b> for high-speed single-connection downloads with pause and resume support.\n\n"
        "<b>External Media Players:</b>\n"
        "Stream links support HTTP 206 range requests and can be opened directly in:\n"
        "• <b>Android:</b> VLC for Android, MX Player (Network Stream)\n"
        "• <b>iOS:</b> Safari native player, VLC, Outplayer\n"
        "• <b>PC / Mac:</b> VLC Media Player (Ctrl+N), PotPlayer, MPV"
    ),
    "player": (
        "<b>Video Player & Mini App</b> 📱\n\n"
        "<b>HTML5 Web Player:</b>\n"
        "• Modern video controls including play/pause, seek bar, volume, playback speed, and fullscreen.\n"
        "• Subtitle rendering engine and multi-audio track selection when tracks are embedded in the video container.\n\n"
        "<b>Telegram Mini App:</b>\n"
        "• On secure HTTPS connections, tap <b>Open Mini App 🚀</b> on the home screen to launch your personal media hub directly inside Telegram without leaving your chat.\n"
        "• Browse active files, launch stream links, and manage settings in-app."
    ),
    "manage": (
        "<b>Managing Your Files</b> 📂\n\n"
        "<b>Viewing Active Files:</b>\n"
        "• Send <code>/myfiles</code> or tap <b>📁 My Files</b> on the home screen.\n"
        "• View your recent uploads with direct links, file sizes, and category badges (video, audio, document).\n\n"
        "<b>File Information:</b>\n"
        "• Send <code>/info &lt;ID&gt;</code> (e.g. <code>/info 20261122001</code>) to inspect technical metadata, MIME type, and exact file size.\n\n"
        "<b>Link Persistence:</b>\n"
        "• Stream links stream directly from Telegram servers via MTProto chunks. As long as the file is intact in Telegram, your stream links remain functional."
    ),
    "troubleshoot": (
        "<b>Troubleshooting & Common Issues</b> 🛠️\n\n"
        "<b>Video Buffering or Loading Slowly:</b>\n"
        "• Check your internet connection speed.\n"
        "• For large files (1GB+), streaming in an external player like <b>VLC</b> or <b>MPV</b> provides smoother hardware-accelerated decoding.\n\n"
        "<b>No Audio in Browser:</b>\n"
        "• Some web browsers do not natively support AC3, EAC3, or DTS audio codecs.\n"
        "• Open the stream URL in VLC or MX Player, which contain built-in decoders for all audio formats.\n\n"
        "<b>Subtitles Not Showing:</b>\n"
        "• The web player extracts embedded ASS/SRT subtitles where present. If subtitles do not appear, ensure they were muxed into the video file or open in VLC."
    )
}

def build_help_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Getting Started", callback_data="help:sec:start"),
            InlineKeyboardButton(text="🎬 Streaming & Downloads", callback_data="help:sec:streaming")
        ],
        [
            InlineKeyboardButton(text="📱 Player & Mini App", callback_data="help:sec:player"),
            InlineKeyboardButton(text="📂 Managing Files", callback_data="help:sec:manage")
        ],
        [
            InlineKeyboardButton(text="🛠️ Troubleshooting", callback_data="help:sec:troubleshoot")
        ],
        [
            InlineKeyboardButton(text="◀️ Back to Home", callback_data="home")
        ]
    ])

def build_help_subpage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Back to Help", callback_data="help:main")
        ]
    ])

def build_help_view(tab: str = "about") -> tuple[str, InlineKeyboardMarkup]:
    tab_map = {
        "howto": "start",
        "commands": "manage",
        "players": "streaming",
        "about": "start"
    }
    sec_key = tab_map.get(tab)
    if sec_key and sec_key in HELP_SECTIONS:
        return HELP_SECTIONS[sec_key], build_help_subpage_keyboard()
    return HELP_MAIN_TEXT, build_help_main_keyboard()

# ==============================================================================
# STARTUP & RESTART NOTIFICATION
# ==============================================================================

async def setup_bot_commands(bot: Bot):
    # Default commands for regular users
    default_commands = [
        BotCommand(command="start", description="Start bot & overview"),
        BotCommand(command="myfiles", description="View your active stream links"),
        BotCommand(command="ping", description="Check server latency & uptime"),
        BotCommand(command="help", description="Player & streaming setup guide"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    # Owner commands: Admin tools strictly at the bottom with [Admin] tags
    owner_commands = default_commands + [
        BotCommand(command="files", description="[Admin] Browse all system files"),
        BotCommand(command="stats", description="[Admin] Service metrics & storage"),
        BotCommand(command="usage", description="[Admin] Live RAM & CPU hardware load"),
        BotCommand(command="restart", description="[Admin] Safe restart streaming service")
    ]
    try:
        await bot.set_my_commands(owner_commands, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    except Exception:
        pass

    # Automatically set Telegram bottom menu button to WebApp if HTTPS is active
    srv_url = get_server_url()
    if srv_url.startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Open App", web_app=WebAppInfo(url=srv_url))
            )
            print(f"[menu] Bottom chat menu button configured to WebApp: {srv_url}")
        except Exception as e:
            print(f"[menu] Could not configure chat menu button: {e}")

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
# UI STRINGS & KEYBOARD BUILDERS
# ==============================================================================

WELCOME_CAPTION = (
    "<b>Welcome to Kayi File to Link</b>\n\n"
    "Turn Telegram files into streaming and download links.\n\n"
    "Send a supported video or file to get started.\n\n"
    "✦ Watch videos online\n"
    "✦ Download files easily\n"
    "✦ Share links instantly\n\n"
    "Need help? Use /help for instructions and feature guides.\n\n"
    "<i>Send a file to begin.</i>"
)

def build_welcome_keyboard() -> InlineKeyboardMarkup:
    srv_url = get_server_url()
    first_row = []
    if srv_url.startswith("https://"):
        first_row.append(InlineKeyboardButton(text="Open Mini App 🚀", web_app=types.WebAppInfo(url=srv_url), style="primary"))
    first_row.append(InlineKeyboardButton(text="📁 My Files", callback_data="user:myfiles", style="success"))

    return InlineKeyboardMarkup(inline_keyboard=[
        first_row,
        [
            InlineKeyboardButton(text="📢 Updates", url=COMMUNITY_URL),
            InlineKeyboardButton(text="👨‍💻 Developer", url=DEVELOPER_URL)
        ]
    ])

def build_help_back_keyboard() -> InlineKeyboardMarkup:
    return build_help_subpage_keyboard()

async def send_welcome_screen(bot: Bot, chat_id: int):
    """Sends the cinematic welcome screen using cached Telegram video file_id."""
    markup = build_welcome_keyboard()
    if WELCOME_VIDEO_FILE_ID:
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=WELCOME_VIDEO_FILE_ID,
                caption=WELCOME_CAPTION,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
                supports_streaming=True
            )
            print(f"[welcome] START_CINEMATIC_SUCCESS chat_id={chat_id}")
            return
        except Exception as e:
            print(f"[welcome] START_CINEMATIC_FAILURE chat_id={chat_id} error={type(e).__name__}: {e}")
    else:
        print(f"[welcome] START_CINEMATIC_FAILURE chat_id={chat_id} error=NO_FILE_ID_CONFIGURED")

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=WELCOME_CAPTION,
            parse_mode=ParseMode.HTML,
            reply_markup=markup
        )
        print(f"[welcome] START_TEXT_FALLBACK chat_id={chat_id}")
    except Exception as fb_err:
        print(f"[welcome] START_TEXT_FALLBACK_FAILURE chat_id={chat_id} error={type(fb_err).__name__}: {fb_err}")

# ==============================================================================
# COMMAND HANDLERS
# ==============================================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message, bot: Bot | None = None):
    if bot is None:
        bot = message.bot
    user_id = message.from_user.id
    await send_welcome_screen(bot, user_id)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.reply(
        HELP_MAIN_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=build_help_main_keyboard()
    )

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
        disp_id = f.get("display_id") or str(f["id"])
        name = f["file_name"]
        size_str = format_file_size(f["file_size"])
        category = get_media_category(f["mime_type"], name)
        type_icon = "🎬" if category == "video" else ("🎵" if category == "audio" else ("📄" if category == "pdf" else "📁"))
        watch_url = f"{srv_url}/watch/{disp_id}"
        added_time = format_date_str(f["created_at"])

        lines.append(
            f"<b>{idx}. {html.escape(name)}</b>\n"
            f"• <b>Size:</b> <code>{size_str}</code> | {type_icon} <code>{category.title()}</code>\n"
            f"• <b>Added:</b> <code>{added_time}</code>"
        )
        watch_item_btn = InlineKeyboardButton(text=f"Watch #{idx} 🍿", web_app=types.WebAppInfo(url=watch_url), style="primary") if watch_url.startswith("https://") else InlineKeyboardButton(text=f"Watch #{idx} 🍿", url=watch_url, style="primary")
        keyboard_rows.append([
            watch_item_btn,
            InlineKeyboardButton(text=f"Delete #{idx} 🗑️", callback_data=f"del:ask:{disp_id}", style="danger")
        ])

    keyboard_rows.append([
        InlineKeyboardButton(text="Refresh 🔄", callback_data="user:myfiles")
    ])

    await message.reply(
        "\n\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

@dp.message(Command("files"))
async def cmd_files(message: types.Message):
    # Restricted strictly to owner
    if message.from_user.id != OWNER_ID:
        await message.reply("Access restricted to bot owner.")
        return

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

    lines = [f"<b>System File Catalog [Admin] 🌐</b>\n<i>{total} active files · Page {page} of {total_pages}</i>\n"]
    srv_url = get_server_url()

    if not files:
        lines.append("<i>No active files found.</i>")
    else:
        for f in files:
            disp_id = f.get("display_id") or str(f["id"])
            name = f["file_name"]
            size_fmt = format_file_size(f["file_size"])
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            fmt_label = ext.upper() if ext else "FILE"
            watch_url = f"{srv_url}/watch/{disp_id}"
            lines.append(f"• <b>Ref {disp_id}</b> [{fmt_label} · {size_fmt}]\n  <a href=\"{watch_url}\">{html.escape(name)}</a>")

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
            "<b>Usage:</b> <code>/info &lt;ID&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return

    query_id = parts[1].strip()
    await send_file_info_card(message, query_id)

async def send_file_info_card(message: types.Message, query_id: str):
    record = await db.get_file_by_id_or_token(query_id)
    if not record:
        await message.reply(f"❌ <i>No active file found.</i>", parse_mode=ParseMode.HTML)
        return

    disp_id = record.get("display_id") or str(record["id"])
    file_name = record["file_name"]
    file_size = record["file_size"]
    mime_type = record["mime_type"]
    uploaded_str = format_date_str(record["created_at"])

    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{disp_id}"
    watch_url = f"{srv_url}/watch/{disp_id}"

    category = get_media_category(mime_type, file_name)
    is_owner = (message.from_user.id == OWNER_ID)

    # Clean file details: No total plays/downloads, no ID for normal users
    card_lines = [
        "<b>File Information ℹ️</b>\n",
        f"• <b>Name:</b> <code>{html.escape(file_name)}</code>",
        f"• <b>Size:</b> <code>{format_file_size(file_size)}</code>",
        f"• <b>Format:</b> <code>{category.title()}</code>",
        f"• <b>MIME:</b> <code>{html.escape(mime_type)}</code>",
        f"• <b>Uploaded:</b> <code>{uploaded_str}</code>"
    ]
    if is_owner:
        card_lines.append(f"• <b>Ref ID:</b> <code>{disp_id}</code>")

    card_lines.extend([
        f"\n<b>Stream URL 👇</b>\n<code>{watch_url}</code>",
        f"\n<b>Download URL 👇</b>\n<code>{dl_url}</code>"
    ])

    info_watch_btn = InlineKeyboardButton(text="Watch in WebApp 🍿", web_app=types.WebAppInfo(url=watch_url), style="primary") if watch_url.startswith("https://") else InlineKeyboardButton(text="Watch Online 🍿", url=watch_url, style="primary")

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            info_watch_btn,
            InlineKeyboardButton(text="Fast Download ⚡", url=dl_url, style="success")
        ],
        [
            InlineKeyboardButton(text="Copy Stream 📋", copy_text=CopyTextButton(text=watch_url)),
            InlineKeyboardButton(text="Delete Link 🗑️", callback_data=f"del:ask:{disp_id}", style="danger")
        ]
    ])
    await message.reply("\n".join(card_lines), parse_mode=ParseMode.HTML, reply_markup=markup, link_preview_options=types.LinkPreviewOptions(is_disabled=True))

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

    text, markup = await build_stats_view(bot, tab="overview")
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

@dp.callback_query(F.data == "fsub:verify")
async def cb_fsub_verify(callback: types.CallbackQuery, bot: Bot | None = None):
    if bot is None:
        bot = callback.bot
    user_id = callback.from_user.id

    await callback.answer("Checking membership...")

    is_member, status = await check_channel_membership(
        bot=bot,
        user_id=user_id,
        bypass_cache=True
    )

    if is_member:
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await send_welcome_screen(bot, user_id)
    else:
        if status in ("left", "kicked") or (status == "restricted" and not is_member):
            await callback.answer(
                "You haven't joined @KayiBots yet. Please join the channel and tap I've Joined.",
                show_alert=True
            )
        else:
            await callback.answer(
                "Membership check unavailable right now. Please try again shortly.",
                show_alert=True
            )

@dp.callback_query(F.data == "home")
async def cb_home(callback: types.CallbackQuery, bot: Bot | None = None):
    if bot is None:
        bot = callback.bot
    user_id = callback.from_user.id
    if callback.message.video:
        try:
            await callback.message.edit_caption(
                caption=WELCOME_CAPTION,
                parse_mode=ParseMode.HTML,
                reply_markup=build_welcome_keyboard()
            )
            await callback.answer()
            return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
                return

    try:
        await callback.message.delete()
    except Exception:
        pass
    await send_welcome_screen(bot, user_id)
    await callback.answer()

@dp.callback_query(F.data.startswith("stats:tab:"))
async def cb_stats_tab(query: types.CallbackQuery, bot: Bot):
    if query.from_user.id != OWNER_ID:
        await query.answer("Access restricted to bot owner.", show_alert=True)
        return
    tab = query.data.split(":")[2]
    text, markup = await build_stats_view(bot, tab=tab)
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await query.answer()

@dp.callback_query(F.data.startswith("stats:refresh:"))
async def cb_stats_refresh(query: types.CallbackQuery, bot: Bot):
    if query.from_user.id != OWNER_ID:
        await query.answer("Access restricted to bot owner.", show_alert=True)
        return
    tab = query.data.split(":")[2]
    text, markup = await build_stats_view(bot, tab=tab)
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await query.answer("Metrics refreshed.")

@dp.callback_query(F.data == "help:main")
async def cb_help_main(query: types.CallbackQuery):
    if query.message.video:
        try:
            await query.message.edit_caption(
                caption=HELP_MAIN_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=build_help_main_keyboard()
            )
            await query.answer()
            return
        except TelegramBadRequest:
            pass
    try:
        await query.message.edit_text(HELP_MAIN_TEXT, parse_mode=ParseMode.HTML, reply_markup=build_help_main_keyboard())
    except TelegramBadRequest:
        pass
    await query.answer()

@dp.callback_query(F.data.startswith("help:sec:"))
async def cb_help_section(query: types.CallbackQuery):
    sec_key = query.data.split(":")[2]
    text = HELP_SECTIONS.get(sec_key)
    if not text:
        await query.answer("Section not found.", show_alert=True)
        return
    if query.message.video:
        try:
            await query.message.edit_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=build_help_subpage_keyboard()
            )
            await query.answer()
            return
        except TelegramBadRequest:
            pass
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=build_help_subpage_keyboard())
    except TelegramBadRequest:
        pass
    await query.answer()

@dp.callback_query(F.data.startswith("help:tab:"))
async def cb_help_tab(query: types.CallbackQuery):
    tab = query.data.split(":")[2]
    text, markup = build_help_view(tab=tab)
    if query.message.video:
        try:
            await query.message.edit_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=markup)
            await query.answer()
            return
        except TelegramBadRequest:
            pass
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await query.answer()

@dp.callback_query(F.data.startswith("show_files_"))
async def callback_show_files(query: types.CallbackQuery):
    if query.from_user.id != OWNER_ID:
        await query.answer("Access restricted to bot owner.", show_alert=True)
        return
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
    disp_id = query.data.split("_")[2]
    await query.answer()
    await send_file_info_card(query.message, disp_id)

@dp.callback_query(F.data.startswith("del:ask:"))
async def cb_delete_ask(callback: types.CallbackQuery):
    disp_id = callback.data.split(":")[2]
    record = await db.get_file_by_id_or_token(disp_id)
    if not record:
        await callback.answer("File record not found or already deleted.", show_alert=True)
        return

    # Check permission
    if callback.from_user.id != record["user_id"] and callback.from_user.id != OWNER_ID:
        await callback.answer("⚠️ You can only delete your own uploads.", show_alert=True)
        return

    confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Confirm Delete 🗑️", callback_data=f"del:confirm:{disp_id}", style="danger"),
            InlineKeyboardButton(text="Cancel ↩️", callback_data=f"del:cancel:{disp_id}")
        ]
    ])

    try:
        await callback.message.edit_reply_markup(reply_markup=confirm_markup)
    except TelegramBadRequest:
        pass
    await callback.answer("Confirm deletion?")

@dp.callback_query(F.data.startswith("del:cancel:"))
async def cb_delete_cancel(callback: types.CallbackQuery):
    disp_id = callback.data.split(":")[2]
    record = await db.get_file_by_id_or_token(disp_id)
    if not record:
        await callback.answer("File record not found.", show_alert=True)
        return

    srv_url = get_server_url()
    watch_url = f"{srv_url}/watch/{disp_id}"
    dl_url = f"{srv_url}/dl/{disp_id}"
    original_markup = build_file_markup(watch_url, dl_url, disp_id)

    try:
        await callback.message.edit_reply_markup(reply_markup=original_markup)
    except TelegramBadRequest:
        pass
    await callback.answer("Deletion cancelled.")

@dp.callback_query(F.data.startswith("del:confirm:"))
async def cb_delete_confirm(callback: types.CallbackQuery):
    disp_id = callback.data.split(":")[2]
    record = await db.get_file_by_id_or_token(disp_id)
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

    await db.delete_file_by_id_or_token(disp_id)
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.answer("🗑️ Streaming link deleted successfully!", show_alert=True)

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

    # 1. Deduplication Cache Check: If exact same file was already sent, return existing link!
    cached = await db.find_file_by_unique_id(file_unique_id)
    if cached:
        disp_id = cached.get("display_id") or str(cached["id"])
        srv_url = get_server_url()
        watch_url = f"{srv_url}/watch/{disp_id}"
        dl_url = f"{srv_url}/dl/{disp_id}"
        card_text = build_file_card_text(
            file_name=cached["file_name"],
            file_size=cached["file_size"],
            mime_type=cached["mime_type"],
            watch_url=watch_url,
            dl_url=dl_url,
            is_cached=True
        )
        markup = build_file_markup(watch_url, dl_url, disp_id)
        await message.reply(card_text, parse_mode=ParseMode.HTML, reply_markup=markup, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        return

    # 2. Forward backup to LOG_CHANNEL_ID if configured
    if LOG_CHANNEL_ID:
        try:
            asyncio.create_task(message.forward(chat_id=int(LOG_CHANNEL_ID)))
        except Exception:
            pass

    # 3. Save new record with sequential date format ID: e.g. 21112026001, 21112026002
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

    disp_id = record["display_id"]
    srv_url = get_server_url()
    dl_url = f"{srv_url}/dl/{disp_id}"
    watch_url = f"{srv_url}/watch/{disp_id}"

    # 4. Build Single Clean Response Card (No ID shown on main card)
    card_text = build_file_card_text(
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        watch_url=watch_url,
        dl_url=dl_url,
        is_cached=False
    )
    markup = build_file_markup(watch_url, dl_url, disp_id)

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
        retry_delay = 2
        handle_signals = (sys.platform != "win32")
        while True:
            try:
                print(f"[{BRAND_NAME}] Polling Telegram updates (handle_signals={handle_signals})...")
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=handle_signals)
                break
            except (asyncio.CancelledError, KeyboardInterrupt):
                print(f"[{BRAND_NAME}] Polling stopped safely.")
                break
            except Exception as e:
                print(f"[{BRAND_NAME}] Polling hiccup: {e}. Resuming in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(int(retry_delay * 1.5) + 1, 30)
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
