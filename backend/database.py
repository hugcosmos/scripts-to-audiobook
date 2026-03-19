#!/usr/bin/env python3
"""
SQLite Database Setup for Scripts to Audiobook
Uses aiosqlite for async operations.
"""
import aiosqlite
import json
import time
import uuid
from pathlib import Path
from typing import Optional, Any
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "library.db"

# SQL to create tables
CREATE_TABLES_SQL = """
-- Albums table
CREATE TABLE IF NOT EXISTS albums (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    cover_image TEXT,
    created_at INTEGER,
    updated_at INTEGER
);

-- Audio files table
CREATE TABLE IF NOT EXISTS audio_files (
    id TEXT PRIMARY KEY,
    album_id TEXT REFERENCES albums(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    project_id TEXT NOT NULL,
    duration_ms INTEGER,
    segment_count INTEGER,
    file_path TEXT NOT NULL,
    timeline_path TEXT,
    srt_path TEXT,
    script_text TEXT,
    characters_json TEXT,
    created_at INTEGER
);

-- TTS Provider credentials table
CREATE TABLE IF NOT EXISTS tts_credentials (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL UNIQUE,
    api_key TEXT,
    api_secret TEXT,
    app_id TEXT,
    is_active INTEGER DEFAULT 1,
    created_at INTEGER
);

-- App settings table
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at INTEGER
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_audio_files_album_id ON audio_files(album_id);
CREATE INDEX IF NOT EXISTS idx_audio_files_project_id ON audio_files(project_id);
CREATE INDEX IF NOT EXISTS idx_tts_credentials_provider ON tts_credentials(provider);
"""


async def init_db():
    """Initialize the database and create tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()


async def get_db():
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# ─── Album Operations ────────────────────────────────────────────────────────

async def create_album(
    id: str,
    name: str,
    description: Optional[str] = None,
    cover_image: Optional[str] = None
) -> dict:
    """Create a new album."""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO albums (id, name, description, cover_image, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id, name, description, cover_image, now, now)
        )
        await db.commit()
    return {
        "id": id,
        "name": name,
        "description": description,
        "cover_image": cover_image,
        "created_at": now,
        "updated_at": now
    }


async def get_albums() -> list[dict]:
    """Get all albums with audio file counts."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT a.*, COUNT(af.id) as audio_count
               FROM albums a
               LEFT JOIN audio_files af ON a.id = af.album_id
               GROUP BY a.id
               ORDER BY a.updated_at DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_album(album_id: str) -> Optional[dict]:
    """Get a single album by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT a.*, COUNT(af.id) as audio_count
               FROM albums a
               LEFT JOIN audio_files af ON a.id = af.album_id
               WHERE a.id = ?
               GROUP BY a.id""",
            (album_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_album(
    album_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cover_image: Optional[str] = None
) -> Optional[dict]:
    """Update an album."""
    now = int(time.time())
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if cover_image is not None:
        updates.append("cover_image = ?")
        params.append(cover_image)

    if not updates:
        return await get_album(album_id)

    updates.append("updated_at = ?")
    params.append(now)
    params.append(album_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE albums SET {', '.join(updates)} WHERE id = ?",
            params
        )
        await db.commit()

    return await get_album(album_id)


async def delete_album(album_id: str) -> bool:
    """Delete an album (audio files will have album_id set to NULL)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        await db.commit()
        return cursor.rowcount > 0


# ─── Audio File Operations ───────────────────────────────────────────────────

async def create_audio_file(
    id: str,
    title: str,
    project_id: str,
    file_path: str,
    duration_ms: Optional[int] = None,
    segment_count: Optional[int] = None,
    timeline_path: Optional[str] = None,
    srt_path: Optional[str] = None,
    album_id: Optional[str] = None,
    script_text: Optional[str] = None,
    characters: Optional[list] = None
) -> dict:
    """Create a new audio file record."""
    now = int(time.time())
    characters_json = json.dumps(characters, ensure_ascii=False) if characters else None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO audio_files
               (id, album_id, title, project_id, duration_ms, segment_count,
                file_path, timeline_path, srt_path, script_text, characters_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (id, album_id, title, project_id, duration_ms, segment_count,
             file_path, timeline_path, srt_path, script_text, characters_json, now)
        )
        await db.commit()

    return {
        "id": id,
        "album_id": album_id,
        "title": title,
        "project_id": project_id,
        "duration_ms": duration_ms,
        "segment_count": segment_count,
        "file_path": file_path,
        "timeline_path": timeline_path,
        "srt_path": srt_path,
        "script_text": script_text,
        "characters": characters,
        "created_at": now
    }


async def get_audio_files(album_id: Optional[str] = None) -> list[dict]:
    """Get all audio files, optionally filtered by album."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if album_id:
            cursor = await db.execute(
                """SELECT * FROM audio_files WHERE album_id = ? ORDER BY created_at DESC""",
                (album_id,)
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM audio_files ORDER BY created_at DESC"""
            )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("characters_json"):
                d["characters"] = json.loads(d["characters_json"])
                del d["characters_json"]
            else:
                d["characters"] = None
                if "characters_json" in d:
                    del d["characters_json"]
            result.append(d)
        return result


async def get_audio_file(audio_id: str) -> Optional[dict]:
    """Get a single audio file by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM audio_files WHERE id = ?",
            (audio_id,)
        )
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            if d.get("characters_json"):
                d["characters"] = json.loads(d["characters_json"])
                del d["characters_json"]
            else:
                d["characters"] = None
                if "characters_json" in d:
                    del d["characters_json"]
            return d
        return None


async def update_audio_file_album(audio_id: str, album_id: Optional[str]) -> Optional[dict]:
    """Move an audio file to a different album."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE audio_files SET album_id = ? WHERE id = ?",
            (album_id, audio_id)
        )
        await db.commit()
    return await get_audio_file(audio_id)


async def delete_audio_file(audio_id: str) -> bool:
    """Delete an audio file record."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM audio_files WHERE id = ?", (audio_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_audio_file(audio_id: str, title: Optional[str] = None) -> Optional[dict]:
    """Update an audio file record."""
    updates = []
    params = []

    if title is not None:
        updates.append("title = ?")
        params.append(title)

    if not updates:
        return await get_audio_file(audio_id)

    params.append(audio_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE audio_files SET {', '.join(updates)} WHERE id = ?",
            params
        )
        await db.commit()

    return await get_audio_file(audio_id)


# ─── TTS Credentials Operations ──────────────────────────────────────────────

async def save_tts_credentials(
    provider: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    app_id: Optional[str] = None
) -> dict:
    """Save TTS provider credentials."""
    import uuid
    now = int(time.time())

    async with aiosqlite.connect(DB_PATH) as db:
        # Check if credentials exist for this provider
        cursor = await db.execute(
            "SELECT id FROM tts_credentials WHERE provider = ?",
            (provider,)
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """UPDATE tts_credentials
                   SET api_key = ?, api_secret = ?, app_id = ?, is_active = 1
                   WHERE provider = ?""",
                (api_key, api_secret, app_id, provider)
            )
        else:
            cred_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO tts_credentials (id, provider, api_key, api_secret, app_id, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (cred_id, provider, api_key, api_secret, app_id, now)
            )
        await db.commit()

    return await get_tts_credentials(provider)


async def get_tts_credentials(provider: str) -> Optional[dict]:
    """Get credentials for a specific provider (keys are masked)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tts_credentials WHERE provider = ?",
            (provider,)
        )
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            # Mask sensitive data
            if d.get("api_key"):
                d["api_key_masked"] = d["api_key"][:4] + "****" if len(d["api_key"]) > 4 else "****"
                del d["api_key"]
            if d.get("api_secret"):
                d["api_secret_masked"] = d["api_secret"][:4] + "****" if len(d["api_secret"]) > 4 else "****"
                del d["api_secret"]
            return d
        return None


async def get_all_tts_credentials() -> list[dict]:
    """Get all TTS credentials (keys are masked)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tts_credentials WHERE is_active = 1")
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("api_key"):
                d["api_key_masked"] = d["api_key"][:4] + "****" if len(d["api_key"]) > 4 else "****"
                del d["api_key"]
            if d.get("api_secret"):
                d["api_secret_masked"] = d["api_secret"][:4] + "****" if len(d["api_secret"]) > 4 else "****"
                del d["api_secret"]
            result.append(d)
        return result


async def get_raw_tts_credentials(provider: str) -> Optional[dict]:
    """Get raw credentials for a specific provider (for internal use).
    
    DEPRECATED: This function is kept for backward compatibility.
    Use the implementation in main.py instead.
    """
    # This is a placeholder - the actual implementation is in main.py
    # Import it from there to avoid circular imports
    return None


async def delete_tts_credentials(provider: str) -> bool:
    """Delete credentials for a provider."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tts_credentials WHERE provider = ?",
            (provider,)
        )
        await db.commit()
        return cursor.rowcount > 0


# ─── App Settings Operations ─────────────────────────────────────────────────

async def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except:
                return row["value"]
        return default


async def set_setting(key: str, value: Any) -> None:
    """Set a setting value."""
    now = int(time.time())
    value_json = json.dumps(value) if not isinstance(value, str) else value

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?""",
            (key, value_json, now, value_json, now)
        )
        await db.commit()


async def get_all_settings() -> dict:
    """Get all settings."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT key, value FROM app_settings")
        rows = await cursor.fetchall()
        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except:
                result[row["key"]] = row["value"]
        return result


# Initialize database on module load
async def ensure_db_initialized():
    """Ensure database is initialized."""
    await init_db()
