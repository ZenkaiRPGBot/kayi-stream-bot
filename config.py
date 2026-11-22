import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# Indian Standard Time (UTC + 05:30)
IST = timezone(timedelta(hours=5, minutes=30))
BOT_START_TIME = datetime.now(IST)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "986380678"))
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID", "-1004495645007").strip()
API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()

BRAND_NAME = "Kayi File to Link"
BOT_USERNAME = os.getenv("BOT_USERNAME", "@KayiStreamBot")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@KayiBots")
COMMUNITY_URL = "https://t.me/KayiBots"
DEVELOPER_URL = "https://t.me/qouba"

# Cinematic Welcome Configuration
WELCOME_VIDEO_FILE_ID = os.getenv(
    "WELCOME_VIDEO_FILE_ID",
    "BAACAgUAAxkDAAO9awK8jBvrPXT7iBp-PYFg_tDIScIAAhEnAAJE7hBU5s5fTjKr_OU9BA"
).strip()

# Mandatory Channel Subscription (FSub)
FSUB_CHANNEL = os.getenv("FSUB_CHANNEL", "@KayiBots").strip()
FSUB_CHANNEL_URL = os.getenv("FSUB_CHANNEL_URL", COMMUNITY_URL).strip()
FSUB_CACHE_TTL = int(os.getenv("FSUB_CACHE_TTL", "45"))
FSUB_TIMEOUT = float(os.getenv("FSUB_TIMEOUT", "5.0"))

def get_server_url() -> str:
    # 1. Custom SERVER_URL if not localhost
    custom = os.getenv("SERVER_URL")
    if custom and "localhost" not in custom and "127.0.0.1" not in custom:
        return custom.rstrip("/")
    # 2. Hugging Face Spaces auto URL
    space_host = os.getenv("SPACE_HOST")
    if space_host:
        return f"https://{space_host}".rstrip("/")
    # 3. Render auto URL
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url.rstrip("/")
    # 4. Local cloudflared tunnel
    tunnel_file = os.path.join(os.path.dirname(__file__), "tunnel_url.txt")
    if os.path.exists(tunnel_file):
        try:
            with open(tunnel_file, "r") as f:
                t_url = f.read().strip()
                if t_url.startswith("http"):
                    return t_url.rstrip("/")
        except Exception:
            pass
    return (os.getenv("SERVER_URL") or "http://localhost:7860").rstrip("/")

SERVER_URL = get_server_url()
PORT = int(os.getenv("PORT", "7860"))
PING_URL = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")
if not PING_URL and os.getenv("SPACE_HOST"):
    PING_URL = f"https://{os.getenv('SPACE_HOST')}"

# Link expiration (in hours)
LINK_EXPIRY_HOURS = 24
RATE_LIMIT_FILES_PER_MINUTE = 5
