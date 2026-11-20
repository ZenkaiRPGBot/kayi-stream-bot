import asyncio
import os
import math
import mimetypes
import re
import json
from datetime import datetime, timezone
import aiohttp
from aiohttp import web

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, API_ID, API_HASH,
    PORT, PING_URL, BRAND_NAME, CHANNEL_USERNAME, get_server_url
)
import database as db
import tracks

mimetypes.init()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

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
                in_memory=True,
                max_concurrent_transmissions=10
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

def detect_quality_tag(file_name: str, file_size: int) -> str:
    fn = file_name.upper()
    if "2160P" in fn or "4K" in fn or "UHD" in fn:
        return "4K UHD"
    elif "1080P" in fn or "FHD" in fn:
        return "1080p FHD"
    elif "720P" in fn or "HD" in fn:
        return "720p HD"
    elif file_size > 1024**3:
        return "HD"
    return "Direct"

async def handle_root(request: web.Request) -> web.Response:
    stats = await db.get_global_stats()
    storage_fmt = format_file_size(stats["active_bytes"])
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#FFFFFF">
<title>{BRAND_NAME}</title>
<style>
:root {{
  --bg-color: #FFFFFF;
  --surface-color: #F5F5F7;
  --text-primary: #1D1D1F;
  --text-secondary: #6E6E73;
  --border-color: #E5E5EA;
  --accent-color: #0A84FF;
  --radius-md: 12px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: Inter, system-ui, -apple-system, sans-serif;
  background-color: var(--bg-color);
  color: var(--text-primary);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}}
.card {{
  background-color: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  padding: 40px 32px;
  max-width: 440px;
  width: 100%;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}}
h1 {{ font-size: 24px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 8px; }}
p {{ color: var(--text-secondary); font-size: 14px; line-height: 1.5; margin-bottom: 24px; }}
.stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 28px; }}
.stat {{ background-color: var(--surface-color); border-radius: var(--radius-md); padding: 12px 8px; }}
.stat-num {{ font-size: 17px; font-weight: 700; color: var(--accent-color); }}
.stat-lbl {{ font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; margin-top: 3px; letter-spacing: 0.06em; }}
.btn {{
  display: flex; align-items: center; justify-content: center; width: 100%;
  padding: 13px; border-radius: var(--radius-md); font-size: 15px; font-weight: 600;
  text-decoration: none; color: #FFFFFF; background-color: var(--accent-color);
  transition: opacity 150ms ease-out;
}}
.btn:hover {{ opacity: 0.9; }}
</style>
</head>
<body>
<div class="card">
  <h1>{BRAND_NAME}</h1>
  <p>Minimal, high-performance streaming and file downloads. No clutter, zero latency.</p>
  <div class="stats">
    <div class="stat">
      <div class="stat-num">{stats['active_links']}</div>
      <div class="stat-lbl">Active</div>
    </div>
    <div class="stat">
      <div class="stat-num">{storage_fmt}</div>
      <div class="stat-lbl">Storage</div>
    </div>
    <div class="stat">
      <div class="stat-num">{stats['total_downloads']}</div>
      <div class="stat-lbl">Downloads</div>
    </div>
  </div>
  <a href="https://t.me/{CHANNEL_USERNAME.lstrip('@')}" class="btn">Launch on Telegram</a>
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
    identifier = request.match_info.get("identifier")
    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.Response(
            text="""<!DOCTYPE html><html><body style="background:#FFFFFF;color:#1D1D1F;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;padding:24px;"><h1>Link expired or not found</h1><p style="color:#6E6E73;margin-top:8px;">This link has expired or has been removed.</p></div></body></html>""",
            content_type="text/html",
            status=404
        )

    f_id = record["id"]
    token = record["token"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    file_size_fmt = format_file_size(file_size)
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    fmt_label = ext.upper() if ext else "FILE"
    quality_label = detect_quality_tag(file_name, file_size)

    server_base = get_server_url()
    stream_url = f"{server_base}/stream/{token}"
    dl_url = f"{server_base}/dl/{token}"

    # Third-party player schemes
    clean_stream_url = stream_url.replace("https://", "").replace("http://", "")
    vlc_url = f"vlc://{clean_stream_url}"
    mx_url = f"intent:{stream_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;S.title={file_name};end"
    potplayer_url = f"potplayer://{stream_url}"

    file_data_json = json.dumps({
        "id": f_id,
        "name": file_name,
        "size": file_size_fmt,
        "format": fmt_label,
        "quality": quality_label,
        "stream": stream_url,
        "download": dl_url
    })

    # Read template from static/index.html
    template_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        template = "<html><body><h1>Player template missing</h1></body></html>"

    # Replace template variables
    html = template.replace("{{file_name}}", file_name)
    html = html.replace("{{brand_name}}", BRAND_NAME)
    html = html.replace("{{file_id}}", str(f_id))
    html = html.replace("{{file_size}}", file_size_fmt)
    html = html.replace("{{file_format}}", fmt_label)
    html = html.replace("{{quality_tag}}", quality_label)
    html = html.replace("{{download_url}}", dl_url)
    html = html.replace("{{vlc_url}}", vlc_url)
    html = html.replace("{{mx_url}}", mx_url)
    html = html.replace("{{potplayer_url}}", potplayer_url)
    html = html.replace("{{file_data_json}}", file_data_json)

    # Trigger background probe so tracks and HLS are ready early
    asyncio.create_task(_prewarm_media(f_id, dl_url))

    return web.Response(text=html, content_type="text/html")

async def _prewarm_media(file_id: int, stream_url: str):
    try:
        # Use localhost URL for fast local probing
        local_url = f"http://127.0.0.1:{PORT}/dl/{file_id}"
        t_data = await tracks.probe_file(file_id, local_url)
        if t_data.get("mode") == "hls":
            await tracks.ensure_hls_generation(file_id, local_url, t_data)
        # Background extract first supported subtitle track if available
        for s in t_data.get("subtitles", []):
            if s.get("supported"):
                asyncio.create_task(tracks.extract_subtitle(file_id, local_url, s["index"]))
                break
    except Exception as e:
        print(f"[prewarm] Error prewarming file {file_id}: {e}")

async def handle_get_tracks(request: web.Request) -> web.Response:
    identifier = request.match_info.get("identifier")
    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.json_response({"error": "File not found"}, status=404)

    f_id = record["id"]
    local_url = f"http://127.0.0.1:{PORT}/dl/{f_id}"

    t_data = await tracks.probe_file(f_id, local_url)

    # If HLS mode is needed, ensure background HLS generator is started
    if t_data.get("mode") == "hls":
        asyncio.create_task(tracks.ensure_hls_generation(f_id, local_url, t_data))

    return web.json_response(t_data)

async def handle_get_subtitle(request: web.Request) -> web.Response:
    identifier = request.match_info.get("identifier")
    index_str = request.match_info.get("index")
    try:
        stream_index = int(index_str)
    except Exception:
        return web.Response(text="Invalid stream index", status=400)

    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.Response(text="File not found", status=404)

    f_id = record["id"]
    local_url = f"http://127.0.0.1:{PORT}/dl/{f_id}"

    vtt_path = await tracks.extract_subtitle(f_id, local_url, stream_index)
    if not vtt_path or not os.path.exists(vtt_path):
        return web.Response(text="WEBVTT\n\n", content_type="text/vtt", charset="utf-8")

    try:
        with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
            vtt_content = f.read()
        return web.Response(text=vtt_content, content_type="text/vtt", charset="utf-8")
    except Exception as e:
        return web.Response(text="WEBVTT\n\n", content_type="text/vtt", charset="utf-8")

async def handle_hls_file(request: web.Request) -> web.Response:
    identifier = request.match_info.get("identifier")
    filename = request.match_info.get("filename")

    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.Response(text="File not found", status=404)

    f_id = record["id"]
    file_path = os.path.join(tracks.CACHE_BASE_DIR, str(f_id), "hls", filename)

    # If master.m3u8 or stream playlist is not yet written, wait up to 15 seconds
    if filename.endswith(".m3u8") and not os.path.exists(file_path):
        local_url = f"http://127.0.0.1:{PORT}/dl/{f_id}"
        t_data = await tracks.probe_file(f_id, local_url)
        await tracks.ensure_hls_generation(f_id, local_url, t_data)
        for _ in range(30):
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                break
            await asyncio.sleep(0.5)

    if not os.path.exists(file_path):
        if filename == "master.m3u8":
            fallback_var = os.path.join(tracks.CACHE_BASE_DIR, str(f_id), "hls", "stream_0.m3u8")
            if os.path.exists(fallback_var) and os.path.getsize(fallback_var) > 0:
                synth = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=2500000\nstream_0.m3u8\n"
                return web.Response(text=synth, content_type="application/vnd.apple.mpegurl", headers={"Access-Control-Allow-Origin": "*"})
        return web.Response(text="Segment not ready", status=404)

    if filename.endswith(".m3u8"):
        c_type = "application/vnd.apple.mpegurl"
    elif filename.endswith(".ts"):
        c_type = "video/MP2T"
    else:
        c_type = "application/octet-stream"

    return web.FileResponse(file_path, headers={"Content-Type": c_type, "Access-Control-Allow-Origin": "*"})

async def handle_stream(request: web.Request) -> web.StreamResponse:
    return await handle_media_transfer(request, is_download=False)

async def handle_download(request: web.Request) -> web.StreamResponse:
    return await handle_media_transfer(request, is_download=True)

async def handle_media_transfer(request: web.Request, is_download: bool) -> web.StreamResponse:
    identifier = request.match_info.get("identifier")
    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.Response(text="File not found or link expired.", status=404)

    file_id = record["file_id"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    mime_type = record.get("mime_type") or "application/octet-stream"

    # Clean file name for Content-Disposition
    safe_name = re.sub(r'[^\w\.\-\s\[\]\(\)]', '_', file_name)

    # 1. MTProto Streaming Engine (Pyrogram - handles files up to 2GB/4GB)
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
            
            disposition_type = "attachment" if is_download else "inline"
            response.headers["Content-Disposition"] = f'{disposition_type}; filename="{safe_name}"'
            
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

                try:
                    await response.write(chunk)
                except (ConnectionResetError, aiohttp.ClientConnectionError, asyncio.CancelledError):
                    break
                bytes_to_send -= len(chunk)
                if bytes_to_send <= 0:
                    break

            await response.write_eof()
            if is_download:
                asyncio.create_task(db.increment_download_count(record["token"]))
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

            upstream_stream_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            headers = {}
            range_header = request.headers.get("Range")
            if range_header:
                headers["Range"] = range_header

            async with session.get(upstream_stream_url, headers=headers, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as upstream_resp:
                status = upstream_resp.status
                response = web.StreamResponse(status=status)

                for h in ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"]:
                    val = upstream_resp.headers.get(h)
                    if val:
                        response.headers[h] = val

                response.headers["Accept-Ranges"] = "bytes"
                disposition_type = "attachment" if is_download else "inline"
                response.headers["Content-Disposition"] = f'{disposition_type}; filename="{safe_name}"'

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

                if is_download:
                    asyncio.create_task(db.increment_download_count(record["token"]))
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
    
    # Static files route for player.css and player.js
    app.router.add_static("/static", path=STATIC_DIR, name="static")

    # API endpoints for tracks & subtitles
    app.router.add_get("/api/media/{identifier}/tracks", handle_get_tracks)
    app.router.add_get("/api/media/{identifier}/subs/{index}.vtt", handle_get_subtitle)

    # HLS streaming endpoints
    app.router.add_get("/hls/{identifier}/{filename}", handle_hls_file)

    # Dual support for /watch, /stream, /dl by numerical ID or token
    app.router.add_get("/watch/{identifier}", handle_watch)
    app.router.add_get("/stream/{identifier}", handle_stream)
    app.router.add_get("/dl/{identifier}", handle_download)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[server] Streaming server listening on port {PORT}")
    asyncio.create_task(ping_self_loop())
    return runner
