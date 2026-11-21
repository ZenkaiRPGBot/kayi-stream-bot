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
COMMUNITY_URL = os.getenv("COMMUNITY_URL", "https://t.me/kayitv")

def get_server_url() -> str:
    # 1. Custom SERVER_URL if not localhost
    custom = os.getenv("SERVER_URL")
    if custom and "localhost" not in custom and "127.0.0.1" not in custom:
        return custom.rstrip("/")
    # 2. Render auto URL
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url.rstrip("/")
    # 3. Local cloudflared tunnel
    tunnel_file = os.path.join(os.path.dirname(__file__), "tunnel_url.txt")
    if os.path.exists(tunnel_file):
        try:
            with open(tunnel_file, "r") as f:
                t_url = f.read().strip()
                if t_url.startswith("http"):
                    return t_url.rstrip("/")
        except Exception:
            pass
    return (os.getenv("SERVER_URL") or "http://localhost:8081").rstrip("/")

SERVER_URL = get_server_url()
PORT = int(os.getenv("PORT", "8081"))
PING_URL = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")

# Link expiration (in hours)
LINK_EXPIRY_HOURS = 24
RATE_LIMIT_FILES_PER_MINUTE = 5
