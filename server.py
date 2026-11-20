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

# Pyrogram MTProto Client for unlimited streaming (handles files up to 2GB/4GB)
pyrogram_client = None

async def init_pyrogram_client():
    global pyrogram_client
    if API_ID and API_HASH and BOT_TOKEN:
        try:
            from pyrogram import Client
            clean_api_id = int(str(API_ID).strip())
            clean_api_hash = str(API_HASH).strip()
            pyrogram_client = Client(
                "kayi_stream_worker",
                api_id=clean_api_id,
                api_hash=clean_api_hash,
                bot_token=BOT_TOKEN,
                no_updates=True,
                in_memory=True
            )
            await pyrogram_client.start()
            me = await pyrogram_client.get_me()
            print(f"[MTProto] Streaming engine connected as @{me.username}! (2GB+ streaming online)")
        except Exception as e:
            print(f"[MTProto] Failed to initialize Pyrogram client: {e}")
            pyrogram_client = None
    else:
        print("[MTProto] Notice: API_ID or API_HASH not found in .env.")

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
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: #06070a;
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(129, 140, 248, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(14, 165, 233, 0.08) 0px, transparent 50%);
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            background: rgba(15, 17, 26, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(28px);
            border-radius: 28px;
            padding: 48px 36px;
            max-width: 560px;
            width: 100%;
            text-align: center;
            box-shadow: 0 35px 80px rgba(0, 0, 0, 0.7);
        }}
        .logo {{ font-size: 56px; margin-bottom: 12px; filter: drop-shadow(0 0 24px rgba(56, 189, 248, 0.4)); }}
        h1 {{
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 30%, #38bdf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }}
        p {{ color: #94a3b8; font-size: 14px; margin-top: 10px; line-height: 1.6; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 30px 0;
        }}
        .stat-box {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 18px;
            padding: 16px 8px;
        }}
        .stat-num {{ font-size: 22px; font-weight: 800; color: #38bdf8; font-family: 'JetBrains Mono', monospace; }}
        .stat-lbl {{ font-size: 11px; color: #64748b; text-transform: uppercase; margin-top: 4px; font-weight: 700; letter-spacing: 0.5px; }}
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            padding: 16px;
            border-radius: 16px;
            text-decoration: none;
            font-weight: 700;
            font-size: 15px;
            box-shadow: 0 12px 30px rgba(37, 99, 235, 0.35);
            transition: all 0.25s ease;
        }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 16px 36px rgba(37, 99, 235, 0.5); }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🦅</div>
        <h1>{BRAND_NAME}</h1>
        <p>Enterprise Cloud Streaming Engine. Direct MTProto multi-threaded pipelining with zero disk footprint and cinema web playback.</p>
        
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

        <a href="https://t.me/{CHANNEL_USERNAME.lstrip('@')}" class="btn">Launch Telegram Bot</a>
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
            text="""<!DOCTYPE html><html><body style="background:#06070a;color:#f4f4f5;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
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
        <div class="codec-alert">
            <div class="alert-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            </div>
            <div class="alert-content">
                <div class="alert-title">MKV / Multi-Track Audio Notice</div>
                <div class="alert-desc">Web browsers may not support AC3, DTS, or 10-bit anime subtitles natively. For stutter-free hardware decoding, launch directly in <b>VLC</b>, <b>MX Player</b>, or <b>PotPlayer</b> below.</div>
            </div>
        </div>
        """

    # Dynamic player block
    if category == "video":
        player_html = f"""
        <div class="cinema-stage" id="cinemaStage">
            <div class="ambilight-glow" id="ambilightGlow"></div>
            <canvas id="ambientCanvas" style="display:none;"></canvas>
            <div class="player-box">
                <video id="player" playsinline controls preload="metadata" crossorigin="anonymous">
                    <source src="{stream_url}" type="{mime_type}">
                    Your browser does not support HTML5 video streaming.
                </video>
            </div>
        </div>"""
    elif category == "audio":
        player_html = f"""
        <div class="audio-stage">
            <div class="vinyl-record" id="vinylRecord">
                <div class="vinyl-core"></div>
            </div>
            <div class="audio-meta">
                <div class="audio-title">{file_name}</div>
                <div class="audio-subtitle">Lossless Audio Stream • {file_size_fmt}</div>
            </div>
            <div class="audio-player-wrapper">
                <audio id="player" controls style="width: 100%;">
                    <source src="{stream_url}" type="{mime_type}">
                </audio>
            </div>
        </div>"""
    elif category == "image":
        player_html = f"""
        <div class="image-stage">
            <img src="{stream_url}" alt="{file_name}" id="imageViewer">
        </div>"""
    else:
        player_html = f"""
        <div class="doc-stage">
            <div class="doc-badge">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.7"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </div>
            <div class="doc-name">{file_name}</div>
            <div class="doc-size">{file_size_fmt} • Document File</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_name} — {BRAND_NAME}</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --plyr-color-main: #0ea5e9;
            --plyr-video-background: #000000;
            --bg-canvas: #06070a;
            --surface-panel: rgba(14, 16, 24, 0.78);
            --surface-card: rgba(255, 255, 255, 0.03);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --cyan-accent: #38bdf8;
            --blue-accent: #2563eb;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: var(--bg-canvas);
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.12) 0px, transparent 40%),
                radial-gradient(at 100% 0%, rgba(99, 102, 241, 0.12) 0px, transparent 40%),
                radial-gradient(at 50% 100%, rgba(2, 132, 199, 0.08) 0px, transparent 50%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 16px 60px;
            overflow-x: hidden;
            transition: background 0.5s ease;
        }}

        /* Top Bar */
        .top-navbar {{
            width: 100%;
            max-width: 1140px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding: 0 4px;
        }}
        .brand-link {{
            font-size: 21px;
            font-weight: 800;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            letter-spacing: -0.4px;
        }}
        .brand-link span {{
            background: linear-gradient(135deg, #ffffff 40%, var(--cyan-accent) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .nav-actions {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .pipeline-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(34, 197, 94, 0.08);
            border: 1px solid rgba(34, 197, 94, 0.22);
            padding: 7px 14px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            color: #4ade80;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }}
        .pulse-light {{
            width: 7px;
            height: 7px;
            background: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 10px #22c55e;
            animation: pulse-ring 2s infinite;
        }}
        @keyframes pulse-ring {{
            0% {{ transform: scale(0.9); opacity: 0.8; }}
            50% {{ transform: scale(1.35); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.8; }}
        }}
        .theater-btn {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-primary);
            padding: 7px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }}
        .theater-btn:hover {{ background: rgba(255, 255, 255, 0.12); }}

        /* Main Container */
        .viewport-container {{
            width: 100%;
            max-width: 1140px;
            background: var(--surface-panel);
            border: 1px solid var(--border-subtle);
            backdrop-filter: blur(28px);
            border-radius: 28px;
            overflow: hidden;
            box-shadow: 0 35px 90px rgba(0, 0, 0, 0.75);
            transition: max-width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .viewport-container.theater-active {{
            max-width: 98vw;
        }}

        /* Cinema Player & Ambilight Glow */
        .cinema-stage {{
            position: relative;
            width: 100%;
            background: #000000;
            overflow: hidden;
        }}
        .ambilight-glow {{
            position: absolute;
            top: 5%;
            left: 5%;
            width: 90%;
            height: 90%;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.3) 0%, rgba(99, 102, 241, 0.18) 50%, transparent 80%);
            filter: blur(70px);
            z-index: 0;
            pointer-events: none;
            opacity: 0.8;
            transition: background 0.8s ease, opacity 0.5s ease;
        }}
        .player-box {{
            position: relative;
            z-index: 1;
            width: 100%;
            background: #000000;
        }}
        .plyr {{
            border-radius: 0;
            max-height: 80vh;
        }}

        /* Codec Alert */
        .codec-alert {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            background: rgba(245, 158, 11, 0.08);
            border: 1px solid rgba(245, 158, 11, 0.22);
            border-radius: 18px;
            padding: 16px 20px;
            margin: 22px 28px 0;
            color: #fef08a;
        }}
        .alert-icon {{
            color: #f59e0b;
            flex-shrink: 0;
            margin-top: 2px;
        }}
        .alert-title {{
            font-size: 13.5px;
            font-weight: 700;
            color: #fbbf24;
            margin-bottom: 4px;
        }}
        .alert-desc {{
            font-size: 12.5px;
            line-height: 1.55;
            color: #fef3c7;
        }}

        /* Panel Body */
        .panel-body {{
            padding: 30px 32px 38px;
        }}

        /* File Title Header */
        .title-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 20px;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 24px;
            margin-bottom: 26px;
        }}
        .filename-text {{
            font-size: 21px;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1.4;
            word-break: break-all;
            letter-spacing: -0.3px;
        }}
        .pills-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }}
        .tag-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 6px 12px;
            border-radius: 10px;
        }}
        .tag-highlight {{
            color: var(--cyan-accent);
            background: rgba(56, 189, 248, 0.08);
            border-color: rgba(56, 189, 248, 0.22);
            font-weight: 700;
        }}

        /* Actions Dock */
        .actions-dock {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 14px;
            margin-bottom: 28px;
        }}
        .dock-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 16px 20px;
            border-radius: 16px;
            font-size: 14px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .btn-direct-download {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
            color: #ffffff;
            font-size: 16px;
            padding: 18px;
            border: none;
            box-shadow: 0 14px 32px rgba(37, 99, 235, 0.35);
        }}
        .btn-direct-download:hover {{
            transform: translateY(-2px);
            box-shadow: 0 18px 40px rgba(37, 99, 235, 0.5);
        }}
        .btn-player-vlc {{
            background: rgba(249, 115, 22, 0.12);
            color: #fb923c;
            border-color: rgba(249, 115, 22, 0.28);
        }}
        .btn-player-vlc:hover {{
            background: rgba(249, 115, 22, 0.22);
            transform: translateY(-2px);
        }}
        .btn-player-mx {{
            background: rgba(14, 165, 233, 0.12);
            color: #38bdf8;
            border-color: rgba(14, 165, 233, 0.28);
        }}
        .btn-player-mx:hover {{
            background: rgba(14, 165, 233, 0.22);
            transform: translateY(-2px);
        }}
        .btn-player-pot {{
            background: rgba(234, 179, 8, 0.12);
            color: #facc15;
            border-color: rgba(234, 179, 8, 0.28);
        }}
        .btn-player-pot:hover {{
            background: rgba(234, 179, 8, 0.22);
            transform: translateY(-2px);
        }}

        /* URL Copy Bar */
        .copy-bar {{
            display: flex;
            align-items: center;
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 6px 6px 6px 16px;
            margin-bottom: 28px;
            gap: 12px;
        }}
        .copy-input {{
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: var(--cyan-accent);
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .copy-action-btn {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #ffffff;
            font-weight: 700;
            font-size: 13px;
            padding: 10px 18px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }}
        .copy-action-btn:hover {{
            background: rgba(255, 255, 255, 0.16);
        }}

        /* Bento Grid */
        .bento-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 14px;
            margin-bottom: 24px;
        }}
        .bento-card {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: 18px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .bento-label {{
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-bottom: 8px;
        }}
        .bento-value {{
            font-size: 16px;
            font-weight: 700;
            color: #ffffff;
        }}
        .bento-sub {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
            font-family: 'JetBrains Mono', monospace;
        }}

        /* Keyboard Controls HUD */
        .hud-footer {{
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 16px;
            padding-top: 20px;
            border-top: 1px solid var(--border-subtle);
            font-size: 12px;
            color: var(--text-muted);
        }}
        .hud-key {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 6px;
            padding: 2px 7px;
            color: #cbd5e1;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 11px;
        }}

        /* Audio / Vinyl */
        .audio-stage {{
            padding: 60px 24px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .vinyl-record {{
            width: 140px;
            height: 140px;
            border-radius: 50%;
            background: radial-gradient(circle, #1e293b 0%, #0f172a 40%, #020617 100%);
            border: 3px solid rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 40px rgba(56, 189, 248, 0.25);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
            animation: spin 10s linear infinite paused;
        }}
        .vinyl-record.playing {{ animation-play-state: running; }}
        @keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}
        .vinyl-core {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: #0ea5e9;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        }}
        .audio-title {{
            font-size: 22px;
            font-weight: 800;
            color: #ffffff;
            max-width: 640px;
            word-break: break-all;
        }}
        .audio-subtitle {{
            font-size: 14px;
            color: var(--text-muted);
            margin-top: 6px;
        }}
        .audio-player-wrapper {{
            width: 100%;
            max-width: 600px;
            margin-top: 28px;
        }}

        /* Image Stage */
        .image-stage {{
            padding: 30px;
            text-align: center;
        }}
        .image-stage img {{
            max-width: 100%;
            max-height: 75vh;
            border-radius: 18px;
            box-shadow: 0 25px 60px rgba(0,0,0,0.6);
        }}

        /* Doc Stage */
        .doc-stage {{
            padding: 60px 24px;
            text-align: center;
        }}
        .doc-badge {{
            width: 80px;
            height: 80px;
            margin: 0 auto 20px;
            background: rgba(56, 189, 248, 0.08);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .doc-name {{
            font-size: 22px;
            font-weight: 800;
            color: #fff;
            max-width: 640px;
            margin: 0 auto;
            word-break: break-all;
        }}
        .doc-size {{
            font-size: 14px;
            color: var(--text-muted);
            margin-top: 8px;
        }}

        /* Floating Toast */
        .floating-toast {{
            position: fixed;
            bottom: 30px;
            background: rgba(24, 24, 32, 0.95);
            color: #ffffff;
            padding: 14px 28px;
            border-radius: 999px;
            font-size: 14px;
            font-weight: 700;
            border: 1px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(16px);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65);
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
            z-index: 999;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .floating-toast.show {{
            opacity: 1;
            transform: translateY(0);
        }}

        @media (max-width: 768px) {{
            .panel-body {{ padding: 22px 18px 28px; }}
            .bento-grid {{ grid-template-columns: 1fr; }}
            .filename-text {{ font-size: 18px; }}
            .top-navbar {{ flex-wrap: wrap; gap: 12px; }}
        }}
    </style>
</head>
<body>
    <div class="top-navbar">
        <a href="/" class="brand-link">🦅 <span>{BRAND_NAME}</span></a>
        <div class="nav-actions">
            <button class="theater-btn" onclick="toggleTheater()">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
                Theater Mode
            </button>
            <div class="pipeline-pill">
                <span class="pulse-light"></span>
                MTProto Pipeline Active
            </div>
        </div>
    </div>

    <div class="viewport-container" id="mainContainer">
        {player_html}
        {mkv_banner}

        <div class="panel-body">
            <div class="title-header">
                <div>
                    <h1 class="filename-text">{file_name}</h1>
                    <div class="pills-row">
                        <span class="tag-pill tag-highlight">{file_size_fmt}</span>
                        <span class="tag-pill">{category.upper()}</span>
                        <span class="tag-pill">MTProto 1MB Chunks</span>
                        <span class="tag-pill">Zero-RAM Buffer</span>
                        <span class="tag-pill">Valid 24h</span>
                    </div>
                </div>
            </div>

            <div class="actions-dock">
                <a href="{dl_url}" class="dock-btn btn-direct-download" download>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Direct High-Speed Download
                </a>
                <a href="{vlc_url}" class="dock-btn btn-player-vlc">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L6 19H18L12 2ZM12 6.5L14.7 15H9.3L12 6.5Z"/></svg>
                    Open in VLC Player
                </a>
                <a href="{mx_url}" class="dock-btn btn-player-mx">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    Open in MX Player
                </a>
                <a href="{potplayer_url}" class="dock-btn btn-player-pot">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg>
                    Open in PotPlayer
                </a>
            </div>

            <div class="copy-bar">
                <input type="text" class="copy-input" id="streamUrlInput" value="{stream_url}" readonly>
                <button class="copy-action-btn" onclick="copyStreamUrl()">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy Stream Link
                </button>
            </div>

            <div class="bento-grid">
                <div class="bento-card">
                    <div class="bento-label">File Profile</div>
                    <div class="bento-value">{category.capitalize()} Container</div>
                    <div class="bento-sub">{mime_type}</div>
                </div>
                <div class="bento-card">
                    <div class="bento-label">Streaming Protocol</div>
                    <div class="bento-value">MTProto 2GB+ Pipeline</div>
                    <div class="bento-sub">RFC 7233 Byte Seeking</div>
                </div>
                <div class="bento-card">
                    <div class="bento-label">Data Volume</div>
                    <div class="bento-value">{file_size_fmt}</div>
                    <div class="bento-sub">{file_size:,} bytes</div>
                </div>
            </div>

            <div class="hud-footer">
                <span><span class="hud-key">Space</span> Play/Pause</span>
                <span><span class="hud-key">F</span> Fullscreen</span>
                <span><span class="hud-key">T</span> Theater Mode</span>
                <span><span class="hud-key">M</span> Mute</span>
                <span><span class="hud-key">← / →</span> 10s Seek</span>
                <span><span class="hud-key">↑ / ↓</span> Volume</span>
            </div>
        </div>
    </div>

    <div id="toast" class="floating-toast">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
        Direct stream link copied to clipboard!
    </div>

    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const videoEl = document.getElementById('player');
            const vinyl = document.getElementById('vinylRecord');

            if (videoEl) {{
                const player = new Plyr(videoEl, {{
                    controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                    speed: {{ selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] }},
                    keyboard: {{ focused: true, global: true }},
                    seekTime: 10
                }});

                if (vinyl) {{
                    videoEl.addEventListener('play', () => vinyl.classList.add('playing'));
                    videoEl.addEventListener('pause', () => vinyl.classList.remove('playing'));
                }}

                // Keyboard 'T' for theater mode
                document.addEventListener('keydown', (e) => {{
                    if (e.key === 't' || e.key === 'T') {{
                        if (document.activeElement.tagName !== 'INPUT') {{
                            toggleTheater();
                        }}
                    }}
                }});
            }}
        }});

        function toggleTheater() {{
            const c = document.getElementById('mainContainer');
            if (c) {{
                c.classList.toggle('theater-active');
            }}
        }}

        function copyStreamUrl() {{
            const input = document.getElementById('streamUrlInput');
            if (input) {{
                navigator.clipboard.writeText(input.value).then(() => {{
                    const toast = document.getElementById('toast');
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2500);
                }});
            }}
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

    return web.Response(text="Streaming pipeline unavailable for this file size.", status=503)

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
    # Initialize MTProto Pyrogram client
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
