import aiosqlite
import os
from datetime import datetime, timezone, timedelta
from config import LINK_EXPIRY_HOURS, IST

DB_PATH = os.path.join(os.path.dirname(__file__), "stream.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if id column exists
        cur = await db.execute("PRAGMA table_info(files)")
        cols = [c[1] for c in await cur.fetchall()]
        if cols and "id" not in cols:
            await db.execute("DROP TABLE IF EXISTS files")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE,
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
        # Indexes for ultra-fast deduplication & user lookups
        await db.execute("CREATE INDEX IF NOT EXISTS idx_files_unique_id ON files (file_unique_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_files_user ON files (user_id, id DESC);")
        await db.commit()

async def find_file_by_unique_id(file_unique_id: str) -> dict | None:
    """Checks if exact same file is already registered and active (deduplication cache)."""
    if not file_unique_id:
        return None
    now_iso = datetime.now(IST).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM files 
            WHERE file_unique_id = ? AND expires_at > ?
            ORDER BY id DESC LIMIT 1
        """, (file_unique_id, now_iso)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def save_file_record(token: str, user_id: int, file_id: str, file_unique_id: str,
                           file_name: str, file_size: int, mime_type: str) -> dict:
    now = datetime.now(IST)
    expires = now + timedelta(hours=LINK_EXPIRY_HOURS)
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO files (token, user_id, file_id, file_unique_id, file_name, file_size, mime_type, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (token, user_id, file_id, file_unique_id, file_name, file_size, mime_type, now.isoformat(), expires.isoformat()))
        file_db_id = cursor.lastrowid
        
        # Track activity for rate limiting
        await db.execute("INSERT INTO user_activity (user_id, uploaded_at) VALUES (?, ?)", (user_id, now.isoformat()))
        await db.commit()
        
    return {
        "id": file_db_id,
        "token": token,
        "file_name": file_name,
        "file_size": file_size,
        "expires_at": expires.isoformat()
    }

async def get_file_record(token: str) -> dict | None:
    now = datetime.now(IST)
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

async def get_file_by_id_or_token(identifier: str | int) -> dict | None:
    now = datetime.now(IST)
    clean_id = str(identifier).strip().lstrip("#")
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = None
        if clean_id.isdigit():
            async with db.execute("SELECT * FROM files WHERE id = ?", (int(clean_id),)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            async with db.execute("SELECT * FROM files WHERE token = ?", (str(identifier).strip(),)) as cursor:
                row = await cursor.fetchone()

        if not row:
            return None
        return dict(row)

async def increment_download_count(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE files SET download_count = download_count + 1 WHERE token = ?", (token,))
        await db.commit()

async def delete_file_record(token: str, user_id: int = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id:
            res = await db.execute("DELETE FROM files WHERE token = ? AND user_id = ?", (token, user_id))
        else:
            res = await db.execute("DELETE FROM files WHERE token = ?", (token,))
        await db.commit()
        return res.rowcount > 0

async def delete_file_by_id_or_token(identifier: str | int, user_id: int | None = None) -> bool:
    clean_id = str(identifier).strip().lstrip("#")
    async with aiosqlite.connect(DB_PATH) as db:
        if clean_id.isdigit():
            if user_id:
                res = await db.execute("DELETE FROM files WHERE id = ? AND user_id = ?", (int(clean_id), user_id))
            else:
                res = await db.execute("DELETE FROM files WHERE id = ?", (int(clean_id),))
        else:
            if user_id:
                res = await db.execute("DELETE FROM files WHERE token = ? AND user_id = ?", (str(identifier).strip(), user_id))
            else:
                res = await db.execute("DELETE FROM files WHERE token = ?", (str(identifier).strip(),))
        await db.commit()
        return res.rowcount > 0

async def get_active_files(user_id: int | None = None, page: int = 1, page_size: int = 8) -> tuple[list[dict], int]:
    now = datetime.now(IST)
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if user_id:
            count_cur = await db.execute("SELECT COUNT(*) FROM files WHERE user_id = ? AND expires_at > ?", (user_id, now.isoformat()))
            total = (await count_cur.fetchone())[0]
            cur = await db.execute(
                "SELECT * FROM files WHERE user_id = ? AND expires_at > ? ORDER BY id ASC LIMIT ? OFFSET ?",
                (user_id, now.isoformat(), page_size, offset)
            )
        else:
            count_cur = await db.execute("SELECT COUNT(*) FROM files WHERE expires_at > ?", (now.isoformat(),))
            total = (await count_cur.fetchone())[0]
            cur = await db.execute(
                "SELECT * FROM files WHERE expires_at > ? ORDER BY id ASC LIMIT ? OFFSET ?",
                (now.isoformat(), page_size, offset)
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows], total

async def get_user_files(user_id: int, limit: int = 10) -> list[dict]:
    now = datetime.now(IST)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM files WHERE user_id = ? AND expires_at > ? ORDER BY id ASC LIMIT ?",
            (user_id, now.isoformat(), limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_global_stats() -> dict:
    now = datetime.now(IST)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), COALESCE(SUM(download_count), 0), COALESCE(SUM(file_size), 0) FROM files") as c1:
            total_files, total_downloads, total_bytes = await c1.fetchone()
            
        async with db.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM files WHERE expires_at > ?", (now.isoformat(),)) as c2:
            active_links, active_bytes = await c2.fetchone()

        return {
            "total_files": total_files or 0,
            "active_links": active_links or 0,
            "active_bytes": active_bytes or 0,
            "total_downloads": total_downloads or 0,
            "total_bytes": total_bytes or 0
        }

async def cleanup_expired_files() -> int:
    now = datetime.now(IST)
    async with aiosqlite.connect(DB_PATH) as db:
        res = await db.execute("DELETE FROM files WHERE expires_at < ?", (now.isoformat(),))
        await db.commit()
        return res.rowcount

async def check_rate_limit(user_id: int, limit: int = 5) -> bool:
    """Returns True if within rate limit, False if rate limited (more than 5 files in last 60 seconds)."""
    now = datetime.now(IST)
    window = now - timedelta(seconds=60)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM user_activity WHERE user_id = ? AND uploaded_at > ?", (user_id, window.isoformat())) as cursor:
            count = (await cursor.fetchone())[0]
            return count < limit
