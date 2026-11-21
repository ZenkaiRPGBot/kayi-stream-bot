import asyncio
import os
import math
import mimetypes
import re
import json
from datetime import datetime, timezone
import aiosqlite
import aiohttp
from aiohttp import web

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, API_ID, API_HASH,
    PORT, PING_URL, BRAND_NAME, CHANNEL_USERNAME, IST, get_server_url
)
import database as db
import tracks

mimetypes.init()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

from streamer import FastByteStreamer

# Pyrogram MTProto Client & FastByteStreamer for unlimited streaming
pyrogram_client = None
byte_streamer: FastByteStreamer | None = None

async def init_pyrogram_client():
    global pyrogram_client, byte_streamer
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
                max_concurrent_transmissions=16
            )
            await pyrogram_client.start()
            me = await pyrogram_client.get_me()
            byte_streamer = FastByteStreamer(pyrogram_client)
            print(f"[MTProto] Turbo FastByteStreamer connected as @{me.username}! (TgCrypto C-accelerator online)")
        except Exception as e:
            print(f"[MTProto] Failed to initialize Pyrogram client: {e}")
            pyrogram_client = None
            byte_streamer = None
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
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{initial_script}}", "")
        html = html.replace("{{stream_src}}", "")
        return web.Response(text=html, content_type="text/html")

    return web.Response(text="Kayi Stream App Ready", content_type="text/plain")

async def handle_api_user_files(request: web.Request) -> web.Response:
    user_id_str = request.query.get("user_id")
    user_id = None
    if user_id_str:
        try:
            user_id = int(user_id_str)
        except ValueError:
            pass

    files = []
    if user_id:
        files = await db.get_user_files(user_id, limit=50)

    # Fallback to recent active files in library if no user files found or outside Telegram
    if not files:
        now = datetime.now(IST)
        async with aiosqlite.connect(db.DB_PATH) as database:
            database.row_factory = aiosqlite.Row
            async with database.execute(
                "SELECT * FROM files WHERE expires_at > ? ORDER BY id DESC LIMIT 50",
                (now.isoformat(),)
            ) as cursor:
                rows = await cursor.fetchall()
                files = [dict(r) for r in rows]

    base_url = get_server_url()

    formatted = []
    for f in files:
        disp_id = f.get("display_id") or str(f["id"])
        formatted.append({
            "id": f["id"],
            "display_id": disp_id,
            "token": f["token"],
            "name": f["file_name"],
            "size": f["file_size"],
            "file_id": f.get("file_id") or "",
            "file_unique_id": f.get("file_unique_id") or "",
            "size_fmt": format_file_size(f["file_size"]),
            "mime_type": f["mime_type"],
            "category": get_media_category(f["mime_type"], f["file_name"]),
            "quality": detect_quality_tag(f["file_name"], f["file_size"]),
            "created_at": f["created_at"],
            "watch_url": f"{base_url}/watch/{disp_id}",
            "stream_url": f"{base_url}/stream/{disp_id}",
            "dl_url": f"{base_url}/dl/{disp_id}"
        })
    return web.json_response({"status": "success", "count": len(formatted), "files": formatted})

async def handle_api_delete_file(request: web.Request) -> web.Response:
    identifier = request.match_info.get("identifier")
    user_id_str = request.query.get("user_id")
    user_id = int(user_id_str) if user_id_str and user_id_str.isdigit() else None
    
    success = await db.delete_file_by_id_or_token(identifier, user_id=user_id)
    if success:
        return web.json_response({"status": "success", "message": "File removed successfully"})
    return web.json_response({"status": "error", "message": "File not found or unauthorized"}, status=404)

async def handle_api_stats(request: web.Request) -> web.Response:
    stats = await db.get_global_stats()
    return web.json_response({
        "status": "success",
        "total_files": stats.get("total_files", 0),
        "active_files": stats.get("active_links", 0),
        "active_links": stats.get("active_links", 0),
        "active_bytes": stats.get("active_bytes", 0),
        "active_bytes_fmt": format_file_size(stats.get("active_bytes", 0)),
        "total_downloads": stats.get("total_downloads", 0)
    })

async def handle_api_file_info(request: web.Request) -> web.Response:
    identifier = request.match_info.get("identifier")
    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.json_response({"status": "error", "message": "File not found or expired"}, status=404)
    base_url = get_server_url()
    disp_id = record.get("display_id") or str(record["id"])
    return web.json_response({
        "status": "success",
        "file": {
            "id": record["id"],
            "display_id": disp_id,
            "token": record["token"],
            "name": record["file_name"],
            "size": record["file_size"],
            "file_id": record.get("file_id") or "",
            "file_unique_id": record.get("file_unique_id") or "",
            "size_fmt": format_file_size(record["file_size"]),
            "mime_type": record["mime_type"],
            "category": get_media_category(record["mime_type"], record["file_name"]),
            "quality": detect_quality_tag(record["file_name"], record["file_size"]),
            "watch_url": f"{base_url}/watch/{disp_id}",
            "stream_url": f"{base_url}/stream/{disp_id}",
            "dl_url": f"{base_url}/dl/{disp_id}"
        }
    })

async def handle_health(request: web.Request) -> web.Response:
    stats = await db.get_global_stats()
    return web.json_response({
        "status": "healthy",
        "service": "kayi-stream-bot",
        "mtproto_active": pyrogram_client is not None,
        "fast_streamer_active": byte_streamer is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": stats
    })

async def handle_watch(request: web.Request) -> web.Response:
    identifier = request.match_info.get("identifier")
    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.Response(
            text="""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Link Expired · Kayi Stream</title><link rel="stylesheet" href="/static/app.css"></head><body style="display:flex;align-items:center;justify-content:center;height:100vh;background:#F8FAFC;"><div style="background:#FFF;border:1px solid #E2E8F0;border-radius:16px;padding:36px 32px;text-align:center;max-width:380px;box-shadow:0 4px 20px rgba(0,0,0,0.04);"><h2 style="font-size:18px;font-weight:700;color:#111827;margin-bottom:8px;">Link Expired or Not Found</h2><p style="color:#64748B;font-size:14px;margin-bottom:20px;">This streaming link has expired or has been removed from the library.</p><a href="/" style="display:inline-block;padding:10px 18px;background:#DC2626;color:#FFF;border-radius:10px;font-weight:600;font-size:13px;text-decoration:none;">Go to Home</a></div></body></html>""",
            content_type="text/html",
            status=404
        )

    f_id = record["id"]
    disp_id = record.get("display_id") or str(f_id)
    file_name = record["file_name"]
    file_size = record["file_size"]
    file_size_fmt = format_file_size(file_size)
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    fmt_label = ext.upper() if ext else "FILE"
    quality_label = detect_quality_tag(file_name, file_size)

    server_base = get_server_url()
    stream_url = f"{server_base}/stream/{disp_id}"
    dl_url = f"{server_base}/dl/{disp_id}"

    initial_file = {
        "id": f_id,
        "display_id": disp_id,
        "file_id": record.get("file_id") or "",
        "file_unique_id": record.get("file_unique_id") or "",
        "name": file_name,
        "size": file_size,
        "size_fmt": file_size_fmt,
        "format": fmt_label,
        "category": get_media_category(record["mime_type"], file_name),
        "quality": quality_label,
        "stream_url": stream_url,
        "dl_url": dl_url
    }

    t_val = request.query.get("t")
    if t_val:
        try:
            initial_file["resume_time"] = float(t_val)
        except (ValueError, TypeError):
            pass

    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        html = "<html><body><h1>App template not found</h1></body></html>"

    inject_js = f"window.__INITIAL_FILE__ = {json.dumps(initial_file)};"
    html = html.replace("{{initial_script}}", inject_js)
    html = html.replace("{{stream_src}}", stream_url)

    # Prewarm media in background
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
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Cache-Control": "public, max-age=3600"
    }
    try:
        stream_index = int(index_str)
    except Exception:
        return web.Response(text="Invalid stream index", status=400, headers=cors_headers)

    record = await db.get_file_by_id_or_token(identifier)
    if not record:
        return web.Response(text="File not found", status=404, headers=cors_headers)

    f_id = record["id"]
    local_url = f"http://127.0.0.1:{PORT}/dl/{f_id}"

    vtt_path = await tracks.extract_subtitle(f_id, local_url, stream_index)
    if not vtt_path or not os.path.exists(vtt_path):
        return web.Response(text="WEBVTT\n\n", content_type="text/vtt", charset="utf-8", headers=cors_headers)

    try:
        with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
            vtt_content = f.read()
        return web.Response(text=vtt_content, content_type="text/vtt", charset="utf-8", headers=cors_headers)
    except Exception as e:
        return web.Response(text="WEBVTT\n\n", content_type="text/vtt", charset="utf-8", headers=cors_headers)

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

async def handle_options_cors(request: web.Request) -> web.Response:
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Accept-Ranges, Content-Range, Content-Length, Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
            "Access-Control-Max-Age": "86400",
        }
    )

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

    # Detect proper media MIME type so browser engines decode correctly
    fn_lower = file_name.lower()
    if fn_lower.endswith(".mkv"):
        mime_type = "video/x-matroska"
    elif fn_lower.endswith(".mp4"):
        mime_type = "video/mp4"
    elif fn_lower.endswith(".webm"):
        mime_type = "video/webm"
    elif fn_lower.endswith(".mov"):
        mime_type = "video/quicktime"
    elif fn_lower.endswith(".ts"):
        mime_type = "video/mp2t"
    elif not mime_type or mime_type == "application/octet-stream":
        mime_type = "video/mp4"

    # 1. Zero-Disk MTProto Streaming Engine (FastByteStreamer with persistent DC sessions)
    if byte_streamer is not None:
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
            response.enable_compression(False)
            response.headers["Content-Type"] = mime_type
            response.headers["Content-Length"] = str(content_length)
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Cache-Control"] = "public, max-age=86400, immutable"
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Range, Accept-Ranges, Content-Range, Content-Length, Content-Type, Authorization"
            response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges"
            
            disposition_type = "attachment" if is_download else "inline"
            response.headers["Content-Disposition"] = f'{disposition_type}; filename="{safe_name}"'
            
            if range_header:
                response.headers["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"

            if request.method == "HEAD":
                await response.prepare(request)
                await response.write_eof()
                return response

            await response.prepare(request)

            async for chunk in byte_streamer.yield_file(file_id, start_byte, content_length):
                try:
                    await response.write(chunk)
                except (ConnectionResetError, aiohttp.ClientConnectionError, asyncio.CancelledError):
                    break

            await response.write_eof()
            if is_download:
                asyncio.create_task(db.increment_download_count(record["token"]))
            return response

        except Exception as e:
            print(f"[FastByteStreamer Error] {e}")

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
    target_url = PING_URL.rstrip("/") + "/health"
    print(f"[keep_alive] Self-ping active! Target: {target_url} (every 4 minutes)")
    await asyncio.sleep(20)
    headers = {"User-Agent": "KayiStream-KeepAlive/1.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            try:
                async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    print(f"[keep_alive] Self-ping status: {resp.status}")
            except Exception as e:
                print(f"[keep_alive] Self-ping failed: {e}")
            await asyncio.sleep(240)

async def start_server():
    # Initialize MTProto Pyrogram client
    await init_pyrogram_client()

    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/app", handle_root)
    app.router.add_get("/webapp", handle_root)
    app.router.add_get("/health", handle_health)
    
    # Static files route for player.css, player.js, dashboard.js
    app.router.add_static("/static", path=STATIC_DIR, name="static")

    # API endpoints for Mini App & dashboard
    app.router.add_get("/api/user/files", handle_api_user_files)
    app.router.add_get("/api/stats", handle_api_stats)
    app.router.add_get("/api/file/{identifier}", handle_api_file_info)
    app.router.add_delete("/api/file/{identifier}", handle_api_delete_file)
    app.router.add_post("/api/file/{identifier}/delete", handle_api_delete_file)

    # API endpoints for tracks & subtitles
    app.router.add_get("/api/media/{identifier}/tracks", handle_get_tracks)
    app.router.add_get("/api/media/{identifier}/subs/{index}.vtt", handle_get_subtitle)

    # HLS streaming endpoints
    app.router.add_get("/hls/{identifier}/{filename}", handle_hls_file)

    # Dual support for /watch, /stream, /dl by numerical ID or token
    app.router.add_get("/watch/{identifier}", handle_watch)
    app.router.add_get("/stream/{identifier}", handle_stream)
    app.router.add_get("/dl/{identifier}", handle_download)

    # CORS OPTIONS routes for WASM Range requests
    app.router.add_route("OPTIONS", "/stream/{identifier}", handle_options_cors)
    app.router.add_route("OPTIONS", "/dl/{identifier}", handle_options_cors)
    app.router.add_route("OPTIONS", "/api/{tail:.*}", handle_options_cors)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[server] Streaming server listening on port {PORT}")
    asyncio.create_task(ping_self_loop())
    return runner
