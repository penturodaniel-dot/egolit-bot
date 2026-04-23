"""
Chat persistence layer.
Tables: chat_sessions, chat_messages, quick_replies
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from db.connection import get_pool

logger = logging.getLogger(__name__)


# ── Init ─────────────────────────────────────────────────────────────────────

async def init_chat_tables() -> None:
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id           SERIAL PRIMARY KEY,
            user_id      BIGINT UNIQUE NOT NULL,
            username     TEXT,
            first_name   TEXT,
            last_name    TEXT,
            photo_url    TEXT,
            status       TEXT NOT NULL DEFAULT 'ai',   -- ai | human | closed
            tag          TEXT,                          -- hot | cold | vip | null
            unread_count INT NOT NULL DEFAULT 0,
            last_message TEXT,
            last_seen_at TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await pool.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id           SERIAL PRIMARY KEY,
            session_id   INT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            user_id      BIGINT NOT NULL,
            direction    TEXT NOT NULL,   -- in | out
            msg_type     TEXT NOT NULL DEFAULT 'text',  -- text | photo | document | sticker
            content      TEXT,
            media_url    TEXT,
            tg_msg_id    INT,
            is_read      BOOLEAN NOT NULL DEFAULT FALSE,
            sent_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session
        ON chat_messages(session_id, sent_at DESC)
    """)

    await pool.execute("""
        CREATE TABLE IF NOT EXISTS quick_replies (
            id         SERIAL PRIMARY KEY,
            title      TEXT NOT NULL,
            content    TEXT NOT NULL,
            position   INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    logger.info("Chat tables ready.")


# ── Sessions ──────────────────────────────────────────────────────────────────

async def upsert_session(
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None = None,
) -> int:
    """Create or update a chat session. Returns session id."""
    pool = await get_pool()
    row = await pool.fetchrow("""
        INSERT INTO chat_sessions (user_id, username, first_name, last_name)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO UPDATE
            SET username   = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name  = EXCLUDED.last_name,
                updated_at = NOW()
        RETURNING id
    """, user_id, username, first_name, last_name)
    return row["id"]


async def get_session_by_user(user_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM chat_sessions WHERE user_id = $1", user_id
    )
    return dict(row) if row else None


async def set_session_status(user_id: int, status: str) -> None:
    pool = await get_pool()
    await pool.execute("""
        UPDATE chat_sessions SET status = $1, updated_at = NOW()
        WHERE user_id = $2
    """, status, user_id)


async def set_session_tag(session_id: int, tag: str | None) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE chat_sessions SET tag = $1, updated_at = NOW() WHERE id = $2",
        tag, session_id
    )


async def get_all_sessions(status_filter: str | None = None) -> list[dict]:
    pool = await get_pool()
    if status_filter:
        rows = await pool.fetch("""
            SELECT * FROM chat_sessions WHERE status = $1
            ORDER BY updated_at DESC
        """, status_filter)
    else:
        rows = await pool.fetch("""
            SELECT * FROM chat_sessions ORDER BY updated_at DESC
        """)
    return [dict(r) for r in rows]


async def mark_session_read(session_id: int) -> None:
    pool = await get_pool()
    await pool.execute("""
        UPDATE chat_sessions SET unread_count = 0 WHERE id = $1
    """, session_id)
    await pool.execute("""
        UPDATE chat_messages SET is_read = TRUE
        WHERE session_id = $1 AND direction = 'in' AND is_read = FALSE
    """, session_id)


# ── Messages ──────────────────────────────────────────────────────────────────

async def save_message(
    user_id: int,
    direction: str,          # "in" | "out"
    content: str | None,
    msg_type: str = "text",
    media_url: str | None = None,
    tg_msg_id: int | None = None,
) -> int:
    """Save a message and update session metadata. Returns message id."""
    pool = await get_pool()

    # Ensure session exists
    session = await pool.fetchrow(
        "SELECT id FROM chat_sessions WHERE user_id = $1", user_id
    )
    if not session:
        return 0
    session_id = session["id"]

    msg_id = await pool.fetchval("""
        INSERT INTO chat_messages
            (session_id, user_id, direction, msg_type, content, media_url, tg_msg_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """, session_id, user_id, direction, msg_type, content, media_url, tg_msg_id)

    # Update session last_message + unread
    preview = (content or f"[{msg_type}]")[:80]
    if direction == "in":
        # Mark all previous outgoing messages as read (proxy read receipt:
        # client sent a message → they've seen everything before it)
        await pool.execute("""
            UPDATE chat_messages SET is_read = TRUE
            WHERE session_id = $1 AND direction = 'out' AND is_read = FALSE
        """, session_id)
        await pool.execute("""
            UPDATE chat_sessions
            SET last_message  = $1,
                updated_at    = NOW(),
                unread_count  = unread_count + 1
            WHERE id = $2
        """, preview, session_id)
    else:
        await pool.execute("""
            UPDATE chat_sessions
            SET last_message = $1, updated_at = NOW()
            WHERE id = $2
        """, preview, session_id)

    return msg_id


async def get_messages(session_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT * FROM chat_messages
        WHERE session_id = $1
        ORDER BY sent_at ASC
        LIMIT $2 OFFSET $3
    """, session_id, limit, offset)
    return [dict(r) for r in rows]


async def get_messages_after(session_id: int, after_id: int) -> list[dict]:
    """Return messages with id > after_id, ordered oldest first. Used for real-time polling."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT * FROM chat_messages
        WHERE session_id = $1 AND id > $2
        ORDER BY sent_at ASC
    """, session_id, after_id)
    return [dict(r) for r in rows]


async def get_all_sessions_rich() -> list[dict]:
    """Return sessions with unread counts, ordered by updated_at DESC."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT
            cs.*,
            (SELECT COUNT(*) FROM chat_messages cm
             WHERE cm.session_id = cs.id AND cm.direction = 'in' AND NOT cm.is_read) AS unread
        FROM chat_sessions cs
        ORDER BY cs.updated_at DESC
        LIMIT 200
    """)
    return [dict(r) for r in rows]


async def save_outgoing_message(
    user_id: int,
    content: str,
    msg_type: str = "text",
    tg_msg_id: int | None = None,
) -> None:
    """Save an outgoing (bot→user or manager→user) message to chat history."""
    await save_message(
        user_id=user_id,
        direction="out",
        content=content,
        msg_type=msg_type,
        tg_msg_id=tg_msg_id,
    )


# ── Quick replies ─────────────────────────────────────────────────────────────

async def get_quick_replies() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM quick_replies ORDER BY position ASC, id ASC"
    )
    return [dict(r) for r in rows]


async def create_quick_reply(title: str, content: str, position: int = 0) -> None:
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO quick_replies (title, content, position) VALUES ($1, $2, $3)",
        title, content, position
    )


async def delete_session(session_id: int) -> None:
    """Hard-delete a session and all its messages (cascade via FK)."""
    pool = await get_pool()
    await pool.execute("DELETE FROM chat_sessions WHERE id = $1", session_id)


async def delete_quick_reply(reply_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM quick_replies WHERE id = $1", reply_id)


async def update_quick_reply(reply_id: int, title: str, content: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE quick_replies SET title=$1, content=$2 WHERE id=$3",
        title, content, reply_id
    )
