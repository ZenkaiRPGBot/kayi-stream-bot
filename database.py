import aiosqlite
import os
from datetime import datetime, timezone, timedelta
from config import LINK_EXPIRY_HOURS

DB_PATH = os.path.join(os.path.dirname(__file__), "stream.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                token TEXT PRIMARY KEY,
                user_id INTEGER,
                file_id TEXT,
                file_unique_id TEXT,
                file_name TEXT,
                file_size INTEGER,
                mime_type TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                download_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_activity (
                user_id INTEGER,
                uploaded_at TIMESTAMP
            )
        """)
        await db.commit()

async def save_file_record(token: str, user_id: int, file_id: str, file_unique_id: str,
                           file_name: str, file_size: int, mime_type: str) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=LINK_EXPIRY_HOURS)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO files (token, user_id, file_id, file_unique_id, file_name, file_size, mime_type, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (token, user_id, file_id, file_unique_id, file_name, file_size, mime_type, now.isoformat(), expires.isoformat()))
        
        # Track activity for rate limiting
        await db.execute("INSERT INTO user_activity (user_id, uploaded_at) VALUES (?, ?)", (user_id, now.isoformat()))
        await db.commit()
        
    return {
        "token": token,
        "file_name": file_name,
        "file_size": file_size,
        "expires_at": expires.isoformat()
    }

async def get_file_record(token: str) -> dict | None:
    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM files WHERE token = ?", (token,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            # Check expiry
            if row["expires_at"]:
                exp_dt = datetime.fromisoformat(row["expires_at"])
                if exp_dt < now:
                    return None
            return dict(row)

async def increment_download_count(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE files SET download_count = download_count + 1 WHERE token = ?", (token,))
        await db.commit()

async def check_rate_limit(user_id: int, limit: int = 5) -> bool:
    """Returns True if within rate limit, False if rate limited (more than 5 files in last 60 seconds)."""
    now = datetime.now(timezone.utc)
    window = now - timedelta(seconds=60)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM user_activity WHERE user_id = ? AND uploaded_at > ?", (user_id, window.isoformat())) as cursor:
            count = (await cursor.fetchone())[0]
            return count < limit
