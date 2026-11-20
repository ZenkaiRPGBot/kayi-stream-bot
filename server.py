import asyncio
import os
import aiohttp
from aiohttp import web
import mimetypes
from datetime import datetime, timezone

from config import BOT_TOKEN, PORT, PING_URL, BRAND_NAME, SERVER_URL, CHANNEL_USERNAME
import database as db

mimetypes.init()

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
    <title>{BRAND_NAME} — High Speed Cloud Stream Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: radial-gradient(circle at 50% 0%, #1e1b4b, #09090b 70%);
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            background: rgba(24, 24, 27, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(16px);
            border-radius: 24px;
            padding: 40px;
            max-width: 520px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }}
        .logo {{ font-size: 52px; margin-bottom: 12px; }}
        h1 {{ font-size: 28px; font-weight: 800; background: linear-gradient(135deg, #a5b4fc, #38bdf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        p {{ color: #a1a1aa; font-size: 14px; margin-top: 8px; line-height: 1.6; }}
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
            background: linear-gradient(135deg, #4f46e5, #0ea5e9);
            color: #fff;
            padding: 14px;
            border-radius: 14px;
            text-decoration: none;
            font-weight: 600;
            font-size: 15px;
            transition: all 0.2s ease;
        }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 10px 25px rgba(14, 165, 233, 0.3); }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🦅</div>
        <h1>{BRAND_NAME}</h1>
        <p>Ultra-Fast File to Direct Link & Video Streaming Engine for Telegram. Zero waiting, full Range seek support, and crystal clear web playback.</p>
        
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

        <a href="https://t.me/{CHANNEL_USERNAME.lstrip('@')}" class="btn">🚀 Join Ecosystem on Telegram</a>
    </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")

async def handle_health(request: web.Request) -> web.Response:
    stats = await db.get_global_stats()
    return web.json_response({
        "status": "healthy",
        "service": "kayi-stream-bot",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": stats
    })

async def handle_watch(request: web.Request) -> web.Response:
    token = request.match_info.get("token")
    record = await db.get_file_record(token)
    if not record:
        return web.Response(
            text="""<!DOCTYPE html><html><body style="background:#09090b;color:#f4f4f5;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;padding:24px;"><h1>404 - Link Expired or Not Found</h1><p style="color:#71717a;margin-top:8px;">This link has expired or has been revoked by the owner.</p></div></body></html>""",
            content_type="text/html",
            status=404
        )

    file_name = record["file_name"]
    file_size_fmt = format_file_size(record["file_size"])
    mime_type = record.get("mime_type") or "application/octet-stream"
    dl_url = f"{SERVER_URL}/dl/{token}"
    stream_url = dl_url
    category = get_media_category(mime_type, file_name)

    # 3rd-party player schemes
    vlc_url = f"vlc://{stream_url.replace('https://', '').replace('http://', '')}"
    mx_url = f"intent:{stream_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end"
    mx_pro_url = f"intent:{stream_url}#Intent;package=com.mxtech.videoplayer.pro;type=video/*;end"

    # Dynamic player block
    if category == "video":
        player_html = f"""
        <div class="player-wrapper">
            <video id="player" playsinline controls preload="metadata">
                <source src="{stream_url}" type="{mime_type}">
            </video>
        </div>"""
    elif category == "audio":
        player_html = f"""
        <div class="audio-wrapper">
            <div class="disc-glow"></div>
            <div class="disc-icon">🎵</div>
            <div class="audio-title">{file_name}</div>
            <div class="audio-sub">High Fidelity Stream</div>
            <audio id="player" controls style="width: 100%; margin-top: 24px;">
                <source src="{stream_url}" type="{mime_type}">
            </audio>
        </div>"""
    elif category == "image":
        player_html = f"""
        <div class="image-wrapper">
            <img src="{stream_url}" alt="{file_name}" style="max-width:100%;max-height:70vh;border-radius:16px;">
        </div>"""
    else:
        player_html = f"""
        <div class="doc-wrapper">
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
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --plyr-color-main: #38bdf8;
            --plyr-video-background: #000;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: #09090b;
            color: #f4f4f5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 16px 40px;
        }}
        .top-nav {{
            width: 100%;
            max-width: 980px;
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
            gap: 8px;
            text-decoration: none;
        }}
        .brand span {{ color: #38bdf8; }}
        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(56, 189, 248, 0.1);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.2);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .main-card {{
            width: 100%;
            max-width: 980px;
            background: #121216;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
        }}
        .player-wrapper {{
            width: 100%;
            background: #000;
        }}
        .plyr {{ border-radius: 0; }}
        .audio-wrapper, .doc-wrapper, .image-wrapper {{
            padding: 48px 24px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .disc-icon, .doc-icon {{
            font-size: 64px;
            margin-bottom: 16px;
        }}
        .audio-title, .doc-title {{
            font-size: 20px;
            font-weight: 700;
            word-break: break-all;
            max-width: 600px;
        }}
        .audio-sub, .doc-size {{
            font-size: 13px;
            color: #71717a;
            margin-top: 6px;
        }}
        .content-body {{
            padding: 28px;
        }}
        .file-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .file-name {{
            font-size: 18px;
            font-weight: 700;
            line-height: 1.4;
            word-break: break-all;
        }}
        .meta-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}
        .tag {{
            font-size: 12px;
            color: #a1a1aa;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 4px 10px;
            border-radius: 8px;
        }}
        .action-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-top: 20px;
        }}
        .action-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 14px 20px;
            border-radius: 14px;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
        }}
        .btn-download {{
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            grid-column: 1 / -1;
            font-size: 16px;
            padding: 16px;
        }}
        .btn-download:hover {{ box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35); transform: translateY(-1px); }}
        .btn-vlc {{
            background: rgba(255, 128, 0, 0.1);
            color: #fb923c;
            border: 1px solid rgba(255, 128, 0, 0.2);
        }}
        .btn-vlc:hover {{ background: rgba(255, 128, 0, 0.2); }}
        .btn-mx {{
            background: rgba(56, 189, 248, 0.1);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}
        .btn-mx:hover {{ background: rgba(56, 189, 248, 0.2); }}
        .btn-copy {{
            background: rgba(255, 255, 255, 0.05);
            color: #e4e4e7;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .btn-copy:hover {{ background: rgba(255, 255, 255, 0.1); }}
        .toast {{
            position: fixed;
            bottom: 24px;
            background: #18181b;
            color: #fff;
            padding: 12px 24px;
            border-radius: 999px;
            font-size: 14px;
            font-weight: 600;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
            z-index: 100;
        }}
        .toast.show {{ opacity: 1; transform: translateY(0); }}
    </style>
</head>
<body>
    <div class="top-nav">
        <a href="/" class="brand">🦅 <span>{BRAND_NAME}</span></a>
        <div class="badge">Live Stream</div>
    </div>

    <div class="main-card">
        {player_html}

        <div class="content-body">
            <div class="file-header">
                <div>
                    <h1 class="file-name">{file_name}</h1>
                    <div class="meta-tags">
                        <span class="tag">📦 {file_size_fmt}</span>
                        <span class="tag">🎬 {category.upper()}</span>
                        <span class="tag">🛡️ Verified Clean</span>
                        <span class="tag">⚡ 64KB Buffer</span>
                    </div>
                </div>
            </div>

            <div class="action-grid">
                <a href="{dl_url}" class="action-btn btn-download" download>
                    ⬇️ High-Speed Direct Download
                </a>
                <a href="{vlc_url}" class="action-btn btn-vlc">
                    ⚡ Open in VLC Player
                </a>
                <a href="{mx_url}" class="action-btn btn-mx">
                    📱 Open in MX Player
                </a>
                <button class="action-btn btn-copy" onclick="copyStreamUrl()">
                    📋 Copy Direct Stream Link
                </button>
            </div>
        </div>
    </div>

    <div id="toast" class="toast">Link copied to clipboard! ✅</div>

    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const el = document.getElementById('player');
            if (el) {{
                new Plyr(el, {{
                    controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                    speed: {{ selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] }},
                    keyboard: {{ focused: true, global: true }}
                }});
            }}
        }});

        function copyStreamUrl() {{
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

    # Fetch file path from Telegram
    get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(get_file_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return web.Response(text="Failed to retrieve file from Telegram servers.", status=502)
            data = await resp.json()
            if not data.get("ok"):
                return web.Response(text=f"Telegram API Error: {data.get('description', 'Unknown')}", status=502)
            file_path = data["result"]["file_path"]

        # Stream file from Telegram file server with Range Header pass-through
        stream_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        headers = {}
        range_header = request.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        async with session.get(stream_url, headers=headers, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as upstream_resp:
            status = upstream_resp.status
            response = web.StreamResponse(status=status)

            # Pass forward relevant headers
            for h in ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"]:
                val = upstream_resp.headers.get(h)
                if val:
                    response.headers[h] = val

            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Disposition"] = f'attachment; filename="{file_name}"'

            if request.method == "HEAD":
                await response.prepare(request)
                await response.write_eof()
                return response

            await response.prepare(request)

            # Stream chunk-by-chunk (128 KB buffer)
            try:
                async for chunk in upstream_resp.content.iter_chunked(131072):
                    await response.write(chunk)
                await response.write_eof()
            except (asyncio.CancelledError, ConnectionResetError):
                pass
            
            asyncio.create_task(db.increment_download_count(token))
            return response

async def ping_self_loop():
    if not PING_URL:
        print("[keep_alive] No PING_URL configured. Self-ping loop disabled.")
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
