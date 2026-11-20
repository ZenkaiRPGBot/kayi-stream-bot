import os
import json
import asyncio
import subprocess

CACHE_BASE_DIR = os.path.join(os.path.dirname(__file__), "media_cache")
os.makedirs(CACHE_BASE_DIR, exist_ok=True)

# ISO 639-2 to English name lookup table
LANG_MAP = {
    "eng": "English", "jpn": "Japanese", "hin": "Hindi", "spa": "Spanish",
    "fra": "French", "fre": "French", "deu": "German", "ger": "German",
    "ita": "Italian", "zho": "Chinese", "chi": "Chinese", "kor": "Korean",
    "rus": "Russian", "por": "Portuguese", "ara": "Arabic", "tam": "Tamil",
    "tel": "Telugu", "mal": "Malayalam", "ben": "Bengali", "mar": "Marathi",
    "pan": "Punjabi", "tur": "Turkish", "vie": "Vietnamese", "tha": "Thai",
    "ind": "Indonesian", "pol": "Polish", "nld": "Dutch", "dut": "Dutch",
    "swe": "Swedish", "nor": "Norwegian", "dan": "Danish", "fin": "Finnish",
    "heb": "Hebrew", "ell": "Greek", "gre": "Greek", "ces": "Czech",
    "cze": "Czech", "hun": "Hungarian", "ukr": "Ukrainian", "ron": "Romanian",
    "rum": "Romanian", "lat": "Latin", "und": "Undetermined"
}

TEXT_SUB_CODECS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt"}
IMAGE_SUB_CODECS = {"hdmv_pgs_subtitle", "pgs", "dvd_subtitle", "vobsub", "dvb_subtitle"}

_PROBE_CACHE = {}
_ACTIVE_HLS_TASKS = {}
_ACTIVE_SUB_TASKS = {}

def get_readable_lang(code: str) -> str:
    if not code:
        return ""
    code_lower = code.lower().strip()
    return LANG_MAP.get(code_lower, code_lower.capitalize())

async def probe_file(file_id: int | str, stream_url: str) -> dict:
    file_id_str = str(file_id)
    if file_id_str in _PROBE_CACHE:
        return _PROBE_CACHE[file_id_str]

    cache_file = os.path.join(CACHE_BASE_DIR, file_id_str, "tracks.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _PROBE_CACHE[file_id_str] = data
                return data
        except Exception:
            pass

    cmd = [
        "ffprobe", "-v", "error",
        "-analyzeduration", "10M",
        "-probesize", "10M",
        "-print_format", "json",
        "-show_streams", "-show_format",
        stream_url
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        raw_json = json.loads(stdout.decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"[tracks] ffprobe error on file {file_id}: {e}")
        raw_json = {"streams": [], "format": {}}

    streams = raw_json.get("streams", [])
    format_info = raw_json.get("format", {})

    audio_list = []
    sub_list = []
    video_info = None

    audio_counter = 1
    sub_counter = 1

    for s in streams:
        c_type = s.get("codec_type")
        codec_name = (s.get("codec_name") or "").lower()
        tags = s.get("tags") or {}
        disp = s.get("disposition") or {}
        lang_code = tags.get("language") or ""
        lang_name = get_readable_lang(lang_code)
        title = tags.get("title") or ""

        if c_type == "video" and video_info is None:
            dur = s.get("duration") or format_info.get("duration") or 0
            try:
                dur_float = float(dur)
            except Exception:
                dur_float = 0.0
            video_info = {
                "codec": codec_name,
                "width": s.get("width", 0),
                "height": s.get("height", 0),
                "duration": dur_float
            }
        elif c_type == "audio":
            if not title:
                title = lang_name if lang_name else f"Track {audio_counter}"
            audio_list.append({
                "index": s.get("index"),
                "stream_id": audio_counter - 1,
                "language": lang_code,
                "language_name": lang_name or title,
                "title": title,
                "codec": codec_name,
                "channels": s.get("channels", 2),
                "default": bool(disp.get("default", 0))
            })
            audio_counter += 1
        elif c_type == "subtitle":
            is_supported = (codec_name in TEXT_SUB_CODECS)
            if not title:
                title = lang_name if lang_name else f"Track {sub_counter}"
            sub_list.append({
                "index": s.get("index"),
                "stream_id": sub_counter - 1,
                "language": lang_code,
                "language_name": lang_name or title,
                "title": title,
                "codec": codec_name,
                "forced": bool(disp.get("forced", 0)),
                "default": bool(disp.get("default", 0)),
                "supported": is_supported
            })
            sub_counter += 1

    if not video_info:
        video_info = {"codec": "unknown", "width": 0, "height": 0, "duration": 0.0}

    # Decide playback mode:
    # Direct mode: Single audio MP4/WebM with browser-compatible codecs (h264, vp8, vp9, av1)
    # HLS mode: MKV files, multi-audio files, or anything the browser can't decode natively
    fmt_name = (format_info.get("format_name") or "").lower()
    is_mkv = ("matroska" in fmt_name)
    is_browser_video = (video_info["codec"] in ["h264", "vp8", "vp9", "av1"])
    has_single_audio = (len(audio_list) <= 1)
    has_compatible_audio = False
    if len(audio_list) == 1:
        has_compatible_audio = audio_list[0]["codec"] in ["aac", "mp3", "opus"]
    elif len(audio_list) == 0:
        has_compatible_audio = True

    if (not is_mkv) and is_browser_video and has_single_audio and has_compatible_audio:
        mode = "direct"
    else:
        mode = "hls"

    result = {
        "mode": mode,
        "video": video_info,
        "audio": audio_list,
        "subtitles": sub_list
    }

    # Cache output to disk
    file_dir = os.path.join(CACHE_BASE_DIR, file_id_str)
    os.makedirs(file_dir, exist_ok=True)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass

    _PROBE_CACHE[file_id_str] = result
    return result

async def ensure_hls_generation(file_id: int | str, stream_url: str, tracks_data: dict):
    file_id_str = str(file_id)
    hls_dir = os.path.join(CACHE_BASE_DIR, file_id_str, "hls")
    os.makedirs(hls_dir, exist_ok=True)

    master_pl = os.path.join(hls_dir, "master.m3u8")
    if os.path.exists(master_pl) and os.path.getsize(master_pl) > 0:
        return

    if file_id_str in _ACTIVE_HLS_TASKS and not _ACTIVE_HLS_TASKS[file_id_str].done():
        return

    task = asyncio.create_task(_run_ffmpeg_hls(file_id_str, stream_url, tracks_data, hls_dir))
    _ACTIVE_HLS_TASKS[file_id_str] = task

async def _run_ffmpeg_hls(file_id_str: str, stream_url: str, tracks_data: dict, hls_dir: str):
    video = tracks_data.get("video") or {}
    audio_tracks = tracks_data.get("audio") or []

    v_codec = video.get("codec", "")
    # If video is H.264, copy stream. Otherwise, encode to H.264 ultrafast
    if v_codec in ["h264", "avc", "avc1"]:
        v_args = ["-c:v", "copy"]
    else:
        v_args = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]

    cmd = [
        "ffmpeg", "-y",
        "-analyzeduration", "10M",
        "-probesize", "10M",
        "-i", stream_url,
        "-map", "0:v:0"
    ] + v_args

    if len(audio_tracks) > 1:
        stream_map_parts = ["v:0,agroup:audio"]
        for i, a in enumerate(audio_tracks):
            cmd.extend([
                "-map", f"0:{a['index']}",
                f"-c:a:{i}", "aac", "-ac", "2", f"-b:a:{i}", "160k"
            ])
            lang = a.get("language") or "und"
            title = a.get("title") or a.get("language_name") or f"Audio {i+1}"
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_")
            is_default = "yes" if a.get("default") else "no"
            stream_map_parts.append(f"a:{i},agroup:audio,language:{lang},title:{safe_title},default:{is_default}")

        cmd.extend([
            "-var_stream_map", " ".join(stream_map_parts),
            "-f", "hls",
            "-hls_time", "6",
            "-hls_list_size", "0",
            "-hls_playlist_type", "event",
            "-master_pl_name", "master.m3u8",
            os.path.join(hls_dir, "stream_%v.m3u8")
        ])
    else:
        if audio_tracks:
            cmd.extend([
                "-map", f"0:{audio_tracks[0]['index']}",
                "-c:a", "aac", "-ac", "2", "-b:a", "160k",
                "-var_stream_map", "v:0,a:0",
                "-f", "hls",
                "-hls_time", "6",
                "-hls_list_size", "0",
                "-hls_playlist_type", "event",
                "-master_pl_name", "master.m3u8",
                os.path.join(hls_dir, "stream_%v.m3u8")
            ])
        else:
            cmd.extend([
                "-var_stream_map", "v:0",
                "-f", "hls",
                "-hls_time", "6",
                "-hls_list_size", "0",
                "-hls_playlist_type", "event",
                "-master_pl_name", "master.m3u8",
                os.path.join(hls_dir, "stream_%v.m3u8")
            ])

    print(f"[hls] Starting HLS generation for ID {file_id_str}...")
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        print(f"[hls] HLS generation completed for ID {file_id_str}")
    except Exception as e:
        print(f"[hls] ffmpeg HLS error for ID {file_id_str}: {e}")
        if proc:
            try:
                proc.kill()
            except Exception:
                pass

async def extract_subtitle(file_id: int | str, stream_url: str, stream_index: int) -> str | None:
    file_id_str = str(file_id)
    subs_dir = os.path.join(CACHE_BASE_DIR, file_id_str, "subs")
    os.makedirs(subs_dir, exist_ok=True)

    vtt_path = os.path.join(subs_dir, f"sub_{stream_index}.vtt")
    if os.path.exists(vtt_path) and os.path.getsize(vtt_path) > 0:
        return vtt_path

    task_key = f"{file_id_str}_{stream_index}"
    if task_key in _ACTIVE_SUB_TASKS and not _ACTIVE_SUB_TASKS[task_key].done():
        try:
            await asyncio.wait_for(asyncio.shield(_ACTIVE_SUB_TASKS[task_key]), timeout=15.0)
        except asyncio.TimeoutError:
            pass
        return vtt_path if os.path.exists(vtt_path) else None

    task = asyncio.create_task(_run_ffmpeg_sub(stream_url, stream_index, vtt_path))
    _ACTIVE_SUB_TASKS[task_key] = task
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
    except asyncio.TimeoutError:
        pass

    return vtt_path if (os.path.exists(vtt_path) and os.path.getsize(vtt_path) > 0) else None

async def _run_ffmpeg_sub(stream_url: str, stream_index: int, vtt_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-analyzeduration", "10M",
        "-probesize", "10M",
        "-fflags", "+fastseek",
        "-i", stream_url,
        "-vn", "-an",
        "-map", f"0:{stream_index}",
        "-c:s", "webvtt",
        vtt_path
    ]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await asyncio.wait_for(proc.wait(), timeout=60.0)
    except Exception as e:
        print(f"[sub] Subtitle extraction note on stream {stream_index}: {e}")
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
