import asyncio
import aiohttp
from aiohttp import web
from config import BOT_TOKEN, PORT, PING_URL, BRAND_NAME, SERVER_URL
import database as db

async def handle_root(request: web.Request) -> web.Response:
    return web.Response(text=f"{BRAND_NAME} Streaming Server is active and healthy! 🚀", content_type="text/plain")

async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "kayi-stream-bot"})

async def handle_watch(request: web.Request) -> web.Response:
    token = request.match_info.get("token")
    record = await db.get_file_record(token)
    if not record:
        return web.Response(text="<h1>404 - File Not Found or Link Expired</h1>", content_type="text/html", status=404)

    file_name = record["file_name"]
    dl_url = f"{SERVER_URL}/dl/{token}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_name} - {BRAND_NAME}</title>
    <style>
        body {{
            background: #0d1117;
            color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }}
        .header {{
            font-size: 22px;
            font-weight: bold;
            color: #58a6ff;
            margin-bottom: 20px;
            text-align: center;
        }}
        .player-container {{
            width: 100%;
            max-width: 900px;
            background: #161b22;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            border: 1px solid #30363d;
        }}
        video {{
            width: 100%;
            height: auto;
            max-height: 540px;
            display: block;
            background: #000;
        }}
        .info-card {{
            padding: 20px;
        }}
        .file-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            word-break: break-all;
        }}
        .btn {{
            display: inline-block;
            background: #238636;
            color: #fff;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            transition: 0.2s;
        }}
        .btn:hover {{
            background: #2ea043;
        }}
    </style>
</head>
<body>
    <div class="header">🦅 {BRAND_NAME} Player</div>
    <div class="player-container">
        <video controls preload="metadata" playsinline>
            <source src="{dl_url}" type="{record.get('mime_type') or 'video/mp4'}">
            Your browser does not support video playback.
        </video>
        <div class="info-card">
            <div class="file-title">📁 {file_name}</div>
            <a href="{dl_url}" class="btn" download>⬇️ Download File</a>
        </div>
    </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")

async def handle_download(request: web.Request) -> web.StreamResponse:
    token = request.match_info.get("token")
    record = await db.get_file_record(token)
    if not record:
        return web.Response(text="File not found or expired", status=404)

    file_id = record["file_id"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    mime_type = record.get("mime_type") or "application/octet-stream"

    # Get file path from Telegram API
    get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(get_file_url) as resp:
            if resp.status != 200:
                return web.Response(text="Failed to retrieve file from Telegram", status=502)
            data = await resp.json()
            if not data.get("ok"):
                return web.Response(text="Telegram file error", status=502)
            file_path = data["result"]["file_path"]

        # Stream file from Telegram file server
        stream_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        headers = {}
        range_header = request.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        async with session.get(stream_url, headers=headers) as upstream_resp:
            response = web.StreamResponse(status=upstream_resp.status)
            for k, v in upstream_resp.headers.items():
                if k.lower() in ["content-type", "content-length", "content-range", "accept-ranges"]:
                    response.headers[k] = v

            response.headers["Content-Disposition"] = f'attachment; filename="{file_name}"'
            response.headers["Accept-Ranges"] = "bytes"
            await response.prepare(request)

            # Stream chunks (64KB each for minimal RAM footprint)
            async for chunk in upstream_resp.content.iter_chunked(65536):
                await response.write(chunk)

            await response.write_eof()
            await db.increment_download_count(token)
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
