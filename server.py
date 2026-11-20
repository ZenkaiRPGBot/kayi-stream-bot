import asyncio
import os
import math
import mimetypes
import re
from datetime import datetime, timezone
import aiohttp
from aiohttp import web

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, API_ID, API_HASH,
    PORT, PING_URL, BRAND_NAME, CHANNEL_USERNAME, get_server_url
)
import database as db

mimetypes.init()

# Optional Pyrogram MTProto Client for files > 20 MB
pyrogram_client = None

async def init_pyrogram_client():
    global pyrogram_client
    if API_ID and API_HASH and BOT_TOKEN:
        try:
            from pyrogram import Client
            clean_api_id = int(str(API_ID).strip())
            clean_api_hash = str(API_HASH).strip()
            pyrogram_client = Client(
                "kayi_stream_mtproto",
                api_id=clean_api_id,
                api_hash=clean_api_hash,
                bot_token=BOT_TOKEN,
                in_memory=True
            )
            await pyrogram_client.start()
            me = await pyrogram_client.get_me()
            print(f"[MTProto] Connected successfully as @{me.username}! (2GB+ streaming enabled)")
        except Exception as e:
            print(f"[MTProto] Failed to initialize Pyrogram client: {e}")
            pyrogram_client = None
    else:
        print("[MTProto] Notice: API_ID or API_HASH not set. Bot API fallback active (max 20 MB).")

def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"

def get_media_category(mime_type: str, file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower()
    if mime_type.startswith("video/") or ext in [".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ts", ".flv", ".3gp"]:
        return "video"
    elif mime_type.startswith("audio/") or ext in [".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma"]:
        return "audio"
    elif mime_type.startswith("image/") or ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
        return "image"
    elif ext == ".pdf":
        return "pdf"
    return "document"

async def handle_root(request: web.Request) -> web.Response:
    stats = await db.get_global_stats()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{BRAND_NAME} — Cinema Cloud Stream Engine</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #08080c 70%);
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            background: rgba(18, 18, 24, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(20px);
            border-radius: 28px;
            padding: 44px 36px;
            max-width: 540px;
            width: 100%;
            text-align: center;
            box-shadow: 0 30px 70px rgba(0,0,0,0.6);
        }}
        .logo {{ font-size: 56px; margin-bottom: 12px; filter: drop-shadow(0 0 20px rgba(56, 189, 248, 0.4)); }}
        h1 {{ font-size: 30px; font-weight: 800; background: linear-gradient(135deg, #a5b4fc, #38bdf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        p {{ color: #a1a1aa; font-size: 14px; margin-top: 10px; line-height: 1.6; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 28px 0;
        }}
        .stat-box {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 16px 8px;
        }}
        .stat-num {{ font-size: 20px; font-weight: 800; color: #38bdf8; }}
        .stat-lbl {{ font-size: 11px; color: #71717a; text-transform: uppercase; margin-top: 4px; font-weight: 600; }}
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            padding: 15px;
            border-radius: 14px;
            text-decoration: none;
            font-weight: 700;
            font-size: 15px;
            box-shadow: 0 10px 25px rgba(37, 99, 235, 0.35);
            transition: all 0.2s ease;
        }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 14px 30px rgba(37, 99, 235, 0.5); }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🦅</div>
        <h1>{BRAND_NAME}</h1>
        <p>Ultra-Fast Telegram File to Direct Link & Video Streaming Engine. Instant zero-RAM streaming, full HTTP Range seeking, and cinema-grade playback.</p>
        
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-num">{stats['active_links']}</div>
                <div class="stat-lbl">Active Links</div>
            </div>
            <div class="stat-box">
                <div class="stat-num">{stats['total_downloads']}</div>
                <div class="stat-lbl">Downloads</div>
            </div>
            <div class="stat-box">
                <div class="stat-num">99.9%</div>
                <div class="stat-lbl">Uptime</div>
            </div>
        </div>

        <a href="https://t.me/{CHANNEL_USERNAME.lstrip('@')}" class="btn">🚀 Join Telegram Ecosystem</a>
    </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")

async def handle_health(request: web.Request) -> web.Response:
    stats = await db.get_global_stats()
    return web.json_response({
        "status": "healthy",
        "service": "kayi-stream-bot",
        "mtproto_active": pyrogram_client is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": stats
    })

async def handle_watch(request: web.Request) -> web.Response:
    token = request.match_info.get("token")
    record = await db.get_file_record(token)
    if not record:
        return web.Response(
            text="""<!DOCTYPE html><html><body style="background:#08080c;color:#f4f4f5;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;padding:24px;"><h1>404 - Link Expired or Not Found</h1><p style="color:#71717a;margin-top:8px;">This link has expired or has been revoked by the owner.</p></div></body></html>""",
            content_type="text/html",
            status=404
        )

    file_name = record["file_name"]
    file_size = record["file_size"]
    file_size_fmt = format_file_size(file_size)
    mime_type = record.get("mime_type") or "application/octet-stream"
    
    server_base = get_server_url()
    dl_url = f"{server_base}/dl/{token}"
    stream_url = dl_url
    category = get_media_category(mime_type, file_name)
    ext = os.path.splitext(file_name)[1].lower()

    # 3rd-party player launch schemes
    raw_url = stream_url.replace("https://", "").replace("http://", "")
    vlc_url = f"vlc://{raw_url}"
    mx_url = f"intent:{stream_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end"
    potplayer_url = f"potplayer://{stream_url}"

    # Is MKV or non-native container
    is_mkv = ext in [".mkv", ".avi", ".ts", ".flv"] or "matroska" in mime_type.lower()
    
    mkv_banner = ""
    if is_mkv:
        mkv_banner = f"""
        <div class="codec-banner">
            <div class="banner-icon">💡</div>
            <div class="banner-text">
                <b>MKV / Anime Video Notice:</b> Web browsers might not support all audio tracks (AC3/E-AC3/DTS) in MKV files natively.
                For stutter-free playback with multi-subtitles, tap <b>Open in VLC Player</b> or <b>MX Player</b> below!
            </div>
        </div>
        """

    # Dynamic player block
    if category == "video":
        player_html = f"""
        <div class="player-container">
            <div class="ambient-glow" id="ambientGlow"></div>
            <div class="player-wrapper">
                <video id="player" playsinline controls preload="metadata">
                    <source src="{stream_url}" type="{mime_type}">
                    Your browser does not support HTML5 video streaming.
                </video>
            </div>
        </div>"""
    elif category == "audio":
        player_html = f"""
        <div class="audio-box">
            <div class="disc-glow"></div>
            <div class="disc-icon">🎵</div>
            <div class="audio-title">{file_name}</div>
            <div class="audio-sub">Lossless Telegram Cloud Stream • {file_size_fmt}</div>
            <audio id="player" controls style="width: 100%; margin-top: 24px;">
                <source src="{stream_url}" type="{mime_type}">
            </audio>
        </div>"""
    elif category == "image":
        player_html = f"""
        <div class="image-box">
            <img src="{stream_url}" alt="{file_name}">
        </div>"""
    else:
        player_html = f"""
        <div class="doc-box">
            <div class="doc-icon">📄</div>
            <div class="doc-title">{file_name}</div>
            <div class="doc-size">{file_size_fmt} • Document</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_name} — {BRAND_NAME}</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --plyr-color-main: #0284c7;
            --plyr-video-background: #000000;
            --bg-dark: #07070a;
            --card-bg: rgba(18, 18, 24, 0.7);
            --border-glow: rgba(56, 189, 248, 0.2);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: radial-gradient(circle at 50% 0%, #151528 0%, #07070a 75%);
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 24px 16px 50px;
            overflow-x: hidden;
        }}
        .top-nav {{
            width: 100%;
            max-width: 1040px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
        }}
        .brand {{
            font-size: 20px;
            font-weight: 800;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            letter-spacing: -0.3px;
        }}
        .brand span {{
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .live-status {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.25);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            color: #4ade80;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .pulse-dot {{
            width: 7px;
            height: 7px;
            background: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 10px #22c55e;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); opacity: 0.8; }}
            50% {{ transform: scale(1.4); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.8; }}
        }}

        .main-card {{
            width: 100%;
            max-width: 1040px;
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(24px);
            border-radius: 28px;
            overflow: hidden;
            box-shadow: 0 35px 80px rgba(0, 0, 0, 0.7);
            position: relative;
        }}

        /* Cinema Player & Ambient Glow */
        .player-container {{
            position: relative;
            width: 100%;
            background: #000;
        }}
        .ambient-glow {{
            position: absolute;
            top: 10%;
            left: 5%;
            width: 90%;
            height: 80%;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.25) 0%, rgba(99, 102, 241, 0.15) 50%, transparent 80%);
            filter: blur(60px);
            z-index: 0;
            pointer-events: none;
            opacity: 0.7;
            transition: opacity 0.5s ease;
        }}
        .player-wrapper {{
            position: relative;
            z-index: 1;
            width: 100%;
            background: #000;
        }}
        .plyr {{
            border-radius: 0;
            max-height: 78vh;
        }}

        /* Codec Warning Banner */
        .codec-banner {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            background: rgba(234, 179, 8, 0.1);
            border: 1px solid rgba(234, 179, 8, 0.25);
            border-radius: 16px;
            padding: 14px 18px;
            margin: 20px 24px 0;
            color: #fef08a;
            font-size: 13px;
            line-height: 1.5;
        }}
        .banner-icon {{ font-size: 20px; }}
        .codec-banner b {{ color: #fde047; }}

        /* Content Body */
        .content-body {{
            padding: 28px 32px 36px;
        }}
        .file-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 22px;
            margin-bottom: 24px;
        }}
        .file-title {{
            font-size: 20px;
            font-weight: 800;
            line-height: 1.4;
            color: #ffffff;
            word-break: break-all;
        }}
        .meta-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: #94a3b8;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 5px 12px;
            border-radius: 10px;
        }}
        .badge-highlight {{
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.08);
            border-color: rgba(56, 189, 248, 0.2);
        }}

        /* Action Launchers Grid */
        .action-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 14px;
            margin-top: 24px;
        }}
        .btn-action {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 15px 20px;
            border-radius: 16px;
            font-size: 14px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .btn-download {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #ffffff;
            font-size: 16px;
            padding: 18px;
            border: none;
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.35);
        }}
        .btn-download:hover {{
            transform: translateY(-2px);
            box-shadow: 0 16px 36px rgba(37, 99, 235, 0.5);
        }}
        .btn-vlc {{
            background: rgba(249, 115, 22, 0.12);
            color: #fb923c;
            border-color: rgba(249, 115, 22, 0.25);
        }}
        .btn-vlc:hover {{
            background: rgba(249, 115, 22, 0.22);
            transform: translateY(-2px);
        }}
        .btn-mx {{
            background: rgba(14, 165, 233, 0.12);
            color: #38bdf8;
            border-color: rgba(14, 165, 233, 0.25);
        }}
        .btn-mx:hover {{
            background: rgba(14, 165, 233, 0.22);
            transform: translateY(-2px);
        }}
        .btn-potplayer {{
            background: rgba(234, 179, 8, 0.12);
            color: #facc15;
            border-color: rgba(234, 179, 8, 0.25);
        }}
        .btn-potplayer:hover {{
            background: rgba(234, 179, 8, 0.22);
            transform: translateY(-2px);
        }}
        .btn-copy {{
            background: rgba(255, 255, 255, 0.05);
            color: #f4f4f5;
            border-color: rgba(255, 255, 255, 0.12);
        }}
        .btn-copy:hover {{
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }}

        /* Audio / Doc Box */
        .audio-box, .doc-box, .image-box {{
            padding: 56px 24px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .disc-icon, .doc-icon {{
            font-size: 68px;
            margin-bottom: 16px;
            filter: drop-shadow(0 0 24px rgba(56, 189, 248, 0.3));
        }}
        .audio-title, .doc-title {{
            font-size: 22px;
            font-weight: 800;
            color: #fff;
            max-width: 640px;
            word-break: break-all;
        }}
        .audio-sub, .doc-size {{
            font-size: 14px;
            color: #71717a;
            margin-top: 8px;
        }}
        .image-box img {{
            max-width: 100%;
            max-height: 75vh;
            border-radius: 16px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }}

        /* Toast */
        .toast {{
            position: fixed;
            bottom: 30px;
            background: #18181b;
            color: #fff;
            padding: 14px 28px;
            border-radius: 999px;
            font-size: 14px;
            font-weight: 700;
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow: 0 15px 40px rgba(0,0,0,0.6);
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
            z-index: 100;
        }}
        .toast.show {{ opacity: 1; transform: translateY(0); }}

        /* Keyboard Cheatsheet */
        .cheatsheet {{
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 12px;
            color: #71717a;
        }}
        .key {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 6px;
            padding: 2px 7px;
            color: #cbd5e1;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <div class="top-nav">
        <a href="/" class="brand">🦅 <span>{BRAND_NAME}</span></a>
        <div class="live-status">
            <span class="pulse-dot"></span>
            Cloud Stream Active
        </div>
    </div>

    <div class="main-card">
        {player_html}
        {mkv_banner}

        <div class="content-body">
            <div class="file-header">
                <div>
                    <h1 class="file-title">{file_name}</h1>
                    <div class="meta-badges">
                        <span class="badge badge-highlight">📦 {file_size_fmt}</span>
                        <span class="badge">🎬 {category.upper()}</span>
                        <span class="badge">⚡ Zero-RAM Buffer</span>
                        <span class="badge">🛡️ Direct Cloud Stream</span>
                        <span class="badge">⏳ Valid 24h</span>
                    </div>
                </div>
            </div>

            <div class="action-grid">
                <a href="{dl_url}" class="btn-action btn-download" download>
                    ⚡ Instant High-Speed Download
                </a>
                <a href="{vlc_url}" class="btn-action btn-vlc">
                    🟧 Open in VLC Player
                </a>
                <a href="{mx_url}" class="btn-action btn-mx">
                    🔷 Open in MX Player
                </a>
                <a href="{potplayer_url}" class="btn-action btn-potplayer">
                    🟨 Open in PotPlayer
                </a>
                <button class="btn-action btn-copy" onclick="copyStreamLink()">
                    📋 Copy Direct Stream Link
                </button>
            </div>

            <div class="cheatsheet">
                <span><span class="key">Space</span> Play/Pause</span>
                <span><span class="key">F</span> Fullscreen</span>
                <span><span class="key">M</span> Mute</span>
                <span><span class="key">← / →</span> 10s Seek</span>
                <span><span class="key">↑ / ↓</span> Volume</span>
            </div>
        </div>
    </div>

    <div id="toast" class="toast">Direct stream link copied to clipboard! ✅</div>

    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const el = document.getElementById('player');
            if (el) {{
                const player = new Plyr(el, {{
                    controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                    speed: {{ selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] }},
                    keyboard: {{ focused: true, global: true }},
                    seekTime: 10
                }});
            }}
        }});

        function copyStreamLink() {{
            const url = "{stream_url}";
            navigator.clipboard.writeText(url).then(() => {{
                const toast = document.getElementById('toast');
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2500);
            }});
        }}
    </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")

async def handle_download(request: web.Request) -> web.StreamResponse:
    token = request.match_info.get("token")
    record = await db.get_file_record(token)
    if not record:
        return web.Response(text="File not found or link expired.", status=404)

    file_id = record["file_id"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    mime_type = record.get("mime_type") or "application/octet-stream"

    # Clean file name for Content-Disposition
    safe_name = re.sub(r'[^\w\.\-\s\[\]\(\)]', '_', file_name)

    # 1. MTProto Streaming Engine (Pyrogram - No 20MB limit, handles up to 2GB/4GB)
    if pyrogram_client is not None:
        try:
            range_header = request.headers.get("Range")
            start_byte = 0
            end_byte = file_size - 1

            if range_header and range_header.startswith("bytes="):
                range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if range_match:
                    start_byte = int(range_match.group(1))
                    if range_match.group(2):
                        end_byte = min(int(range_match.group(2)), file_size - 1)

            content_length = (end_byte - start_byte) + 1
            status_code = 206 if range_header else 200

            response = web.StreamResponse(status=status_code)
            response.headers["Content-Type"] = mime_type
            response.headers["Content-Length"] = str(content_length)
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
            
            if range_header:
                response.headers["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"

            if request.method == "HEAD":
                await response.prepare(request)
                await response.write_eof()
                return response

            await response.prepare(request)

            # Pyrogram 1 MiB chunk offset
            chunk_size = 1024 * 1024  # 1 MiB
            chunk_offset = start_byte // chunk_size
            skip_in_first_chunk = start_byte % chunk_size
            bytes_to_send = content_length

            async for chunk in pyrogram_client.stream_media(file_id, offset=chunk_offset):
                if skip_in_first_chunk > 0:
                    chunk = chunk[skip_in_first_chunk:]
                    skip_in_first_chunk = 0

                if len(chunk) > bytes_to_send:
                    chunk = chunk[:bytes_to_send]

                if not chunk:
                    break

                await response.write(chunk)
                bytes_to_send -= len(chunk)
                if bytes_to_send <= 0:
                    break

            await response.write_eof()
            asyncio.create_task(db.increment_download_count(token))
            return response

        except Exception as e:
            print(f"[MTProto Stream Error] {e}")
            # Fall through to fallback

    # 2. Standard Bot API Fallback (for files <= 20 MB)
    if file_size <= 20 * 1024 * 1024:
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(get_file_url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status != 200:
                    return web.Response(text="Failed to retrieve file from Telegram servers.", status=502)
                data = await resp.json()
                if not data.get("ok"):
                    return web.Response(text=f"Telegram API Error: {data.get('description', 'Unknown')}", status=502)
                file_path = data["result"]["file_path"]

            stream_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            headers = {}
            range_header = request.headers.get("Range")
            if range_header:
                headers["Range"] = range_header

            async with session.get(stream_url, headers=headers, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as upstream_resp:
                status = upstream_resp.status
                response = web.StreamResponse(status=status)

                for h in ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"]:
                    val = upstream_resp.headers.get(h)
                    if val:
                        response.headers[h] = val

                response.headers["Accept-Ranges"] = "bytes"
                response.headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

                if request.method == "HEAD":
                    await response.prepare(request)
                    await response.write_eof()
                    return response

                await response.prepare(request)

                try:
                    async for chunk in upstream_resp.content.iter_chunked(131072):
                        await response.write(chunk)
                    await response.write_eof()
                except (asyncio.CancelledError, ConnectionResetError):
                    pass

                asyncio.create_task(db.increment_download_count(token))
                return response

    # 3. File > 20 MB and MTProto credentials not yet configured
    # Instead of throwing a raw 502 that crashes Cloudflare with "Bad Gateway Host Error",
    # render a polished, actionable guide page.
    error_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Setup Required — {BRAND_NAME}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #07070a 75%);
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            background: rgba(18, 18, 24, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(24px);
            border-radius: 28px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 30px 80px rgba(0,0,0,0.7);
        }}
        .icon {{ font-size: 48px; margin-bottom: 16px; text-align: center; }}
        h1 {{ font-size: 24px; font-weight: 800; color: #fff; text-align: center; margin-bottom: 8px; }}
        p {{ color: #a1a1aa; font-size: 14px; line-height: 1.6; }}
        .file-box {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 16px;
            margin: 20px 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }}
        .guide-box {{
            background: rgba(56, 189, 248, 0.06);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 16px;
            padding: 20px;
            margin-top: 16px;
        }}
        .guide-title {{ font-weight: 700; color: #38bdf8; font-size: 15px; margin-bottom: 10px; }}
        ol {{ padding-left: 20px; color: #cbd5e1; font-size: 13px; line-height: 1.8; }}
        code {{ background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 6px; color: #38bdf8; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">⚡</div>
        <h1>2GB+ MTProto Stream Activation Required</h1>
        <p style="text-align:center;">This file exceeds Telegram's standard 20 MB Bot API download limit.</p>
        
        <div class="file-box">
            <div>📁 <b>File:</b> {file_name}</div>
            <div style="margin-top:6px;">📦 <b>Size:</b> {format_file_size(file_size)} (Limit: 20.00 MB)</div>
        </div>

        <div class="guide-box">
            <div class="guide-title">💡 How to unlock 2GB+ streaming in 30 seconds:</div>
            <ol>
                <li>Visit <a href="https://my.telegram.org" target="_blank" style="color:#38bdf8;font-weight:700;">my.telegram.org</a> and log in.</li>
                <li>Click <b>API development tools</b> and create an app (e.g. <i>KayiStream</i>).</li>
                <li>Copy your <code>API_ID</code> and <code>API_HASH</code>.</li>
                <li>Add them to the bot's <code>.env</code> file:
                    <pre style="margin-top:8px;background:#000;padding:10px;border-radius:8px;color:#a5b4fc;font-size:12px;">API_ID=12345678&#10;API_HASH=abcdef0123456789abcdef0123456789</pre>
                </li>
            </ol>
        </div>
    </div>
</body>
</html>"""
    return web.Response(text=error_html, content_type="text/html", status=200)

async def ping_self_loop():
    if not PING_URL:
        return
    print(f"[keep_alive] Self-ping active! Target: {PING_URL} (every 10 minutes)")
    await asyncio.sleep(30)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(PING_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    print(f"[keep_alive] Self-ping status: {resp.status}")
            except Exception as e:
                print(f"[keep_alive] Self-ping failed: {e}")
            await asyncio.sleep(600)

async def start_server():
    # Initialize MTProto Pyrogram client if credentials exist
    await init_pyrogram_client()

    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/watch/{token}", handle_watch)
    app.router.add_get("/dl/{token}", handle_download)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[server] Streaming server listening on port {PORT}")
    asyncio.create_task(ping_self_loop())
    return runner
