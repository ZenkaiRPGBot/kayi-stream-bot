---
title: Kayi Stream
emoji: 🎬
colorFrom: red
colorTo: slate
sdk: docker
app_port: 7860
---

# Kayi Stream — File to Link & Streaming Player

A minimal, high-performance Telegram File-to-Link bot and streaming media player with multi-audio and subtitle track selection. Part of the **@KayiBots** umbrella.

---

## 1. Prerequisites & FFmpeg Installation

Kayi Stream uses `ffmpeg` and `ffprobe` for media track detection, subtitle extraction (VTT), and multi-rendition HLS generation.

### Windows
```powershell
winget install Gyan.FFmpeg
```
*(Verify by running `ffmpeg -version` and `ffprobe -version` in your terminal).*

### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install -y ffmpeg
```

### macOS
```bash
brew install ffmpeg
```

---

## 2. Environment Variables

Create a `.env` file in the project root:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | `123456789:ABCdef...` |
| `API_ID` | Telegram API ID from my.telegram.org | `8447214` |
| `API_HASH` | Telegram API Hash from my.telegram.org | `9ec5782ddd...` |
| `OWNER_ID` | Telegram user ID of the bot owner | `986380678` |
| `LOG_CHANNEL_ID` | Telegram Channel ID for generation logs | `-1004495645007` |
| `PORT` | Streaming server HTTP port | `8081` |
| `SERVER_URL` | Public URL (or Cloudflare tunnel URL) | `https://your-domain.com` |
| `PING_URL` | Self-ping keepalive target URL | `https://your-domain.com/health` |

---

## 3. Architecture & Features

* **Track Detection (`GET /api/media/:id/tracks`):** Probes audio tracks, subtitle streams, and video metadata.
* **Dual Playback Engine:**
  * **Direct Mode:** Direct stream with HTTP Range seeking for MP4/WebM with browser-compatible codecs.
  * **HLS Mode:** Multi-audio HLS generation with `hls.js` for MKV, non-browser audio codecs, and multiple audio tracks.
* **On-Demand Subtitles (`GET /api/media/:id/subs/:index.vtt`):** Text subtitles (ASS, SSA, SRT) are dynamically extracted to WebVTT.
* **Apple-Inspired Design:** Minimal, bright `#FFFFFF` interface with `#0A84FF` accents, custom keyboard-navigable settings menu, and external player launchers (VLC, MX Player, PotPlayer).
* **Telegram Native Rich Messages:** Native `<table bordered striped>`, full-width file name headings, and emoji-free styled buttons.
