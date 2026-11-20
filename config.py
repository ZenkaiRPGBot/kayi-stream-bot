import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BOT_START_TIME = datetime.now(timezone.utc)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "986380678"))
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID", "-1004495645007").strip()

BRAND_NAME = "Kayi Stream"
BOT_USERNAME = "@KayiStreamBot"
CHANNEL_USERNAME = "@KayiBots"

# Public URL for stream & download links (e.g. https://kayi-stream-bot.onrender.com)
SERVER_URL = (os.getenv("SERVER_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8080").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
PING_URL = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")

# Link expiration (in hours)
LINK_EXPIRY_HOURS = 24
RATE_LIMIT_FILES_PER_MINUTE = 5
