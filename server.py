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
<meta name="theme-color" content="#F4F6FC">
<title>{BRAND_NAME}</title>
<style>
:root{{
  --canvas:#F4F6FC; --surface:#FFFFFF; --ink:#0E1426; --muted:#5A6480;
  --blue:#2D6BFF; --violet:#8B5CF6; --pink:#FF4D8D; --green:#00C27A; --line:#E4E9F4;
  --radius:22px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  background:var(--canvas);color:var(--ink);min-height:100vh;
  display:flex;align-items:center;justify-content:center;padding:24px;
}}
.card{{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:36px 32px;max-width:480px;width:100%;text-align:center;
  box-shadow:0 14px 30px -20px rgba(14,20,38,.25);
}}
.logo{{
  width:44px;height:44px;border-radius:12px;margin:0 auto 16px;display:grid;place-items:center;
  color:#fff;font-weight:900;font-size:20px;
  background:linear-gradient(135deg,var(--blue),var(--violet));
  box-shadow:0 8px 20px -6px var(--blue);
}}
h1{{font-size:24px;font-weight:800;letter-spacing:-.02em;margin-bottom:8px}}
p{{color:var(--muted);font-size:14px;line-height:1.6;margin-bottom:24px}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:24px}}
.stat{{background:var(--canvas);border:1px solid var(--line);border-radius:14px;padding:12px 8px}}
.stat-num{{font-size:18px;font-weight:800;color:var(--blue)}}
.stat-lbl{{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;margin-top:2px}}
.btn{{
  display:flex;align-items:center;justify-content:center;gap:8px;width:100%;
  padding:14px;border:0;border-radius:14px;cursor:pointer;
  font-family:inherit;font-size:15px;font-weight:700;text-decoration:none;
  color:#fff;background:var(--blue);
  box-shadow:0 10px 24px -10px var(--blue);
  transition:transform .12s ease;
}}
.btn:active{{transform:scale(.98)}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">K</div>
  <h1>{BRAND_NAME}</h1>
  <p>Direct Telegram file downloads and high-speed web playback. Fast, minimal, and responsive.</p>
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
  <a href="https://t.me/{CHANNEL_USERNAME.lstrip('@')}" class="btn">Open in Telegram</a>
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
            text="""<!DOCTYPE html><html><body style="background:#F4F6FC;color:#0E1426;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;padding:24px;"><h1>Link expired or not found</h1><p style="color:#5A6480;margin-top:8px;">This link has expired or has been removed.</p></div></body></html>""",
            content_type="text/html",
            status=404
        )

    f_id = record["id"]
    token = record["token"]
    file_name = record["file_name"]
    file_size = record["file_size"]
    file_size_fmt = format_file_size(file_size)
    mime_type = record.get("mime_type") or "application/octet-stream"
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    fmt_label = ext.upper() if ext else "FILE"
    quality_label = detect_quality_tag(file_name, file_size)

    server_base = get_server_url()
    stream_url = f"{server_base}/stream/{token}"
    dl_url = f"{server_base}/dl/{token}"

    file_data_json = json.dumps({
        "id": f_id,
        "name": file_name,
        "size": file_size_fmt,
        "format": fmt_label,
        "quality": quality_label,
        "stream": stream_url,
        "download": dl_url
    })

    # Bright Stage Player HTML exactly following Claude UI/UX specification
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#F4F6FC">
<title>{file_name} · {BRAND_NAME}</title>
<style>
:root{{
  --canvas:#F4F6FC; --surface:#FFFFFF; --ink:#0E1426; --muted:#5A6480;
  --blue:#2D6BFF; --violet:#8B5CF6; --pink:#FF4D8D; --green:#00C27A; --line:#E4E9F4;
  --radius:22px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{-webkit-text-size-adjust:100%}}
body{{
  font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  background:var(--canvas);color:var(--ink);min-height:100vh;
  line-height:1.5;-webkit-font-smoothing:antialiased;
  padding-bottom:env(safe-area-inset-bottom,0px);
}}

/* ---------- Header ---------- */
.top{{
  position:sticky;top:0;z-index:20;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:env(safe-area-inset-top,0px) 20px 0;height:calc(60px + env(safe-area-inset-top,0px));
  background:rgba(255,255,255,.82);backdrop-filter:saturate(180%) blur(14px);
  -webkit-backdrop-filter:saturate(180%) blur(14px);
  border-bottom:1px solid var(--line);
}}
.brand{{display:flex;align-items:center;gap:10px;font-weight:800;font-size:17px;letter-spacing:-.02em}}
.logo{{
  width:32px;height:32px;border-radius:10px;display:grid;place-items:center;
  color:#fff;font-weight:900;font-size:16px;
  background:linear-gradient(135deg,var(--blue),var(--violet));
  box-shadow:0 6px 16px -6px var(--blue);
}}
.chip{{
  font-size:12px;font-weight:700;color:var(--blue);
  background:#EAF0FF;padding:6px 12px;border-radius:999px;white-space:nowrap;
}}

/* ---------- Hero ---------- */
.hero{{position:relative;isolation:isolate;padding:28px 16px 0}}
.hero::before{{
  content:"";position:absolute;inset:-40px 0 auto;height:420px;z-index:-1;
  background:
    radial-gradient(60% 70% at 15% 20%,rgba(45,107,255,.35),transparent 70%),
    radial-gradient(55% 65% at 85% 10%,rgba(139,92,246,.32),transparent 70%),
    radial-gradient(50% 60% at 50% 60%,rgba(255,77,141,.18),transparent 70%);
  filter:blur(10px);
}}
.wrap{{max-width:1120px;margin:0 auto}}

.stage{{
  position:relative;aspect-ratio:16/9;border-radius:var(--radius);overflow:hidden;
  background:#05070F;
  box-shadow:0 30px 60px -28px rgba(45,107,255,.55),0 0 0 1px rgba(14,20,38,.06);
}}
video{{width:100%;height:100%;display:block;background:#05070F}}

/* loading skeleton */
.stage.loading::after{{
  content:"";position:absolute;inset:0;
  background:linear-gradient(110deg,#0c1224 30%,#18223d 50%,#0c1224 70%);
  background-size:220% 100%;animation:shine 1.4s linear infinite;pointer-events:none;
}}
.stage.ready::after{{display:none}}
@keyframes shine{{to{{background-position:-220% 0}}}}

/* ---------- Content grid ---------- */
.content{{
  display:grid;gap:18px;padding:22px 16px 60px;
  grid-template-columns:1fr;
}}
@media(min-width:900px){{
  .content{{grid-template-columns:minmax(0,1fr) 360px;padding:26px 0 70px;gap:24px}}
}}
.wrap.grid{{padding:0}}

.info{{padding:4px 2px}}
h1{{
  font-size:clamp(20px,2.8vw,30px);font-weight:800;letter-spacing:-.025em;line-height:1.2;
  overflow-wrap:anywhere;
}}
.facts{{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}}
.fact{{
  font-size:13px;font-weight:700;padding:6px 12px;border-radius:10px;
  background:var(--surface);border:1px solid var(--line);color:var(--ink);
}}
.fact.quality{{
  color:#fff;border:0;
  background:linear-gradient(135deg,var(--pink),var(--violet));
}}
.note{{margin-top:16px;font-size:14px;color:var(--muted);max-width:60ch}}

/* ---------- Action panel ---------- */
.panel{{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;box-shadow:0 14px 30px -22px rgba(14,20,38,.25);
}}
.panel h2{{font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:18px 0 10px}}
.panel h2:first-child{{margin-top:0}}

.btn{{
  display:flex;align-items:center;justify-content:center;gap:8px;width:100%;
  padding:15px 16px;border:0;border-radius:14px;cursor:pointer;
  font-family:inherit;font-size:15px;font-weight:700;line-height:1;text-decoration:none;
  transition:transform .12s ease,box-shadow .2s ease,background .2s ease;
}}
.btn:active{{transform:scale(.97)}}
.btn-download{{
  color:#fff;background:var(--green);
  box-shadow:0 14px 28px -14px var(--green);
}}
.btn-download:hover{{box-shadow:0 18px 32px -14px var(--green)}}

.apps{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.app{{
  display:flex;align-items:center;gap:10px;padding:12px;
  background:var(--canvas);border:1px solid var(--line);border-radius:14px;
  color:var(--ink);font-family:inherit;font-size:14px;font-weight:700;cursor:pointer;
  transition:border-color .2s,transform .12s;text-align:left;
}}
.app:hover{{border-color:var(--blue)}}
.app:active{{transform:scale(.97)}}
.app .ico{{
  width:32px;height:32px;border-radius:9px;display:grid;place-items:center;flex:none;
  color:#fff;font-weight:900;font-size:14px;background:var(--c);
}}
.app.highlight{{border-color:var(--pink);box-shadow:0 0 0 4px rgba(255,77,141,.15)}}

.copy{{
  margin-top:10px;width:100%;padding:13px;border-radius:14px;
  background:transparent;border:1px dashed #C8D1E6;color:var(--muted);
  font-family:inherit;font-size:14px;font-weight:700;cursor:pointer;
}}
.copy:hover{{color:var(--blue);border-color:var(--blue)}}

.help{{margin-top:14px;font-size:13px;color:var(--muted)}}

/* ---------- Bottom sheet (mobile external players) ---------- */
.scrim{{
  position:fixed;inset:0;background:rgba(14,20,38,.35);opacity:0;pointer-events:none;
  transition:opacity .25s;z-index:40;
}}
.sheet{{
  position:fixed;left:0;right:0;bottom:0;z-index:41;background:var(--surface);
  border-radius:24px 24px 0 0;padding:14px 20px calc(20px + env(safe-area-inset-bottom,0px));
  transform:translateY(105%);transition:transform .3s cubic-bezier(.2,.8,.2,1);
  box-shadow:0 -20px 40px -20px rgba(14,20,38,.35);
}}
.sheet .grab{{width:44px;height:5px;border-radius:99px;background:var(--line);margin:0 auto 14px}}
.sheet h3{{font-size:17px;font-weight:800;margin-bottom:4px}}
.sheet p{{font-size:14px;color:var(--muted);margin-bottom:14px}}
.sheet .apps{{grid-template-columns:1fr 1fr 1fr}}
.sheet .app{{flex-direction:column;text-align:center;padding:14px 8px}}
.open .scrim{{opacity:1;pointer-events:auto}}
.open .sheet{{transform:translateY(0)}}

/* ---------- Toast ---------- */
.toast{{
  position:fixed;left:50%;bottom:calc(24px + env(safe-area-inset-bottom,0px));
  transform:translate(-50%,160px);background:var(--ink);color:#fff;
  padding:12px 18px;border-radius:14px;font-size:14px;font-weight:600;
  transition:transform .35s cubic-bezier(.2,.8,.2,1);z-index:60;white-space:nowrap;
  box-shadow:0 14px 30px -12px rgba(14,20,38,.6);
}}
.toast.show{{transform:translate(-50%,0)}}
</style>
</head>
<body>

<header class="top">
  <div class="brand"><div class="logo">K</div>Kayi Stream</div>
  <div class="chip" id="chip"></div>
</header>

<section class="hero">
  <div class="wrap">
    <div class="stage loading" id="stage">
      <video id="player" controls playsinline preload="metadata"></video>
    </div>
  </div>
</section>

<main class="wrap content">
  <div class="info">
    <h1 id="title"></h1>
    <div class="facts">
      <span class="fact" id="size"></span>
      <span class="fact" id="format"></span>
      <span class="fact quality" id="quality"></span>
    </div>
    <p class="note" id="note">Playing in your browser. If the video doesn't start, open it in a dedicated player.</p>
  </div>

  <aside class="panel">
    <h2>Download</h2>
    <a class="btn btn-download" id="dl" href="#">Download file</a>

    <h2>Open in</h2>
    <div class="apps">
      <button class="app" data-app="vlc"><span class="ico" style="--c:#FF7A00">V</span>VLC</button>
      <button class="app" data-app="mx"><span class="ico" style="--c:#7C3AED">M</span>MX Player</button>
      <button class="app" data-app="pot"><span class="ico" style="--c:#F59E0B">P</span>PotPlayer</button>
      <button class="app" data-app="more"><span class="ico" style="--c:#2D6BFF">+</span>More</button>
    </div>
    <button class="copy" id="copy">Copy link</button>
    <p class="help" id="help">Works best in VLC, MX Player, or PotPlayer for MKV files with multiple audio or subtitle tracks.</p>
  </aside>
</main>

<div class="scrim" id="scrim"></div>
<div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-labelledby="sheetTitle">
  <div class="grab"></div>
  <h3 id="sheetTitle">Open in a player</h3>
  <p>Choose a player to play this file with full audio and subtitle support.</p>
  <div class="apps">
    <button class="app" data-app="vlc"><span class="ico" style="--c:#FF7A00">V</span>VLC</button>
    <button class="app" data-app="mx"><span class="ico" style="--c:#7C3AED">M</span>MX Player</button>
    <button class="app" data-app="pot"><span class="ico" style="--c:#F59E0B">P</span>PotPlayer</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
/* Injected by the server for each file */
const F = {file_data_json};

const $ = id => document.getElementById(id);
const abs = new URL(F.stream, location.href).href;
const isAndroid = /Android/i.test(navigator.userAgent);
const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);

/* Fill the page */
$("title").textContent = F.name;
$("size").textContent = F.size;
$("format").textContent = F.format;
$("quality").textContent = F.quality;
$("chip").textContent = "ID " + F.id;
$("dl").href = F.download;
document.title = F.name + " · Kayi Stream";
$("player").src = F.stream;

/* Loading and ready states */
const player = $("player");
player.addEventListener("loadeddata", () => $("stage").classList.replace("loading", "ready"));

/* Friendly fallback when the browser can't decode the file */
player.addEventListener("error", () => {{
  $("stage").classList.replace("loading", "ready");
  $("note").textContent = "This file won't play in the browser. Open it in VLC or MX Player below.";
  document.querySelectorAll('.app[data-app="vlc"], .app[data-app="mx"]').forEach(b => b.classList.add("highlight"));
  if (isMobile) openSheet();
}});

/* Toast */
function toast(msg){{
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 2200);
}}

/* Bottom sheet */
function openSheet(){{ document.body.classList.add("open"); }}
function closeSheet(){{ document.body.classList.remove("open"); }}
$("scrim").addEventListener("click", closeSheet);

/* External players */
function intentFor(pkg){{
  return `intent:${{abs}}#Intent;package=${{pkg}};type=video/*;S.title=${{encodeURIComponent(F.name)}};end`;
}}
function copyLink(message = "Link copied"){{
  navigator.clipboard.writeText(abs).then(() => toast(message)).catch(() => toast("Could not copy link"));
}}
function openExternal(app){{
  if(app === "more"){{ openSheet(); return; }}
  let target = null;
  if(app === "vlc") target = isAndroid ? intentFor("org.videolan.vlc") : "vlc://" + abs;
  if(app === "pot") target = "potplayer://" + abs;
  if(app === "mx" && isAndroid) target = intentFor("com.mxtech.videoplayer.ad");

  if(!target){{
    closeSheet();
    copyLink("Paste this link into your player");
    return;
  }}
  closeSheet();
  location.href = target;
}}

document.querySelectorAll("[data-app]").forEach(b =>
  b.addEventListener("click", () => openExternal(b.dataset.app))
);
$("copy").addEventListener("click", () => copyLink());
</script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")

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

                await response.write(chunk)
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
