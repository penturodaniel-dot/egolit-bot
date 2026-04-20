"""
Human-mode session tracking.

Sessions are stored in DB (human_sessions table) as the source of truth.
The admin panel can end sessions directly via DB — the bot will pick it up
on the next incoming message since is_human_mode() queries DB each time.
"""

from db.connection import get_pool

# Maps forwarded_message_id → original_user_id
# Used so manager replies to a forwarded msg are routed back to the right user.
# In-memory only — resets on restart (acceptable for MVP).
reply_map: dict[int, int] = {}


async def init_human_sessions() -> None:
    """Create table if not exists on startup."""
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS human_sessions (
            user_id    BIGINT PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            started_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)


async def is_human_mode(user_id: int) -> bool:
    """Check DB — source of truth (admin panel can end sessions without bot restart)."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT 1 FROM human_sessions WHERE user_id = $1", user_id
    )
    return row is not None


async def start_human_session(
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO human_sessions (user_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE SET started_at = NOW()
        """,
        user_id,
        username,
        first_name,
    )


async def end_human_session(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM human_sessions WHERE user_id = $1", user_id)
    # Clean up reply_map entries for this user
    for msg_id, uid in list(reply_map.items()):
        if uid == user_id:
            del reply_map[msg_id]


async def get_active_sessions():
    pool = await get_pool()
    return await pool.fetch(
        "SELECT user_id, username, first_name, started_at FROM human_sessions ORDER BY started_at DESC"
    )
